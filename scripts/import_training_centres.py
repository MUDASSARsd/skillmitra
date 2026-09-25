from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backend.training.store import import_training_csv, training_data_status

p = argparse.ArgumentParser(description="Import verified training-centre/course-batch snapshot into SkillMitra cache")
p.add_argument("csv", help="Normalized CSV path")
args = p.parse_args()
print(json.dumps(import_training_csv(args.csv), indent=2))
print(json.dumps(training_data_status(), indent=2))
