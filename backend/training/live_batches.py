from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Iterable, Optional

from backend.database.db import get_db_connection


def _norm(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "").strip()).casefold()


def _pick(d: dict, *names: str):
    if not isinstance(d, dict):
        return None
    by_norm = {re.sub(r"[^a-z0-9]", "", str(k).casefold()): v for k, v in d.items()}
    for name in names:
        key = re.sub(r"[^a-z0-9]", "", name.casefold())
        if key in by_norm and by_norm[key] not in (None, "", []):
            return by_norm[key]
    return None


def _int(v):
    try:
        if v in (None, ""):
            return None
        return int(float(str(v).replace(",", "").strip()))
    except Exception:
        return None


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(_norm(p) for p in parts)
    return f"{prefix}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:18]}"


def ensure_live_batch_schema(db_path=None):
    with get_db_connection(db_path) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS training_batch_observations (
            observation_id TEXT PRIMARY KEY,
            batch_id TEXT,
            centre_id TEXT,
            centre_name TEXT,
            training_partner TEXT,
            qualification_code TEXT,
            job_role TEXT,
            sector TEXT,
            scheme TEXT,
            state TEXT,
            district TEXT,
            address TEXT,
            start_date TEXT,
            end_date TEXT,
            timing TEXT,
            capacity INTEGER,
            seats_available INTEGER,
            raw_status TEXT,
            normalized_status TEXT NOT NULL DEFAULT 'UNKNOWN',
            source TEXT NOT NULL,
            source_url TEXT,
            fetched_at TEXT NOT NULL,
            payload_json TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tbo_code ON training_batch_observations(qualification_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tbo_role ON training_batch_observations(job_role)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tbo_location ON training_batch_observations(state,district)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tbo_status ON training_batch_observations(normalized_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tbo_batch ON training_batch_observations(batch_id)")


def _walk_dicts(obj: Any) -> Iterable[dict]:
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_dicts(v)


def _looks_like_batch(d: dict) -> bool:
    # Avoid treating every nested object as a batch. Require centre/batch identity plus
    # at least one training-specific field.
    batch = _pick(d, "BatchId", "BatchID", "batch_id", "batchCode", "batch_code")
    centre = _pick(d, "TrainingCentre", "TrainingCenter", "CentreName", "CenterName", "TcName", "training_centre", "training_center")
    role = _pick(d, "JobRole", "job_role", "CourseName", "QualificationName", "course_name")
    qcode = _pick(d, "QpCode", "QPCode", "CourseCode", "qualification_code", "QualificationCode")
    start = _pick(d, "StartDate", "BatchStartDate", "batch_start_date")
    status = _pick(d, "BatchStatus", "Status", "availability_status", "AvailabilityStatus")
    return bool((batch or centre) and (role or qcode or start or status))




def _format_batch_timing(v: Any) -> Optional[str]:
    """Convert SIDH BatchTiming objects to a readable India-local time string.

    Raw payload_json is still preserved, so no information is lost.
    """
    if v in (None, "", []):
        return None
    if not isinstance(v, list):
        return str(v).strip()
    parts = []
    india = ZoneInfo("Asia/Kolkata")
    for item in v:
        if not isinstance(item, dict):
            continue
        day = _pick(item, "DayOfWeek", "day_of_week") or ""
        start = _pick(item, "StartTime", "start_time")
        end = _pick(item, "EndTime", "end_time")
        def fmt(x):
            if not x:
                return None
            try:
                dt = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(india).strftime("%I:%M %p").lstrip("0")
            except Exception:
                return str(x)
        a, b = fmt(start), fmt(end)
        if a and b:
            parts.append(f"{day + ' ' if day else ''}{a} to {b} IST")
        elif a:
            parts.append(f"{day + ' ' if day else ''}{a} IST")
        elif day:
            parts.append(str(day))
    return "; ".join(parts) if parts else json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def _normalize_status(raw: Any, seats_available: Optional[int], end_date: Optional[str], *, listed_live: bool = False) -> str:
    s = _norm(raw)
    if any(x in s for x in ("active", "open", "ongoing", "available", "enrol", "enroll", "started")):
        return "VERIFIED_ACTIVE_BATCH"
    if any(x in s for x in ("closed", "completed", "inactive", "cancelled", "canceled", "full", "expired")):
        return "VERIFIED_NO_ACTIVE_BATCH"
    if seats_available is not None:
        return "VERIFIED_ACTIVE_BATCH" if seats_available > 0 else "VERIFIED_NO_ACTIVE_BATCH"
    # An end date in the past is useful evidence of non-currentness even when raw status is absent.
    if end_date:
        try:
            dt = datetime.fromisoformat(str(end_date).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt.astimezone(timezone.utc) < datetime.now(timezone.utc):
                return "VERIFIED_NO_ACTIVE_BATCH"
        except Exception:
            pass
    # SIDH's Data.SchemeBatchDetails is the selectable current/future batch listing.
    # A record present in that live collection is therefore positive batch evidence even
    # when the API's Status field is null. We still reject records whose end date is past.
    if listed_live:
        return "VERIFIED_ACTIVE_BATCH"
    return "VERIFIED_BATCH_STATUS_UNKNOWN"


def _canonical_row(d: dict, *, source: str, source_url: Optional[str], fetched_at: str, listed_live: bool = False) -> Optional[dict]:
    if not _looks_like_batch(d):
        return None
    # SipBatchId is the batch id displayed to learners; BatchId is an internal SIDH id.
    batch_id = _pick(d, "SipBatchId", "BatchId", "BatchID", "batch_id", "batchCode", "batch_code")
    centre_id = _pick(d, "TcId", "TrainingCentreId", "TrainingCenterId", "CentreId", "CenterId", "centre_id", "center_id")
    centre_name = _pick(d, "TcName", "TrainingCentre", "TrainingCenter", "CentreName", "CenterName", "training_centre", "training_center")
    partner = _pick(d, "TpName", "TrainingPartner", "TrainingPartnerName", "PartnerName", "training_partner")
    qcode = _pick(d, "CourseCode", "QpCode", "QPCode", "qualification_code", "QualificationCode")
    role = _pick(d, "JobRole", "JobRoleName", "job_role", "CourseName", "QualificationName", "course_name")
    sector = _pick(d, "Sector", "SectorName", "sector")
    scheme = _pick(d, "Scheme", "SchemeName", "Program", "Programme", "scheme")
    state = _pick(d, "State", "StateName", "state")
    district = _pick(d, "District", "DistrictName", "district")
    address = _pick(d, "Address", "CentreAddress", "CenterAddress", "address")
    start = _pick(d, "StartDate", "BatchStartDate", "batch_start_date")
    end = _pick(d, "EndDate", "BatchEndDate", "batch_end_date")
    timing_raw = _pick(d, "BatchTiming", "Timing", "batch_timing", "Shift")
    timing = _format_batch_timing(timing_raw)
    capacity = _int(_pick(d, "BatchSize", "Capacity", "BatchCapacity", "TotalSeats", "SeatCapacity", "capacity"))
    seats = _int(_pick(d, "SeatsAvailable", "AvailableSeats", "VacantSeats", "RemainingSeats", "seats_available"))
    raw_status = _pick(d, "BatchStatus", "Status", "availability_status", "AvailabilityStatus", "BatchState")
    normalized = _normalize_status(raw_status, seats, str(end) if end else None, listed_live=listed_live)
    oid = _stable_id("batchobs", source, batch_id or "", centre_id or centre_name or "", qcode or role or "", start or "")
    return {
        "observation_id": oid,
        "batch_id": str(batch_id).strip() if batch_id is not None else None,
        "centre_id": str(centre_id).strip() if centre_id is not None else None,
        "centre_name": str(centre_name).strip() if centre_name is not None else None,
        "training_partner": str(partner).strip() if partner is not None else None,
        "qualification_code": str(qcode).strip() if qcode is not None else None,
        "job_role": str(role).strip() if role is not None else None,
        "sector": str(sector).strip() if sector is not None else None,
        "scheme": str(scheme).strip() if scheme is not None else None,
        "state": str(state).strip() if state is not None else None,
        "district": str(district).strip() if district is not None else None,
        "address": str(address).strip() if address is not None else None,
        "start_date": str(start).strip() if start is not None else None,
        "end_date": str(end).strip() if end is not None else None,
        "timing": str(timing).strip() if timing is not None else None,
        "capacity": capacity,
        "seats_available": seats,
        "raw_status": str(raw_status).strip() if raw_status is not None else None,
        "normalized_status": normalized,
        "source": source,
        "source_url": source_url,
        "fetched_at": fetched_at,
        "payload_json": json.dumps(d, ensure_ascii=False, separators=(",", ":"))[:30000],
    }


def import_live_batch_json(path: str | Path, *, source: str = "Skill India Digital captured response",
                           source_url: Optional[str] = None, db_path=None, replace_source: bool = False) -> dict:
    """Import an official batch-search JSON response without hard-coding one private endpoint.

    The parser understands common SIDH-style field names and recursively finds batch objects.
    It intentionally does not infer seat availability when the source does not provide it.
    """
    ensure_live_batch_schema(db_path)
    p = Path(path)
    obj = json.loads(p.read_text(encoding="utf-8-sig"))
    fetched_at = datetime.now(timezone.utc).isoformat()
    rows = []
    seen = set()
    # First handle the exact SIDH structure discovered from the live PMKVY batch-selection page.
    # Presence in this collection is positive current/future-batch evidence, even when Status=null.
    scheme_batch_details = None
    if isinstance(obj, dict):
        data = obj.get("Data")
        if isinstance(data, dict) and isinstance(data.get("SchemeBatchDetails"), list):
            scheme_batch_details = data.get("SchemeBatchDetails")
            for d in scheme_batch_details:
                if not isinstance(d, dict):
                    continue
                row = _canonical_row(d, source=source, source_url=source_url, fetched_at=fetched_at, listed_live=True)
                if row and row["observation_id"] not in seen:
                    seen.add(row["observation_id"])
                    rows.append(row)
    # Keep the generic recursive parser for other official response shapes.
    for d in _walk_dicts(obj):
        row = _canonical_row(d, source=source, source_url=source_url, fetched_at=fetched_at)
        if row and row["observation_id"] not in seen:
            seen.add(row["observation_id"])
            rows.append(row)
    with get_db_connection(db_path) as conn:
        if replace_source:
            conn.execute("DELETE FROM training_batch_observations WHERE source=?", (source,))
        for r in rows:
            conn.execute("""
            INSERT INTO training_batch_observations(
                observation_id,batch_id,centre_id,centre_name,training_partner,qualification_code,
                job_role,sector,scheme,state,district,address,start_date,end_date,timing,capacity,
                seats_available,raw_status,normalized_status,source,source_url,fetched_at,payload_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(observation_id) DO UPDATE SET
                batch_id=excluded.batch_id,centre_id=excluded.centre_id,centre_name=excluded.centre_name,
                training_partner=excluded.training_partner,qualification_code=excluded.qualification_code,
                job_role=excluded.job_role,sector=excluded.sector,scheme=excluded.scheme,state=excluded.state,
                district=excluded.district,address=excluded.address,start_date=excluded.start_date,end_date=excluded.end_date,
                timing=excluded.timing,capacity=excluded.capacity,seats_available=excluded.seats_available,
                raw_status=excluded.raw_status,normalized_status=excluded.normalized_status,source=excluded.source,
                source_url=excluded.source_url,fetched_at=excluded.fetched_at,payload_json=excluded.payload_json
            """, tuple(r[k] for k in (
                "observation_id","batch_id","centre_id","centre_name","training_partner","qualification_code",
                "job_role","sector","scheme","state","district","address","start_date","end_date","timing","capacity",
                "seats_available","raw_status","normalized_status","source","source_url","fetched_at","payload_json"
            )))
    return {
        "records_detected": len(rows),
        "records_imported": len(rows),
        "active_batches": sum(r["normalized_status"] == "VERIFIED_ACTIVE_BATCH" for r in rows),
        "status_unknown": sum(r["normalized_status"] == "VERIFIED_BATCH_STATUS_UNKNOWN" for r in rows),
        "with_seat_counts": sum(r["seats_available"] is not None for r in rows),
        "source": source,
        "fetched_at": fetched_at,
        "sidh_scheme_batch_details_detected": len(scheme_batch_details) if isinstance(scheme_batch_details, list) else None,
        "verified_empty_live_response": isinstance(scheme_batch_details, list) and len(scheme_batch_details) == 0,
    }


def live_batch_status(db_path=None) -> dict:
    ensure_live_batch_schema(db_path)
    with get_db_connection(db_path) as conn:
        r = conn.execute("""
        SELECT COUNT(*) n,
               SUM(CASE WHEN normalized_status='VERIFIED_ACTIVE_BATCH' THEN 1 ELSE 0 END) active,
               SUM(CASE WHEN normalized_status='VERIFIED_NO_ACTIVE_BATCH' THEN 1 ELSE 0 END) inactive,
               SUM(CASE WHEN normalized_status='VERIFIED_BATCH_STATUS_UNKNOWN' THEN 1 ELSE 0 END) unknown,
               SUM(CASE WHEN seats_available IS NOT NULL THEN 1 ELSE 0 END) seats_known,
               MAX(fetched_at) latest_fetched_at
        FROM training_batch_observations
        """).fetchone()
    n = int(r["n"] or 0)
    return {
        "batch_observations": n,
        "verified_active_batches": int(r["active"] or 0),
        "verified_no_active_batches": int(r["inactive"] or 0),
        "batch_status_unknown": int(r["unknown"] or 0),
        "seat_counts_known": int(r["seats_known"] or 0),
        "latest_fetched_at": r["latest_fetched_at"],
        "mode": "captured_official_live_response" if n else "no_live_batch_snapshot",
        "live_source_required": n == 0,
    }


def find_live_batches(*, qualification_code: Optional[str] = None, job_role: Optional[str] = None,
                      state: Optional[str] = None, district: Optional[str] = None,
                      active_only: bool = True, limit: int = 20, db_path=None) -> list[dict]:
    ensure_live_batch_schema(db_path)
    clauses, args = [], []
    if qualification_code:
        clauses.append("lower(trim(qualification_code))=lower(trim(?))")
        args.append(qualification_code)
    elif job_role:
        # multi-token AND matching is less noisy than one broad substring
        toks = [t for t in re.findall(r"[a-z0-9]+", job_role.casefold()) if len(t) >= 3]
        for t in toks[:6]:
            clauses.append("lower(COALESCE(job_role,'')) LIKE ?")
            args.append(f"%{t}%")
    if state:
        clauses.append("lower(trim(state))=lower(trim(?))")
        args.append(state)
    if district:
        clauses.append("lower(trim(district))=lower(trim(?))")
        args.append(district)
    if active_only:
        clauses.append("normalized_status='VERIFIED_ACTIVE_BATCH'")
    where = " AND ".join(clauses) if clauses else "1=1"
    args.append(max(1, min(int(limit), 100)))
    with get_db_connection(db_path) as conn:
        rows = conn.execute(f"""
        SELECT observation_id,batch_id,centre_id,centre_name,training_partner,qualification_code,
               job_role,sector,scheme,state,district,address,start_date,end_date,timing,capacity,
               seats_available,raw_status,normalized_status,source,source_url,fetched_at
        FROM training_batch_observations
        WHERE {where}
        ORDER BY fetched_at DESC, start_date DESC
        LIMIT ?
        """, args).fetchall()
    return [dict(r) for r in rows]
