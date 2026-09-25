from __future__ import annotations
import json, sqlite3
from pathlib import Path
from typing import Any
from backend.database.db import DEFAULT_DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS government_schemes (
    scheme_code TEXT PRIMARY KEY,
    scheme_name TEXT NOT NULL,
    ministry TEXT,
    scheme_type TEXT,
    target_groups_json TEXT,
    benefits TEXT,
    application_method TEXT,
    official_url TEXT,
    source_title TEXT,
    source_url TEXT,
    source_checked_on TEXT,
    eligibility_json TEXT,
    notes TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_gov_schemes_type ON government_schemes(scheme_type);
"""


def ensure_scheme_schema(db_path=DEFAULT_DB_PATH):
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(SCHEMA)


def import_scheme_snapshot(snapshot_path: str | Path, db_path=DEFAULT_DB_PATH) -> dict:
    ensure_scheme_schema(db_path)
    payload = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    schemes = payload.get("schemes", payload if isinstance(payload, list) else [])
    with sqlite3.connect(str(db_path)) as conn:
        for s in schemes:
            conn.execute("""
                INSERT INTO government_schemes (
                    scheme_code,scheme_name,ministry,scheme_type,target_groups_json,benefits,
                    application_method,official_url,source_title,source_url,source_checked_on,
                    eligibility_json,notes
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(scheme_code) DO UPDATE SET
                    scheme_name=excluded.scheme_name,ministry=excluded.ministry,
                    scheme_type=excluded.scheme_type,target_groups_json=excluded.target_groups_json,
                    benefits=excluded.benefits,application_method=excluded.application_method,
                    official_url=excluded.official_url,source_title=excluded.source_title,
                    source_url=excluded.source_url,source_checked_on=excluded.source_checked_on,
                    eligibility_json=excluded.eligibility_json,notes=excluded.notes
            """, (
                s["scheme_code"], s["scheme_name"], s.get("ministry"), s.get("scheme_type"),
                json.dumps(s.get("target_groups", []), ensure_ascii=False), s.get("benefits"),
                s.get("application_method"), s.get("official_url"), s.get("source_title"),
                s.get("source_url"), s.get("source_checked_on"),
                json.dumps(s.get("eligibility", {}), ensure_ascii=False), s.get("notes")
            ))
        conn.commit()
    return scheme_data_status(db_path)


def list_schemes(db_path=DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    ensure_scheme_schema(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM government_schemes ORDER BY scheme_name").fetchall()
    out=[]
    for r in rows:
        d=dict(r)
        d["target_groups"] = json.loads(d.pop("target_groups_json") or "[]")
        d["eligibility"] = json.loads(d.pop("eligibility_json") or "{}")
        out.append(d)
    return out


def scheme_data_status(db_path=DEFAULT_DB_PATH) -> dict:
    ensure_scheme_schema(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        count=conn.execute("SELECT COUNT(*) FROM government_schemes").fetchone()[0]
        checked=conn.execute("SELECT MAX(source_checked_on) FROM government_schemes").fetchone()[0]
    return {"schemes": count, "latest_source_check": checked, "mode": "curated_official_snapshot"}
