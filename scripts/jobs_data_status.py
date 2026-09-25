from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from backend.jobs.store import jobs_data_status
print(json.dumps(jobs_data_status(), indent=2))
