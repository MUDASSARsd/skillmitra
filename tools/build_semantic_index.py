"""One-time builder for the local multilingual NQR semantic index."""
from backend.mapping.semantic_retriever import SemanticNQRIndex


def progress(done, total):
    pct = 100.0 * done / max(total, 1)
    print(f"Embedding NQR catalogue: {done}/{total} ({pct:.1f}%)", flush=True)


if __name__ == "__main__":
    index = SemanticNQRIndex()
    print("Embedding model status:", index.embedder.status())
    result = index.build(progress=progress)
    print(result.as_dict())
