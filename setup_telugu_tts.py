"""One-time installer for SkillMitra's offline Telugu Piper voice."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "models" / "piper-te"
MODEL = DEST / "te_IN-padmavathi-medium.onnx"
CONFIG = DEST / "te_IN-padmavathi-medium.onnx.json"
BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/te/te_IN/padmavathi/medium"
FILES = {
    MODEL: (f"{BASE}/{MODEL.name}?download=true", 63516050, "1a7fb140ecc8b5e8b3e80e460b719319"),
    CONFIG: (f"{BASE}/{CONFIG.name}?download=true", 4974, "3f07441340aecc2a8b89987361e8078e"),
}


def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def valid(path: Path, size: int, checksum: str) -> bool:
    return path.is_file() and path.stat().st_size == size and md5(path) == checksum


def download(url: str, path: Path, size: int, checksum: str):
    if valid(path, size, checksum):
        print(f"OK: {path.name} already verified")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".download")
    tmp.unlink(missing_ok=True)
    print(f"Downloading {path.name} ...")

    def progress(blocks, block_size, total):
        if total > 0:
            pct = min(100, int(blocks * block_size * 100 / total))
            print(f"\r  {pct:3d}%", end="", flush=True)

    urllib.request.urlretrieve(url, tmp, reporthook=progress)
    print()
    if not valid(tmp, size, checksum):
        got_size = tmp.stat().st_size if tmp.exists() else 0
        got_hash = md5(tmp) if tmp.exists() else "missing"
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"Downloaded file verification failed for {path.name}. size={got_size}, md5={got_hash}"
        )
    os.replace(tmp, path)
    print(f"Verified: {path.name}")


def ensure_piper():
    try:
        import piper  # noqa: F401
        print("OK: piper-tts is already installed")
        return
    except Exception:
        pass
    print("Installing piper-tts into this Python environment ...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "piper-tts"])


def verify_runtime():
    # Import only after installation.
    from piper import PiperVoice
    print("Loading Telugu voice for a final runtime check ...")
    PiperVoice.load(str(MODEL), config_path=str(CONFIG))
    print("OK: Telugu Piper voice loaded successfully")


def main():
    print("SkillMitra Offline Telugu TTS Setup")
    print(f"Python: {sys.executable}")
    ensure_piper()
    for path, (url, size, checksum) in FILES.items():
        download(url, path, size, checksum)
    verify_runtime()
    print("\nREADY: Offline Telugu TTS is installed.")
    print("Restart START_HYBRID.bat, then check: http://127.0.0.1:8000/tts/offline/status")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nSETUP FAILED: {exc}")
        print("Check internet access, then run SETUP_TELUGU_TTS.bat again.")
        sys.exit(1)
