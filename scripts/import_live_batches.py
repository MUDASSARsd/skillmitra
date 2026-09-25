from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backend.database.db import DEFAULT_DB_PATH
from backend.training.live_batches import import_live_batch_json


def main():
    p = argparse.ArgumentParser(description="Import captured official Skill India/live batch JSON")
    p.add_argument("json_file")
    p.add_argument("--source", default="Skill India Digital captured response")
    p.add_argument("--source-url", default=None)
    p.add_argument("--replace-source", action="store_true")
    args = p.parse_args()
    out = import_live_batch_json(args.json_file, source=args.source, source_url=args.source_url,
                                 db_path=DEFAULT_DB_PATH, replace_source=args.replace_source)
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
