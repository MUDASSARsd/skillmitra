"""Download project-local Indic-first Offline ASR packs.

Default Indic jury pack: Hindi, Telugu and Tamil; English uses project-local Whisper Small.
Use --all to add every Indian language exposed by the UI.
No .env file is read or modified.
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL_ROOT = ROOT / "models" / "indicconformer-sherpa-onnx"
REPO_ID = "parismitaglobalsolutions/indicconformer-sherpa-onnx"
CORE = ["en", "hi", "te", "ta", "hinglish"]
ALL_UI = ["en", "hi", "te", "ta", "kn", "ml", "mr", "bn", "gu", "pa", "or", "hinglish"]


def _download_file(filename: str) -> Path:
    from huggingface_hub import hf_hub_download
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    path = hf_hub_download(
        repo_id=REPO_ID,
        filename=filename,
        local_dir=str(MODEL_ROOT),
    )
    return Path(path)


def ensure_language(lang: str) -> None:
    if lang == "en":
        required = ["en/model.int8.onnx", "en/tokens.txt"]
    elif lang == "hinglish":
        required = [
            "hi-hinglish-swift/encoder.int8.onnx",
            "hi-hinglish-swift/decoder.int8.onnx",
            "hi-hinglish-swift/tokens.txt",
        ]
    else:
        required = ["tokens.txt", f"{lang}/model.int8.onnx"]
    for filename in required:
        target = MODEL_ROOT / filename
        if target.is_file() and target.stat().st_size > 1024:
            print(f"  [ok] {filename}")
        else:
            print(f"  [download] {filename}")
            _download_file(filename)


def validate(languages: list[str]) -> None:
    import sherpa_onnx
    for lang in languages:
        print(f"  [validate] {lang}")
        if lang == "hinglish":
            d = MODEL_ROOT / "hi-hinglish-swift"
            sherpa_onnx.OfflineRecognizer.from_whisper(
                encoder=str(d / "encoder.int8.onnx"),
                decoder=str(d / "decoder.int8.onnx"),
                tokens=str(d / "tokens.txt"),
                num_threads=2,
                decoding_method="greedy_search",
                language="hi",
                task="transcribe",
            )
        else:
            if lang == "en":
                model = MODEL_ROOT / "en" / "model.int8.onnx"
                tokens = MODEL_ROOT / "en" / "tokens.txt"
            else:
                model = MODEL_ROOT / lang / "model.int8.onnx"
                tokens = MODEL_ROOT / "tokens.txt"
            sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
                model=str(model),
                tokens=str(tokens),
                num_threads=2,
                decoding_method="greedy_search",
            )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="download every UI Indian-language pack")
    ap.add_argument("--languages", nargs="*", help="explicit language codes")
    args = ap.parse_args()
    languages = args.languages or (ALL_UI if args.all else CORE)
    languages = list(dict.fromkeys(languages))
    bad = [x for x in languages if x not in ALL_UI]
    if bad:
        raise SystemExit(f"Unsupported setup language(s): {', '.join(bad)}")
    print("Indic-first Offline ASR pack:", ", ".join(languages))
    print("Models are stored only inside:", MODEL_ROOT)
    for lang in languages:
        ensure_language(lang)
    validate(languages)
    print("Indic-first Offline ASR is ready for:", ", ".join(languages))


if __name__ == "__main__":
    main()
