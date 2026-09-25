from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from backend.database.db import DEFAULT_DB_PATH

_STOP = {
    'and','or','the','of','for','in','to','a','an','with','senior','junior','assistant',
    'operator','technician','executive','associate','worker','specialist','manager','engineer',
    'level','vertical','horizontal','progression','career','pathway','role'
}


def _norm(text: str | None) -> str:
    s = (text or '').casefold()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _tokens(text: str | None, *, keep_generic: bool = False) -> set[str]:
    toks = set(_norm(text).split())
    if keep_generic:
        return toks
    return {t for t in toks if len(t) > 2 and t not in _STOP}


def _split_occupation(raw: str | None) -> list[str]:
    if not raw:
        return []
    bits = re.split(r'\s*(?:,|/|;|\||\band\b|\&)\s*', raw, flags=re.I)
    out=[]
    for x in bits:
        x=re.sub(r'\s+',' ',x).strip(' -–—')
        if x and len(x) >= 3 and x.casefold() not in {y.casefold() for y in out}:
            out.append(x)
    return out or [raw.strip()]


def _parse_pathway(raw: str | None) -> list[str]:
    """Extract role-like chunks without claiming they are linked qualifications."""
    if not raw:
        return []
    s = raw.replace('\r','\n')
    s = re.sub(r'(?i)\b(vertical|horizontal)\s+progression\b\s*[-–—:]*', '\n', s)
    s = re.sub(r'(?i)\blevel\s*\d+(?:\.\d+)?\s*[:\-–—]*', '', s)
    s = re.sub(r'(?i)\bcareer\s+progression\b\s*[:\-–—]*', '\n', s)
    parts = re.split(r'[\n;,→]+|\s+->\s+|\s+to\s+', s)
    out=[]
    for p in parts:
        p=re.sub(r'\s+',' ',p).strip(' .:-–—')
        if not p or len(p)<3:
            continue
        if _norm(p) in {'vertical','horizontal','progression','na','n a','not applicable'}:
            continue
        if p.casefold() not in {x.casefold() for x in out}:
            out.append(p)
    return out[:12]


@dataclass
class OccupationTaxonomy:
    db_path: Path = DEFAULT_DB_PATH

    def _conn(self):
        c=sqlite3.connect(str(self.db_path)); c.row_factory=sqlite3.Row; return c

    def status(self) -> dict:
        with self._conn() as c:
            q=c.execute("SELECT COUNT(*) c FROM qualifications").fetchone()['c']
            occ=c.execute("SELECT COUNT(DISTINCT proposed_occupation) c FROM qualifications WHERE TRIM(COALESCE(proposed_occupation,''))<>''").fetchone()['c']
            prog=c.execute("SELECT COUNT(*) c FROM qualifications WHERE TRIM(COALESCE(progression_pathway,''))<>''").fetchone()['c']
            sectors=c.execute("SELECT COUNT(DISTINCT sector_name) c FROM qualifications WHERE TRIM(COALESCE(sector_name,''))<>''").fetchone()['c']
        return {
            'qualifications': q,
            'distinct_raw_occupation_labels': occ,
            'qualifications_with_official_progression_text': prog,
            'sectors': sectors,
            'mode': 'derived_from_local_nqr',
            'taxonomy_truth': 'Aliases/families are derived for retrieval; official NQR occupation/progression text is preserved separately.'
        }

    def search(self, query: str, sector: Optional[str]=None, limit: int=20) -> list[dict]:
        qnorm=_norm(query); qt=_tokens(query, keep_generic=True)
        if not qnorm:
            return []
        sql="SELECT code,title,sector_name,proposed_occupation,nsqf_level_numeric FROM qualifications WHERE 1=1"
        args=[]
        if sector:
            sql += " AND LOWER(sector_name)=LOWER(?)"; args.append(sector)
        with self._conn() as c:
            rows=c.execute(sql,args).fetchall()
        groups={}
        for r in rows:
            occ=(r['proposed_occupation'] or '').strip() or r['title']
            aliases=[r['title'], *_split_occupation(r['proposed_occupation'])]
            text=' '.join(x for x in aliases if x)
            nt=_tokens(text, keep_generic=True)
            if qnorm not in _norm(text) and not (qt and len(qt & nt)/max(1,len(qt)) >= .5):
                continue
            key=(_norm(occ), (r['sector_name'] or '').casefold())
            g=groups.setdefault(key, {
                'canonical_occupation': occ,
                'sector': r['sector_name'],
                'aliases': set(),
                'qualification_codes': [],
                'qualification_titles': [],
                'nsqf_levels': set(),
                '_score': 0.0,
            })
            for a in aliases:
                if a: g['aliases'].add(a)
            if r['code']: g['qualification_codes'].append(r['code'])
            g['qualification_titles'].append(r['title'])
            if r['nsqf_level_numeric'] is not None: g['nsqf_levels'].add(float(r['nsqf_level_numeric']))
            score = 3.0 if qnorm == _norm(occ) else 2.0 if qnorm in _norm(occ) else 1.0
            score += len(qt & nt)/max(1,len(qt))
            g['_score']=max(g['_score'], score)
        out=[]
        for g in groups.values():
            g['aliases']=sorted(g['aliases'])[:20]
            g['qualification_codes']=list(dict.fromkeys(g['qualification_codes']))[:30]
            g['qualification_titles']=list(dict.fromkeys(g['qualification_titles']))[:30]
            g['nsqf_levels']=sorted(g['nsqf_levels'])
            out.append(g)
        out.sort(key=lambda x:(-x['_score'], x['canonical_occupation']))
        for x in out: x.pop('_score',None)
        return out[:max(1,min(limit,100))]


@dataclass
class CareerProgressionEngine:
    db_path: Path = DEFAULT_DB_PATH

    def _conn(self):
        c=sqlite3.connect(str(self.db_path)); c.row_factory=sqlite3.Row; return c

    def _qualification(self, code: str):
        with self._conn() as c:
            return c.execute("SELECT * FROM qualifications WHERE code=? LIMIT 1",(code,)).fetchone()

    def analyze(self, qualification_code: str, related_limit: int=8) -> dict:
        row=self._qualification(qualification_code)
        if not row:
            raise ValueError(f'Qualification not found: {qualification_code}')
        row=dict(row)
        raw=row.get('progression_pathway') or ''
        pathway_roles=_parse_pathway(raw)
        level=row.get('nsqf_level_numeric')
        sector=row.get('sector_name')
        occupation=row.get('proposed_occupation') or ''
        base_tokens=_tokens(occupation) or _tokens(row.get('title'))

        with self._conn() as c:
            candidates=c.execute(
                "SELECT code,title,sector_name,proposed_occupation,nsqf_level_numeric,progression_pathway FROM qualifications WHERE code<>? AND LOWER(COALESCE(sector_name,''))=LOWER(COALESCE(?,''))",
                (qualification_code,sector)
            ).fetchall()

        # Link official pathway role text to existing NQR records only when lexical evidence is strong.
        official_steps=[]
        for role in pathway_roles:
            rt=_tokens(role, keep_generic=True)
            best=None; bestscore=0
            for c in candidates:
                hay=f"{c['title']} {c['proposed_occupation'] or ''}"
                ht=_tokens(hay, keep_generic=True)
                if not rt or not ht: continue
                overlap=len(rt & ht)/max(1,len(rt))
                title_norm=_norm(c['title'])
                score=overlap + (0.6 if _norm(role) in title_norm or title_norm in _norm(role) else 0)
                if score>bestscore:
                    bestscore=score; best=c
            item={'role_text': role, 'evidence':'NQR_PROGRESSION_PATHWAY_TEXT', 'matched_qualification':None}
            if best is not None and bestscore >= 0.68:
                item['matched_qualification']={
                    'code':best['code'],'title':best['title'],'nsqf_level':best['nsqf_level_numeric'],
                    'sector':best['sector_name'],'proposed_occupation':best['proposed_occupation'],
                    'match_basis':'LEXICAL_LINK_TO_NQR_RECORD'
                }
            official_steps.append(item)

        related=[]
        for c in candidates:
            clevel=c['nsqf_level_numeric']
            if level is not None and clevel is not None and float(clevel) <= float(level):
                continue
            ct=_tokens(c['proposed_occupation']) or _tokens(c['title'])
            if not base_tokens or not ct: continue
            overlap=len(base_tokens & ct)/max(1,len(base_tokens | ct))
            if overlap < .16: continue
            related.append((overlap, c))
        related.sort(key=lambda z:(-z[0], (z[1]['nsqf_level_numeric'] or 99), z[1]['title']))
        related_rows=[]
        seen=set()
        for score,c in related:
            if c['code'] in seen: continue
            seen.add(c['code'])
            related_rows.append({
                'code':c['code'],'title':c['title'],'nsqf_level':c['nsqf_level_numeric'],
                'sector':c['sector_name'],'proposed_occupation':c['proposed_occupation'],
                'relation':'RELATED_HIGHER_NSQF_SAME_OCCUPATION_FAMILY',
                'similarity':round(score,3),
                'warning':'Related higher-level qualification; not claimed as the official next step unless explicitly linked above.'
            })
            if len(related_rows)>=related_limit: break

        return {
            'qualification': {
                'code':row.get('code'),'title':row.get('title'),'sector':sector,
                'proposed_occupation':row.get('proposed_occupation'),'nsqf_level':level,
            },
            'official_progression_text': raw or None,
            'official_progression_roles': official_steps,
            'related_higher_nsqf_options': related_rows,
            'has_official_progression_text': bool(raw.strip()),
            'evidence_policy': 'Official progression text is preserved verbatim. Related higher-NSQF options are retrieval aids, not asserted career steps.'
        }
