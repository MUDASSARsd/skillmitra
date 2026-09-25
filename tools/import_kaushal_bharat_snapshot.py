import json
from pathlib import Path
from backend.database.db import DEFAULT_DB_PATH
from backend.training.directory import upsert_directory_centres
p = Path(__file__).resolve().parent / 'data' / 'kaushal_bharat_telangana_snapshot.json'
records = json.loads(p.read_text(encoding='utf-8'))
print(upsert_directory_centres(records, db_path=DEFAULT_DB_PATH))
