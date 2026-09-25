from pathlib import Path
from backend.schemes.store import import_scheme_snapshot

base=Path(__file__).resolve().parent
print(import_scheme_snapshot(base/'data'/'government_schemes_official_snapshot.json'))
