from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from backend.courses.store import import_skill_india_json, course_data_status
p=argparse.ArgumentParser(description='Import a captured Skill India course-list JSON response')
p.add_argument('json_file')
a=p.parse_args()
print(json.dumps(import_skill_india_json(a.json_file),indent=2,ensure_ascii=False))
print(json.dumps(course_data_status(),indent=2,ensure_ascii=False))
