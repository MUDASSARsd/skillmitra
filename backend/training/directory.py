from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup

from backend.database.db import get_db_connection
from backend.training.store import ensure_training_schema

KAUSHAL_BHARAT_SOURCE = "Kaushal Bharat (DDU-GKY)"


def _norm(v: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (v or "").strip()).casefold()


def _to_int(v) -> Optional[int]:
    if v is None:
        return None
    s = re.sub(r"[^0-9-]", "", str(v))
    if not s or s == "-":
        return None
    try:
        return int(s)
    except ValueError:
        return None


def ensure_directory_schema(db_path=None):
    ensure_training_schema(db_path)
    with get_db_connection(db_path) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(training_centres)").fetchall()}
        wanted = {
            "sanction_order": "TEXT",
            "reported_batch_count": "INTEGER",
            "candidate_enrolled": "INTEGER",
            "candidate_undergoing": "INTEGER",
            "candidate_trained": "INTEGER",
            "candidate_certified": "INTEGER",
            "candidate_placed": "INTEGER",
            "directory_as_of": "TEXT",
        }
        for name, ddl in wanted.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE training_centres ADD COLUMN {name} {ddl}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tc_source ON training_centres(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tc_verification ON training_centres(verification_status)")


def _extract_as_of(text: str) -> Optional[str]:
    m = re.search(r"as of\s+(\d{1,2}-[A-Za-z]{3}-\d{4})", text or "", re.I)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%d-%b-%Y").date().isoformat()
    except ValueError:
        return m.group(1)


def parse_kaushal_bharat_html(html: str, source_url: str) -> list[dict]:
    """Parse the public DDU-GKY Training Center Wise Details table.

    The report is directory/history evidence. Batch Count is an aggregate report
    metric, NOT proof of an active enrolment batch today.
    """
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    as_of = _extract_as_of(page_text)
    tables = soup.find_all("table")
    out: list[dict] = []
    for table in tables:
        rows = table.find_all("tr")
        if not rows:
            continue
        headers = [re.sub(r"\s+", " ", x.get_text(" ", strip=True)) for x in rows[0].find_all(["th", "td"])]
        joined = " | ".join(headers).casefold()
        if "tc name" not in joined or "tc id" not in joined or "batch count" not in joined:
            continue
        for tr in rows[1:]:
            cells = [re.sub(r"\s+", " ", x.get_text(" ", strip=True)) for x in tr.find_all(["th", "td"])]
            if len(cells) < 7:
                continue
            # Public report currently exposes 17 columns in this fixed order.
            # We intentionally do not infer district, QP, or current batch status.
            if any(c.casefold() == "total" for c in cells[:5]):
                continue
            state = cells[1] if len(cells) > 1 else ""
            sanction = cells[2] if len(cells) > 2 else ""
            pia = cells[3] if len(cells) > 3 else ""
            tc_name = cells[4] if len(cells) > 4 else ""
            tc_id = cells[5] if len(cells) > 5 else ""
            if not tc_name or not tc_id or not state:
                continue
            out.append({
                "centre_id": tc_id,
                "centre_name": tc_name,
                "training_partner": pia or None,
                "state": state,
                "district": None,
                "sanction_order": sanction or None,
                "reported_batch_count": _to_int(cells[6] if len(cells) > 6 else None),
                "candidate_enrolled": _to_int(cells[7] if len(cells) > 7 else None),
                "candidate_trained": _to_int(cells[9] if len(cells) > 9 else None),
                "candidate_undergoing": _to_int(cells[11] if len(cells) > 11 else None),
                "candidate_certified": _to_int(cells[13] if len(cells) > 13 else None),
                "candidate_placed": _to_int(cells[16] if len(cells) > 16 else None),
                "directory_as_of": as_of,
                "source": KAUSHAL_BHARAT_SOURCE,
                "source_url": source_url,
                "verification_status": "OFFICIAL_DIRECTORY",
            })
    return out


def upsert_directory_centres(records: Iterable[dict], db_path=None) -> dict:
    ensure_directory_schema(db_path)
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    with get_db_connection(db_path) as conn:
        for r in records:
            cid = str(r.get("centre_id") or "").strip()
            name = str(r.get("centre_name") or "").strip()
            if not cid or not name:
                continue
            conn.execute("""
                INSERT INTO training_centres(
                    centre_id, centre_name, state, district, address, latitude, longitude,
                    qualification_code, training_partner, scheme, status, pincode,
                    source, source_url, verification_status, last_verified_at,
                    sanction_order, reported_batch_count, candidate_enrolled,
                    candidate_undergoing, candidate_trained, candidate_certified,
                    candidate_placed, directory_as_of
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(centre_id) DO UPDATE SET
                    centre_name=excluded.centre_name,
                    state=excluded.state,
                    training_partner=excluded.training_partner,
                    source=excluded.source,
                    source_url=excluded.source_url,
                    verification_status=excluded.verification_status,
                    last_verified_at=excluded.last_verified_at,
                    sanction_order=excluded.sanction_order,
                    reported_batch_count=excluded.reported_batch_count,
                    candidate_enrolled=excluded.candidate_enrolled,
                    candidate_undergoing=excluded.candidate_undergoing,
                    candidate_trained=excluded.candidate_trained,
                    candidate_certified=excluded.candidate_certified,
                    candidate_placed=excluded.candidate_placed,
                    directory_as_of=excluded.directory_as_of
            """, (
                cid, name, r.get("state"), r.get("district"), r.get("address"),
                r.get("latitude"), r.get("longitude"), r.get("qualification_code"),
                r.get("training_partner"), r.get("scheme") or "DDU-GKY",
                "DIRECTORY_VERIFIED", r.get("pincode"), r.get("source") or KAUSHAL_BHARAT_SOURCE,
                r.get("source_url"), r.get("verification_status") or "OFFICIAL_DIRECTORY",
                now, r.get("sanction_order"), r.get("reported_batch_count"),
                r.get("candidate_enrolled"), r.get("candidate_undergoing"),
                r.get("candidate_trained"), r.get("candidate_certified"),
                r.get("candidate_placed"), r.get("directory_as_of"),
            ))
            count += 1
    return {"centres_upserted": count, "last_verified_at": now}


def sync_kaushal_bharat_urls(urls: Iterable[str], db_path=None, timeout: int = 30) -> dict:
    all_records: list[dict] = []
    failures: list[dict] = []
    reports = 0
    for url in urls:
        url = str(url).strip()
        if not url:
            continue
        try:
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": "SkillMitra/1.0 official-data-sync"})
            resp.raise_for_status()
            recs = parse_kaushal_bharat_html(resp.text, url)
            if not recs:
                raise ValueError("No training-centre table found")
            all_records.extend(recs)
            reports += 1
        except Exception as exc:
            failures.append({"url": url, "error": str(exc)[:300]})
    result = upsert_directory_centres(all_records, db_path=db_path) if all_records else {"centres_upserted": 0, "last_verified_at": None}
    result.update({"reports_synced": reports, "records_seen": len(all_records), "failures": failures})
    return result


def load_source_urls(path: str | Path) -> list[str]:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(obj, dict):
        obj = obj.get("urls", [])
    if not isinstance(obj, list):
        raise ValueError("Source file must be a JSON array or {'urls': [...]} object")
    return [str(x).strip() for x in obj if str(x).strip()]


def find_directory_centres(*, state: Optional[str] = None, district: Optional[str] = None,
                           query: Optional[str] = None, limit: int = 25, db_path=None) -> list[dict]:
    ensure_directory_schema(db_path)
    clauses = ["verification_status IN ('OFFICIAL_DIRECTORY','OFFICIAL_SOURCE')"]
    args: list = []
    if state:
        clauses.append("lower(trim(state)) = lower(trim(?))")
        args.append(state)
    if district:
        clauses.append("lower(trim(district)) = lower(trim(?))")
        args.append(district)
    if query:
        clauses.append("(lower(centre_name) LIKE ? OR lower(training_partner) LIKE ?)")
        q = f"%{_norm(query)}%"
        args.extend([q, q])
    args.append(max(1, min(int(limit), 100)))
    sql = f"""
      SELECT centre_id, centre_name, training_partner, state, district, address, pincode,
             source, source_url, verification_status, last_verified_at, sanction_order,
             reported_batch_count, candidate_enrolled, candidate_undergoing, candidate_trained,
             candidate_certified, candidate_placed, directory_as_of
      FROM training_centres
      WHERE {' AND '.join(clauses)}
      ORDER BY COALESCE(candidate_undergoing,0) DESC, COALESCE(reported_batch_count,0) DESC, centre_name
      LIMIT ?
    """
    with get_db_connection(db_path) as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def directory_status(db_path=None) -> dict:
    ensure_directory_schema(db_path)
    with get_db_connection(db_path) as conn:
        row = conn.execute("""
          SELECT COUNT(*) AS n, COUNT(DISTINCT state) AS states,
                 MAX(last_verified_at) AS latest_verified_at,
                 MAX(directory_as_of) AS latest_directory_as_of
          FROM training_centres
          WHERE verification_status='OFFICIAL_DIRECTORY'
        """).fetchone()
    return {
        "verified_directory_centres": row["n"],
        "states_covered": row["states"],
        "latest_verified_at": row["latest_verified_at"],
        "latest_directory_as_of": row["latest_directory_as_of"],
        "batch_truth": "UNVERIFIED_UNLESS_OFFERING_EXISTS",
    }
