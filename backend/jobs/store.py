from __future__ import annotations
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Optional

from backend.database.db import get_db_connection
from backend.jobs.models import JobOpening, JobDemandSummary


def _norm(v) -> str:
    return re.sub(r"\s+", " ", str(v or "").strip()).casefold()


def _float(v):
    try:
        if v is None or str(v).strip() == "":
            return None
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _flatten_tags(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return []
        try:
            v = json.loads(s)
        except Exception:
            return [x.strip() for x in re.split(r"[,;]", s) if x.strip()]
    out = []
    def walk(x):
        if isinstance(x, (list, tuple)):
            for y in x: walk(y)
        elif isinstance(x, dict):
            for y in x.values(): walk(y)
        elif x is not None and str(x).strip():
            out.append(str(x).strip())
    walk(v)
    # preserve order / unique
    seen, clean = set(), []
    for x in out:
        k = x.casefold()
        if k not in seen:
            seen.add(k); clean.append(x)
    return clean


def ensure_jobs_schema(db_path=None):
    with get_db_connection(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS job_openings (
                job_id TEXT PRIMARY KEY,
                transient_id TEXT,
                title TEXT NOT NULL,
                company_name TEXT,
                description TEXT,
                roles_responsibility TEXT,
                sector_name TEXT,
                functional_area TEXT,
                min_education TEXT,
                min_experience REAL,
                max_experience REAL,
                vacancy_count INTEGER DEFAULT 0,
                min_ctc_monthly REAL,
                max_ctc_monthly REAL,
                min_ctc_annual REAL,
                max_ctc_annual REAL,
                wage_type TEXT,
                state TEXT,
                district TEXT,
                country TEXT,
                tags_json TEXT,
                posted_on TEXT,
                valid_upto TEXT,
                apply_url TEXT,
                source_system TEXT,
                is_active INTEGER DEFAULT 1,
                fetched_at TEXT,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_location ON job_openings(state,district)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_sector ON job_openings(sector_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_posted ON job_openings(posted_on)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_active ON job_openings(is_active)")


def _extract_jobs(payload) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    # Skill India / NCS response shape captured from the browser.
    candidates = [
        payload.get("Data", {}).get("Jobs", {}).get("Data") if isinstance(payload.get("Data"), dict) else None,
        payload.get("Jobs", {}).get("Data") if isinstance(payload.get("Jobs"), dict) else None,
        payload.get("Data") if isinstance(payload.get("Data"), list) else None,
        payload.get("jobs"),
    ]
    for c in candidates:
        if isinstance(c, list):
            return [x for x in c if isinstance(x, dict)]
    return []


def import_jobs_json(path: str | Path, db_path=None) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    payload = json.loads(p.read_text(encoding="utf-8-sig"))
    return import_jobs_payload(payload, db_path=db_path, source_file=str(p))


def import_jobs_payload(payload, db_path=None, source_file: str | None = None) -> dict:
    ensure_jobs_schema(db_path)
    jobs = _extract_jobs(payload)
    now = datetime.now(timezone.utc).isoformat()
    imported = 0
    with get_db_connection(db_path) as conn:
        for j in jobs:
            job_id = str(j.get("JobId") or j.get("Id") or "").strip()
            title = str(j.get("JobTitle") or j.get("Title") or "").strip()
            if not job_id or not title:
                continue
            loc = j.get("JobLocation") if isinstance(j.get("JobLocation"), dict) else {}
            state = j.get("JobLocationState") or loc.get("State")
            district = j.get("JobLocationDistrict") or loc.get("District")
            country = j.get("JobLocationCountry") or loc.get("Country")
            tags = _flatten_tags(j.get("SearchTags") if j.get("SearchTags") is not None else j.get("Tags"))
            conn.execute("""
                INSERT INTO job_openings(
                    job_id, transient_id, title, company_name, description, roles_responsibility,
                    sector_name, functional_area, min_education, min_experience, max_experience,
                    vacancy_count, min_ctc_monthly, max_ctc_monthly, min_ctc_annual, max_ctc_annual,
                    wage_type, state, district, country, tags_json, posted_on, valid_upto, apply_url,
                    source_system, is_active, fetched_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(job_id) DO UPDATE SET
                    transient_id=excluded.transient_id, title=excluded.title, company_name=excluded.company_name,
                    description=excluded.description, roles_responsibility=excluded.roles_responsibility,
                    sector_name=excluded.sector_name, functional_area=excluded.functional_area,
                    min_education=excluded.min_education, min_experience=excluded.min_experience,
                    max_experience=excluded.max_experience, vacancy_count=excluded.vacancy_count,
                    min_ctc_monthly=excluded.min_ctc_monthly, max_ctc_monthly=excluded.max_ctc_monthly,
                    min_ctc_annual=excluded.min_ctc_annual, max_ctc_annual=excluded.max_ctc_annual,
                    wage_type=excluded.wage_type, state=excluded.state, district=excluded.district,
                    country=excluded.country, tags_json=excluded.tags_json, posted_on=excluded.posted_on,
                    valid_upto=excluded.valid_upto, apply_url=excluded.apply_url,
                    source_system=excluded.source_system, is_active=excluded.is_active, fetched_at=excluded.fetched_at
            """, (
                job_id, str(j.get("JobTransientId") or "").strip() or None, title,
                str(j.get("CompanyName") or "").strip() or None,
                str(j.get("JobDescription") or "").strip() or None,
                str(j.get("RolesAndResponsiblty") or j.get("RolesAndResponsibility") or "").strip() or None,
                str(j.get("SectorName") or "").strip() or None,
                str(j.get("FunctionalAreaName") or "").strip() or None,
                str(j.get("MinEduQual") or "").strip() or None,
                _float(j.get("MinExperience")), _float(j.get("MaxExperience")),
                max(0, _int(j.get("VacancyCount"))), _float(j.get("MinCtcMonthly")), _float(j.get("MaxCtcMonthly")),
                _float(j.get("MinCtc")), _float(j.get("MaxCtc")),
                str(j.get("WageTypeDesc") or "").strip() or None,
                str(state or "").strip() or None, str(district or "").strip() or None, str(country or "").strip() or None,
                json.dumps(tags, ensure_ascii=False), str(j.get("PostedOn") or "").strip() or None,
                str(j.get("ValidUpto") or "").strip() or None, str(j.get("ApplyUrl") or "").strip() or None,
                str(j.get("SourceSystem") or j.get("SourceId") or source_file or "NCS").strip() or "NCS",
                1 if j.get("IsActive", True) else 0, now,
            ))
            imported += 1
    return {"source_records": len(jobs), "jobs_upserted": imported, "fetched_at": now}


def _row_to_job(r) -> JobOpening:
    d = dict(r)
    try: tags = json.loads(d.get("tags_json") or "[]")
    except Exception: tags = []
    return JobOpening(
        job_id=d["job_id"], title=d["title"], company_name=d.get("company_name"),
        description=d.get("description"), roles_responsibility=d.get("roles_responsibility"),
        sector_name=d.get("sector_name"), functional_area=d.get("functional_area"),
        min_education=d.get("min_education"), min_experience=d.get("min_experience"), max_experience=d.get("max_experience"),
        vacancy_count=d.get("vacancy_count") or 0, min_ctc_monthly=d.get("min_ctc_monthly"),
        max_ctc_monthly=d.get("max_ctc_monthly"), min_ctc_annual=d.get("min_ctc_annual"), max_ctc_annual=d.get("max_ctc_annual"),
        wage_type=d.get("wage_type"), state=d.get("state"), district=d.get("district"), country=d.get("country"),
        tags=tags, posted_on=d.get("posted_on"), valid_upto=d.get("valid_upto"), apply_url=d.get("apply_url"),
        source_system=d.get("source_system"), is_active=bool(d.get("is_active")), fetched_at=d.get("fetched_at"),
    )


def _is_not_expired(valid_upto: str | None, now: datetime | None = None) -> bool:
    if not valid_upto:
        return True
    now = now or datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(str(valid_upto).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= now
    except (TypeError, ValueError):
        # Keep malformed source rows visible instead of silently deleting them.
        return True


def _job_relevance(job: JobOpening, query: str) -> float:
    q = _norm(query)
    if not q:
        return 0.0
    tokens = [t for t in re.findall(r"[\w+#.-]+", q) if len(t) >= 2]
    title = _norm(job.title)
    tags = _norm(" ".join(job.tags))
    desc = _norm(" ".join(filter(None, [job.description, job.roles_responsibility, job.sector_name, job.functional_area])))
    score = 0.0
    if q == title:
        score += 100
    elif q in title:
        score += 55
    elif q in tags:
        score += 35
    elif q in desc:
        score += 15
    for t in tokens:
        if t in title: score += 8
        if t in tags: score += 5
        if t in desc: score += 2
    return score


def _role_match(job: JobOpening, query: str) -> bool:
    """Conservative role match used for demand statistics.

    Descriptions alone are not enough for multi-word role queries because generic
    terms such as installer/assistant/technician otherwise create large false matches.
    """
    q = _norm(query)
    tokens = [t for t in re.findall(r"[\w+#.-]+", q) if len(t) >= 2]
    if not tokens:
        return True
    role_text = _norm(" ".join(filter(None, [job.title, " ".join(job.tags), job.sector_name, job.functional_area])))
    if q and q in role_text:
        return True
    hits = sum(1 for t in set(tokens) if t in role_text)
    if len(set(tokens)) == 1:
        return hits >= 1
    return hits >= 2

def search_jobs(query: str, *, state: Optional[str] = None, district: Optional[str] = None,
                limit: int = 20, active_only: bool = True, include_expired: bool = False,
                strict_role: bool = False, db_path=None) -> list[JobOpening]:
    ensure_jobs_schema(db_path)
    q = _norm(query)
    tokens = [t for t in re.findall(r"[\w+#.-]+", q) if len(t) >= 2][:8]
    clauses, args = [], []
    if tokens:
        token_clauses = []
        for t in tokens:
            token_clauses.append("lower(title || ' ' || coalesce(description,'') || ' ' || coalesce(roles_responsibility,'') || ' ' || coalesce(sector_name,'') || ' ' || coalesce(functional_area,'') || ' ' || coalesce(tags_json,'')) LIKE ?")
            args.append(f"%{t}%")
        clauses.append("(" + " OR ".join(token_clauses) + ")")
    if active_only:
        clauses.append("is_active=1")
    if state:
        clauses.append("lower(trim(state))=lower(trim(?))"); args.append(state)
    if district:
        clauses.append("lower(trim(district))=lower(trim(?))"); args.append(district)
    where = " AND ".join(clauses) if clauses else "1=1"
    # Pull a wider candidate set, then rank with title/tags weighted above descriptions.
    scan_limit = max(50, min(int(limit) * 12, 1000))
    sql = f"""
      SELECT * FROM job_openings WHERE {where}
      ORDER BY coalesce(posted_on,'') DESC, vacancy_count DESC
      LIMIT ?
    """
    args.append(scan_limit)
    with get_db_connection(db_path) as conn:
        jobs = [_row_to_job(r) for r in conn.execute(sql, args).fetchall()]
    if not include_expired:
        jobs = [j for j in jobs if _is_not_expired(j.valid_upto)]
    if strict_role:
        jobs = [j for j in jobs if _role_match(j, query)]
    jobs.sort(key=lambda j: (_job_relevance(j, query), j.posted_on or "", j.vacancy_count), reverse=True)
    return jobs[:max(1, min(int(limit), 100))]

def job_evidence(query: str, *, state: Optional[str] = None, district: Optional[str] = None,
                 limit: int = 10, db_path=None) -> dict:
    """Return job evidence at the narrowest location scope that has data.

    Scope falls back district -> state -> national. The selected scope is explicit so
    callers never mistake state/national evidence for district-local demand.
    """
    scopes = []
    if state and district:
        scopes.append(("district", state, district))
    if state:
        scopes.append(("state", state, None))
    scopes.append(("national", None, None))
    for scope, st, dist in scopes:
        jobs = search_jobs(query, state=st, district=dist, limit=limit, strict_role=True, db_path=db_path)
        if jobs:
            summary = demand_summary(query, state=st, district=dist, db_path=db_path)
            return {
                "scope": scope,
                "state": st,
                "district": dist,
                "jobs": jobs,
                "summary": summary,
                "fallback_used": scope != ("district" if state and district else "state" if state else "national"),
            }
    return {
        "scope": "none", "state": state, "district": district, "jobs": [],
        "summary": demand_summary(query, state=state, district=district, db_path=db_path),
        "fallback_used": False,
    }

def _salary_mid(j: JobOpening):
    vals = [x for x in (j.min_ctc_monthly, j.max_ctc_monthly) if x is not None and x > 0]
    return sum(vals) / len(vals) if vals else None


def demand_summary(query: str, *, state: Optional[str] = None, district: Optional[str] = None,
                   db_path=None, max_scan: int = 500) -> JobDemandSummary:
    jobs = search_jobs(query, state=state, district=district, limit=max_scan, strict_role=True, db_path=db_path)
    vacancies = sum(max(0, j.vacancy_count) for j in jobs)
    mids = [x for x in (_salary_mid(j) for j in jobs) if x is not None]
    mins = [j.min_ctc_monthly for j in jobs if j.min_ctc_monthly and j.min_ctc_monthly > 0]
    maxs = [j.max_ctc_monthly for j in jobs if j.max_ctc_monthly and j.max_ctc_monthly > 0]
    districts = Counter((j.district or "Unknown").strip() for j in jobs)
    # Transparent heuristic for UI sorting only; never a labour-market probability.
    if not jobs:
        band = "NO_DATA"
    elif vacancies >= 100 or len(jobs) >= 25:
        band = "HIGH"
    elif vacancies >= 25 or len(jobs) >= 8:
        band = "MODERATE"
    else:
        band = "LIMITED"
    latest = max((j.posted_on for j in jobs if j.posted_on), default=None)
    sources = sorted({j.source_system for j in jobs if j.source_system})
    return JobDemandSummary(
        query=query, state=state, district=district, matched_job_postings=len(jobs), total_vacancies=vacancies,
        salary_records=len(mids), median_monthly_salary=round(median(mids), 2) if mids else None,
        advertised_monthly_min=min(mins) if mins else None, advertised_monthly_max=max(maxs) if maxs else None,
        top_districts=[{"district": d, "postings": c} for d, c in districts.most_common(5)],
        demand_band=band, latest_posted_on=latest, source_systems=sources,
    )


def jobs_data_status(db_path=None) -> dict:
    ensure_jobs_schema(db_path)
    with get_db_connection(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM job_openings").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM job_openings WHERE is_active=1").fetchone()[0]
        vacancies = conn.execute("SELECT COALESCE(SUM(vacancy_count),0) FROM job_openings WHERE is_active=1").fetchone()[0]
        latest = conn.execute("SELECT MAX(fetched_at) FROM job_openings").fetchone()[0]
        latest_post = conn.execute("SELECT MAX(posted_on) FROM job_openings WHERE is_active=1").fetchone()[0]
    return {"job_openings": total, "active_job_openings": active, "active_vacancies": vacancies,
            "latest_fetched_at": latest, "latest_posted_on": latest_post, "mode": "cached_live_snapshot"}
