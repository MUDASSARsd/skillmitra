from __future__ import annotations
import json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from backend.database.db import get_db_connection
from backend.courses.models import SkillIndiaCourse, CourseMatch

SOURCE_URL = "https://courses.skillindiadigital.gov.in/courses/"

_STOP = {"and","or","the","of","for","to","in","a","an","with","under","cum","level","nsqf","year","years","hrs","hour","hours","english","hindi","course","training"}

def _norm(v: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (v or "").strip()).casefold()

def _tokens(v: Optional[str]) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9]+", _norm(v)) if len(x) >= 3 and x not in _STOP}

def _first(items, key):
    if not isinstance(items, list): return None
    for x in items:
        if isinstance(x, dict) and x.get(key): return str(x.get(key)).strip()
    return None

def _join_vals(items, key):
    if not isinstance(items, list): return []
    out=[]
    for x in items:
        if isinstance(x,dict) and x.get(key):
            s=str(x[key]).strip()
            if s and s not in out: out.append(s)
    return out

def ensure_course_schema(db_path=None):
    with get_db_connection(db_path) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS skill_india_courses (
            course_id TEXT PRIMARY KEY,
            code TEXT, readable_code TEXT, title TEXT NOT NULL,
            qp_codes_json TEXT, nos_codes_json TEXT, nsqf_level REAL,
            provider TEXT, provider_id TEXT, program TEXT, initiative TEXT,
            language TEXT, price REAL, course_mode TEXT, availability INTEGER,
            start_date TEXT, end_date TEXT, occupation TEXT, domain TEXT,
            description TEXT, enrollment_count INTEGER, rating_average REAL,
            age_requirement TEXT, educational_qualification TEXT, industry_experience TEXT,
            source_url TEXT, fetched_at TEXT, imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_courses_title ON skill_india_courses(title)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_courses_nsqf ON skill_india_courses(nsqf_level)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_courses_language ON skill_india_courses(language)")

def import_skill_india_json(path: str | Path, db_path=None) -> dict:
    ensure_course_schema(db_path)
    p=Path(path)
    obj=json.loads(p.read_text(encoding="utf-8"))
    courses=((obj.get("Data") or {}).get("Courses") or [])
    pagination=(obj.get("Data") or {}).get("Pagination") or {}
    now=datetime.now(timezone.utc).isoformat()
    up=0
    with get_db_connection(db_path) as conn:
        for c in courses:
            if not isinstance(c,dict): continue
            cid=str(c.get("Id") or c.get("Code") or "").strip()
            title=str(c.get("Title") or "").strip()
            if not cid or not title: continue
            info=c.get("CourseInformation") or {}
            qp=_join_vals(info.get("QpCode"),"QpCode")
            nos=_join_vals(info.get("NosCode"),"Noscode")
            criteria={str(x.get("Name")):str(x.get("Value") or "") for x in (c.get("CourseCriteria") or []) if isinstance(x,dict)}
            programs=[str(x.get("Program")) for x in (c.get("Programs") or []) if isinstance(x,dict) and x.get("Program")]
            initiatives=[str(x.get("Initiative")) for x in (c.get("InitiativeOfs") or []) if isinstance(x,dict) and x.get("Initiative")]
            occ=[str(x.get("Occupation")) for x in (c.get("Occupations") or []) if isinstance(x,dict) and x.get("Occupation")]
            dom=[str(x.get("Domain")) for x in (c.get("Domains") or []) if isinstance(x,dict) and x.get("Domain")]
            mode={1:"online",2:"offline",3:"blended"}.get(c.get("CourseMode"), str(c.get("CourseMode") or "") or None)
            conn.execute("""
            INSERT INTO skill_india_courses(
              course_id,code,readable_code,title,qp_codes_json,nos_codes_json,nsqf_level,
              provider,provider_id,program,initiative,language,price,course_mode,availability,
              start_date,end_date,occupation,domain,description,enrollment_count,rating_average,
              age_requirement,educational_qualification,industry_experience,source_url,fetched_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(course_id) DO UPDATE SET
              code=excluded.code, readable_code=excluded.readable_code, title=excluded.title,
              qp_codes_json=excluded.qp_codes_json, nos_codes_json=excluded.nos_codes_json,
              nsqf_level=excluded.nsqf_level, provider=excluded.provider, provider_id=excluded.provider_id,
              program=excluded.program, initiative=excluded.initiative, language=excluded.language,
              price=excluded.price, course_mode=excluded.course_mode, availability=excluded.availability,
              start_date=excluded.start_date, end_date=excluded.end_date, occupation=excluded.occupation,
              domain=excluded.domain, description=excluded.description, enrollment_count=excluded.enrollment_count,
              rating_average=excluded.rating_average, age_requirement=excluded.age_requirement,
              educational_qualification=excluded.educational_qualification, industry_experience=excluded.industry_experience,
              source_url=excluded.source_url, fetched_at=excluded.fetched_at
            """,(
              cid,c.get("Code"),c.get("ReadableCode"),title,json.dumps(qp,ensure_ascii=False),json.dumps(nos,ensure_ascii=False),
              info.get("NsqfLevel"),c.get("CreatedBy"),c.get("CourseProviderId"),programs[0] if programs else c.get("ProgramBy"),
              initiatives[0] if initiatives else None,c.get("Language"),c.get("Price"),mode,c.get("Availability"),
              c.get("StartDate"),c.get("EndDate"),occ[0] if occ else None,dom[0] if dom else None,
              c.get("ShortDescription") or c.get("LongDescription") or c.get("LearningOutcome"),
              (c.get("CourseStatistic") or {}).get("EnrollmentCount"),(c.get("CourseStatistic") or {}).get("RatingAverage"),
              criteria.get("age_requirement"),criteria.get("educational_qualification"),criteria.get("industry_experience"),
              SOURCE_URL,now
            ))
            up+=1
    return {"courses_upserted":up,"snapshot_page":pagination.get("CurrentPageNumber"),"snapshot_page_size":pagination.get("CurrentPageSize"),"portal_total_count_at_capture":pagination.get("TotalCount"),"fetched_at":now}

def _row_to_course(r) -> SkillIndiaCourse:
    d=dict(r)
    try: d["qp_codes"]=json.loads(d.pop("qp_codes_json") or "[]")
    except Exception: d["qp_codes"]=[]
    try: d["nos_codes"]=json.loads(d.pop("nos_codes_json") or "[]")
    except Exception: d["nos_codes"]=[]
    return SkillIndiaCourse(**d)

def course_data_status(db_path=None) -> dict:
    ensure_course_schema(db_path)
    with get_db_connection(db_path) as conn:
        n=conn.execute("SELECT COUNT(*) FROM skill_india_courses").fetchone()[0]
        avail=conn.execute("SELECT COUNT(*) FROM skill_india_courses WHERE availability=1").fetchone()[0]
        latest=conn.execute("SELECT MAX(fetched_at) FROM skill_india_courses").fetchone()[0]
        qpc=conn.execute("SELECT COUNT(*) FROM skill_india_courses WHERE qp_codes_json IS NOT NULL AND qp_codes_json NOT IN ('','[]')").fetchone()[0]
    return {"cached_courses":n,"availability_flagged_courses":avail,"courses_with_qp_code":qpc,"latest_fetched_at":latest,"mode":"cached_skill_india_catalogue","live_batch_confirmation_required":True}

def search_courses(query: str, *, language: Optional[str]=None, limit:int=20, db_path=None) -> list[CourseMatch]:
    ensure_course_schema(db_path)
    qt=_tokens(query)
    if not qt: return []
    with get_db_connection(db_path) as conn:
        rows=conn.execute("SELECT * FROM skill_india_courses").fetchall()
    scored=[]
    for r in rows:
        c=_row_to_course(r)
        if language and _norm(c.language)!=_norm(language): continue
        title_t=_tokens(c.title); occ_t=_tokens(c.occupation); dom_t=_tokens(c.domain); desc_t=_tokens(c.description)
        exact=_norm(query)==_norm(c.title)
        inter_title=len(qt & title_t); inter_occ=len(qt & occ_t); inter_dom=len(qt & dom_t); inter_desc=len(qt & desc_t)
        score=(1.0 if exact else 0.0)+0.22*inter_title+0.12*inter_occ+0.08*inter_dom+0.02*min(inter_desc,4)
        if not exact and inter_title==0 and inter_occ==0 and inter_dom==0: continue
        denom=max(1,len(qt))
        score=min(0.99 if not exact else 1.0, score/denom if not exact else 1.0)
        mt="exact_title" if exact else ("title" if inter_title else "occupation_domain")
        scored.append((score,c,mt))
    scored.sort(key=lambda x:(-x[0],-(x[1].enrollment_count or 0),x[1].title.casefold()))
    return [CourseMatch(course=c,match_type=mt,match_score=round(s,3)) for s,c,mt in scored[:max(1,min(limit,100))]]

def courses_for_qualification(qualification_code: str, *, limit:int=10, db_path=None) -> list[CourseMatch]:
    ensure_course_schema(db_path)
    with get_db_connection(db_path) as conn:
        q=conn.execute("SELECT title, code, proposed_occupation FROM qualifications WHERE lower(trim(code))=lower(trim(?)) LIMIT 1",(qualification_code,)).fetchone()
        if not q: return []
        rows=conn.execute("SELECT * FROM skill_india_courses").fetchall()
    # First, exact QP-code evidence where a course exposes one of the same legacy/external codes.
    exact=[]
    code_norm=_norm(qualification_code)
    for r in rows:
        c=_row_to_course(r)
        if any(_norm(x)==code_norm for x in c.qp_codes): exact.append(CourseMatch(course=c,match_type="exact_qp_code",match_score=1.0))
    if exact: return exact[:limit]
    # NQR and Skill India code schemes often differ; use deterministic title/occupation matching as fallback.
    title=str(q["title"] or "").strip(); occupation=str(q["proposed_occupation"] or "").strip()
    primary=search_courses(title,limit=limit,db_path=db_path)
    if primary: return primary
    return search_courses(occupation,limit=limit,db_path=db_path) if occupation else []
