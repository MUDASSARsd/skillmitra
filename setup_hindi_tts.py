from pathlib import Path
from urllib.request import Request, urlopen
import shutil

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "models" / "piper-hi"
OUT.mkdir(parents=True, exist_ok=True)

BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/pratham/medium/"
FILES = [
    "hi_IN-pratham-medium.onnx",
    "hi_IN-pratham-medium.onnx.json",
]

for name in FILES:
    dest = OUT / name
    if dest.is_file() and dest.stat().st_size > 1024:
        print(f"Already present: {dest}")
        continue
    print(f"Downloading {name}...")
    req = Request(BASE + name + "?download=true", headers={"User-Agent": "JeevikaMitra/1.0"})
    with urlopen(req, timeout=120) as response, open(dest, "wb") as f:
        shutil.copyfileobj(response, f)
    print(f"Saved: {dest}")

print("Hindi Piper voice setup complete.")
