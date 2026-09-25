from pathlib import Path
from backend.database.db import DEFAULT_DB_PATH
from backend.training.directory import load_source_urls, sync_kaushal_bharat_urls

src = Path(__file__).resolve().parent / "data" / "kaushal_bharat_sources.json"
urls = load_source_urls(src)
result = sync_kaushal_bharat_urls(urls, db_path=DEFAULT_DB_PATH)
print(result)
