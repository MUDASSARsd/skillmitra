"""Import harvested eligibility_routes.csv into SkillMitra SQLite without rebuilding qualifications."""
from pathlib import Path
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.data.eligibility_loader import load_eligibility_routes

DB = ROOT / "data" / "nqr_database.db"
CSV = ROOT / "eligibility_routes.csv"
REPORT = ROOT / "data" / "eligibility_import_report.json"

if __name__ == "__main__":
    conn = sqlite3.connect(DB)
    try:
        metrics = load_eligibility_routes(CSV, conn)
    finally:
        conn.close()
    REPORT.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print(f"Saved: {REPORT}")
