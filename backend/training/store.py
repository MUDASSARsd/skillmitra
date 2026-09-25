from __future__ import annotations
import csv
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from backend.database.db import get_db_connection
from backend.training.models import TrainingCentre, TrainingOffering, TrainingOption


def _norm(v: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (v or "").strip()).casefold()


def _as_float(v):
    if v is None or str(v).strip() == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(_norm(x) for x in parts)
    return f"{prefix}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def ensure_training_schema(db_path=None):
    with get_db_connection(db_path) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(training_centres)").fetchall()}
        wanted = {
            "pincode": "TEXT", "source": "TEXT", "source_url": "TEXT",
            "verification_status": "TEXT DEFAULT 'UNVERIFIED'", "last_verified_at": "TEXT",
        }
        for name, ddl in wanted.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE training_centres ADD COLUMN {name} {ddl}")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS training_offerings (
                offering_id TEXT PRIMARY KEY,
                centre_id TEXT NOT NULL,
                qualification_code TEXT,
                job_role TEXT,
                sector TEXT,
                scheme TEXT,
                batch_id TEXT,
                delivery_mode TEXT,
                batch_start_date TEXT,
                batch_end_date TEXT,
                batch_timing TEXT,
                availability_status TEXT DEFAULT 'UNKNOWN',
                source TEXT,
                source_url TEXT,
                last_verified_at TEXT,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(centre_id) REFERENCES training_centres(centre_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tc_location ON training_centres(state, district)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_to_code ON training_offerings(qualification_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_to_centre ON training_offerings(centre_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_to_job_role ON training_offerings(job_role)")


def import_training_csv(path: str | Path, db_path=None) -> dict:
    """Import a normalized centre/batch CSV while preserving provenance.

    Required: centre_name. Strongly recommended: state,district and either
    qualification_code or job_role. Rows are upserted, so refreshed official
    snapshots can safely replace stale availability metadata.
    """
    ensure_training_schema(db_path)
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    now = datetime.now(timezone.utc).isoformat()
    centres, offerings = 0, 0
    with p.open("r", encoding="utf-8-sig", newline="") as fh, get_db_connection(db_path) as conn:
        reader = csv.DictReader(fh)
        for row in reader:
            name = (row.get("centre_name") or "").strip()
            if not name:
                continue
            state, district = (row.get("state") or "").strip(), (row.get("district") or "").strip()
            centre_id = (row.get("centre_id") or "").strip() or _stable_id("tc", name, district, state, row.get("address") or "")
            source = (row.get("source") or "official_snapshot").strip()
            verified = (row.get("verification_status") or "OFFICIAL_SOURCE").strip()
            last_verified = (row.get("last_verified_at") or now).strip()
            conn.execute("""
                INSERT INTO training_centres(
                    centre_id, centre_name, state, district, address, latitude, longitude,
                    qualification_code, training_partner, scheme, status,
                    pincode, source, source_url, verification_status, last_verified_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(centre_id) DO UPDATE SET
                    centre_name=excluded.centre_name, state=excluded.state, district=excluded.district,
                    address=excluded.address, latitude=excluded.latitude, longitude=excluded.longitude,
                    training_partner=excluded.training_partner, pincode=excluded.pincode,
                    source=excluded.source, source_url=excluded.source_url,
                    verification_status=excluded.verification_status, last_verified_at=excluded.last_verified_at
            """, (
                centre_id, name, state or None, district or None, (row.get("address") or "").strip() or None,
                _as_float(row.get("latitude")), _as_float(row.get("longitude")),
                (row.get("qualification_code") or "").strip() or None,
                (row.get("training_partner") or "").strip() or None,
                (row.get("scheme") or "").strip() or None,
                (row.get("centre_status") or "").strip() or None,
                (row.get("pincode") or "").strip() or None, source,
                (row.get("source_url") or "").strip() or None, verified, last_verified,
            ))
            centres += 1
            qcode = (row.get("qualification_code") or "").strip()
            role = (row.get("job_role") or "").strip()
            batch = (row.get("batch_id") or "").strip()
            if qcode or role or batch:
                oid = (row.get("offering_id") or "").strip() or _stable_id("off", centre_id, qcode, role, batch, row.get("scheme") or "")
                conn.execute("""
                    INSERT INTO training_offerings(
                        offering_id, centre_id, qualification_code, job_role, sector, scheme,
                        batch_id, delivery_mode, batch_start_date, batch_end_date, batch_timing,
                        availability_status, source, source_url, last_verified_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(offering_id) DO UPDATE SET
                        qualification_code=excluded.qualification_code, job_role=excluded.job_role,
                        sector=excluded.sector, scheme=excluded.scheme, batch_id=excluded.batch_id,
                        delivery_mode=excluded.delivery_mode, batch_start_date=excluded.batch_start_date,
                        batch_end_date=excluded.batch_end_date, batch_timing=excluded.batch_timing,
                        availability_status=excluded.availability_status, source=excluded.source,
                        source_url=excluded.source_url, last_verified_at=excluded.last_verified_at
                """, (
                    oid, centre_id, qcode or None, role or None, (row.get("sector") or "").strip() or None,
                    (row.get("scheme") or "").strip() or None, batch or None,
                    (row.get("delivery_mode") or "").strip() or None,
                    (row.get("batch_start_date") or "").strip() or None,
                    (row.get("batch_end_date") or "").strip() or None,
                    (row.get("batch_timing") or "").strip() or None,
                    (row.get("availability_status") or "UNKNOWN").strip().upper(), source,
                    (row.get("source_url") or "").strip() or None, last_verified,
                ))
                offerings += 1
    return {"rows_processed": centres, "offerings_upserted": offerings}


def _currentness(last_verified_at: Optional[str]) -> str:
    if not last_verified_at:
        return "UNKNOWN"
    try:
        d = datetime.fromisoformat(last_verified_at.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - d.astimezone(timezone.utc)).days
        return "CURRENT" if age <= 30 else ("RECENT" if age <= 90 else "STALE")
    except Exception:
        return "UNKNOWN"


def find_training_options(*, qualification_code: Optional[str] = None, job_role: Optional[str] = None,
                          state: Optional[str] = None, district: Optional[str] = None,
                          limit: int = 20, db_path=None) -> list[TrainingOption]:
    ensure_training_schema(db_path)
    clauses, args = [], []
    if qualification_code:
        clauses.append("lower(trim(o.qualification_code)) = lower(trim(?))")
        args.append(qualification_code)
    elif job_role:
        clauses.append("lower(o.job_role) LIKE ?")
        args.append(f"%{_norm(job_role)}%")
    if state:
        clauses.append("lower(trim(c.state)) = lower(trim(?))")
        args.append(state)
    if district:
        clauses.append("lower(trim(c.district)) = lower(trim(?))")
        args.append(district)
    where = " AND ".join(clauses) if clauses else "1=1"
    sql = f"""
        SELECT
          c.centre_id AS c_centre_id, c.centre_name AS c_centre_name, c.training_partner AS c_training_partner,
          c.state AS c_state, c.district AS c_district, c.address AS c_address, c.pincode AS c_pincode,
          c.latitude AS c_latitude, c.longitude AS c_longitude, c.source AS c_source, c.source_url AS c_source_url,
          c.verification_status AS c_verification_status, c.last_verified_at AS c_last_verified_at,
          o.offering_id AS o_offering_id, o.centre_id AS o_centre_id, o.qualification_code AS o_qualification_code,
          o.job_role AS o_job_role, o.sector AS o_sector, o.scheme AS o_scheme, o.batch_id AS o_batch_id,
          o.delivery_mode AS o_delivery_mode, o.batch_start_date AS o_batch_start_date, o.batch_end_date AS o_batch_end_date,
          o.batch_timing AS o_batch_timing, o.availability_status AS o_availability_status, o.source AS o_source,
          o.source_url AS o_source_url, o.last_verified_at AS o_last_verified_at
        FROM training_offerings o
        JOIN training_centres c ON c.centre_id=o.centre_id
        WHERE {where}
        ORDER BY
          CASE WHEN upper(o.availability_status) IN ('OPEN','AVAILABLE','ACTIVE') THEN 0 ELSE 1 END,
          c.centre_name
        LIMIT ?
    """
    args.append(max(1, min(int(limit), 100)))
    out = []
    with get_db_connection(db_path) as conn:
        rows = conn.execute(sql, args).fetchall()
        for r in rows:
            d = dict(r)
            centre = TrainingCentre(
                centre_id=d["c_centre_id"], centre_name=d["c_centre_name"], training_partner=d["c_training_partner"],
                state=d["c_state"], district=d["c_district"], address=d["c_address"], pincode=d["c_pincode"],
                latitude=d["c_latitude"], longitude=d["c_longitude"], source=d["c_source"], source_url=d["c_source_url"],
                verification_status=d["c_verification_status"] or "UNVERIFIED", last_verified_at=d["c_last_verified_at"],
            )
            offering = TrainingOffering(
                offering_id=d["o_offering_id"], centre_id=d["o_centre_id"], qualification_code=d["o_qualification_code"],
                job_role=d["o_job_role"], sector=d["o_sector"], scheme=d["o_scheme"], batch_id=d["o_batch_id"],
                delivery_mode=d["o_delivery_mode"], batch_start_date=d["o_batch_start_date"], batch_end_date=d["o_batch_end_date"],
                batch_timing=d["o_batch_timing"], availability_status=d["o_availability_status"] or "UNKNOWN",
                source=d["o_source"], source_url=d["o_source_url"], last_verified_at=d["o_last_verified_at"],
            )
            if district and _norm(centre.district) == _norm(district):
                lm = "DISTRICT"
            elif state and _norm(centre.state) == _norm(state):
                lm = "STATE"
            else:
                lm = "UNFILTERED"
            out.append(TrainingOption(centre=centre, offering=offering, location_match=lm,
                                      currentness=_currentness(offering.last_verified_at)))
    return out


def training_data_status(db_path=None) -> dict:
    ensure_training_schema(db_path)
    # V21 distinguishes verified directory presence from qualification/batch offerings.
    # A centre appearing in an official directory must never be reported as an active batch.
    try:
        from backend.training.directory import ensure_directory_schema
        ensure_directory_schema(db_path)
    except Exception:
        pass
    with get_db_connection(db_path) as conn:
        c = conn.execute("SELECT COUNT(*) FROM training_centres").fetchone()[0]
        verified_directory = conn.execute("SELECT COUNT(*) FROM training_centres WHERE verification_status='OFFICIAL_DIRECTORY'").fetchone()[0]
        o = conn.execute("SELECT COUNT(*) FROM training_offerings").fetchone()[0]
        open_count = conn.execute("SELECT COUNT(*) FROM training_offerings WHERE upper(availability_status) IN ('OPEN','AVAILABLE','ACTIVE','VERIFIED_ACTIVE_BATCH')").fetchone()[0]
        latest_offering = conn.execute("SELECT MAX(last_verified_at) FROM training_offerings").fetchone()[0]
        latest_centre = conn.execute("SELECT MAX(last_verified_at) FROM training_centres").fetchone()[0]
    return {
        "training_centres": c,
        "verified_directory_centres": verified_directory,
        "offerings": o,
        "open_or_active_offerings": open_count,
        "latest_verified_at": latest_offering or latest_centre,
        "mode": "hybrid_verified_directory_plus_batch_cache",
        "batch_truth": "Only training_offerings with explicit batch evidence can be active; directory centres are batch-unknown.",
    }
