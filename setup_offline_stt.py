"""One-time project-local multilingual microphone setup.

Downloads the Systran faster-whisper-small multilingual model into the project.
The older tiny model remains an emergency fallback, but base is preferred for Indic accuracy.
No .env file is read or modified.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "models" / "faster-whisper-small"


def main():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_bin = MODEL_DIR / "model.bin"
    if not model_bin.is_file():
        print(f"Downloading jury-quality multilingual microphone model to: {MODEL_DIR}")
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id="Systran/faster-whisper-small",
            local_dir=str(MODEL_DIR),
        )
    else:
        print("Quality multilingual microphone model already exists.")

    from faster_whisper import WhisperModel
    print("Validating local microphone model...")
    WhisperModel(str(MODEL_DIR), device="cpu", compute_type="int8", cpu_threads=2, num_workers=1)
    print("Jury-quality multilingual offline microphone is ready.")


if __name__ == "__main__":
    main()
