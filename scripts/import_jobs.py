from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backend.jobs.store import import_jobs_json, jobs_data_status

p=argparse.ArgumentParser(description="Import a raw Skill India/NCS jobs JSON response into SkillMitra.")
p.add_argument("json_file", help="Saved browser/API response JSON")
a=p.parse_args()
print(json.dumps(import_jobs_json(a.json_file), indent=2))
print(json.dumps(jobs_data_status(), indent=2))
