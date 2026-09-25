from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent
TTS = ROOT / "backend" / "tts_local.py"

if not TTS.is_file():
    raise SystemExit(
        "ERROR: backend/tts_local.py not found.\n"
        "Run this file from the SkillMitra project root.\n"
        f"Expected: {TTS}"
    )

src = TTS.read_text(encoding="utf-8")

english_block = (
    '    "en": {\n'
    '        "name": "en_US-lessac-medium.onnx",\n'
    '        "folder": "piper-en",\n'
    '        "model_env": "PIPER_ENGLISH_MODEL",\n'
    '        "config_env": "PIPER_ENGLISH_CONFIG",\n'
    '        "dir_env": "PIPER_ENGLISH_DIR",\n'
    '        "label": "English",\n'
    '    },\n'
)

if '"folder": "piper-en"' not in src:
    marker = "_PIPER_VOICES = {\n"
    if marker not in src:
        raise SystemExit("ERROR: Could not find _PIPER_VOICES in backend/tts_local.py")

    backup = TTS.with_suffix(".py.before_english_piper.bak")
    if not backup.exists():
        backup.write_text(src, encoding="utf-8")
        print("Backup:", backup)

    src = src.replace(marker, marker + english_block, 1)
    TTS.write_text(src, encoding="utf-8")
    print("PATCHED: English added to _PIPER_VOICES")
else:
    print("OK: English Piper configuration is already present")

try:
    import piper
    print("OK: piper-tts installed")
except Exception:
    print("Installing piper-tts...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "piper-tts"])

DEST = ROOT / "models" / "piper-en"
DEST.mkdir(parents=True, exist_ok=True)

BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/"
FILES = [
    ("en_US-lessac-medium.onnx", 60_000_000),
    ("en_US-lessac-medium.onnx.json", 1_000),
]

for name, min_size in FILES:
    path = DEST / name
    if path.is_file() and path.stat().st_size >= min_size:
        print(f"OK: {name} already present ({path.stat().st_size:,} bytes)")
        continue

    print(f"Downloading {name} ...")
    req = urllib.request.Request(
        BASE + name + "?download=true",
        headers={"User-Agent": "SkillMitra/1.0"},
    )
    with urllib.request.urlopen(req, timeout=180) as response, open(path, "wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)

    if path.stat().st_size < min_size:
        raise SystemExit(
            f"ERROR: {name} download looks incomplete ({path.stat().st_size:,} bytes). "
            "Delete it and run this setup again with internet ON."
        )
    print(f"DOWNLOADED: {name} ({path.stat().st_size:,} bytes)")

check = (
    "from backend.tts_local import LocalTTS; "
    "t=LocalTTS(); "
    "print('ENGLISH PIPER:', t._piper_ready('en')); "
    "print('ENGLISH STATUS:', t.status().languages.get('en')); "
    "print('ENGLISH VOICE:', t._voices.get('en'))"
)

print("\n--- VALIDATION ---")
subprocess.check_call([sys.executable, "-c", check], cwd=str(ROOT))

print("\nDONE.")
print("Now run STOP_SERVER.bat, then LAUNCH_APP.bat.")
