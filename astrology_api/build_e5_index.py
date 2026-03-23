"""
build_e5_index.py — Build FAISS index using intfloat/multilingual-e5-small.

Better retrieval quality than MiniLM: trained explicitly for query→document
retrieval. Requires "passage: " prefix on documents and "query: " on queries.
Supports 100+ languages including Chinese, English, Portuguese.

Output:
  data/e5_index/index.faiss
  data/e5_index/chunks.json
  data/e5_index/model_info.json

Usage:
    cd astrology_api
    python build_e5_index.py
"""

import json
import pathlib
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

TEXTS_DIR  = pathlib.Path("data/processed_texts")
INDEX_DIR  = pathlib.Path("data/e5_index")
CHUNK_SIZE = 600
OVERLAP    = 100
SKIP       = {"exemplo_interpretacoes.txt"}
MODEL_NAME = "intfloat/multilingual-e5-small"
BATCH_SIZE = 32
SAVE_EVERY = 50

INDEX_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_FILE     = INDEX_DIR / "chunks.json"
INDEX_FILE      = INDEX_DIR / "index.faiss"
MODEL_INFO_FILE = INDEX_DIR / "model_info.json"
VECTORS_FILE    = INDEX_DIR / "vectors.npy"
PROGRESS_FILE   = INDEX_DIR / "progress.json"


def chunk_text(text: str, source: str) -> list[dict]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end].strip()
        if chunk:
            chunks.append({"text": chunk, "source": source, "start": start})
        start += CHUNK_SIZE - OVERLAP
    return chunks


def load_all_chunks() -> list[dict]:
    all_chunks = []
    files = sorted(TEXTS_DIR.glob("*.txt"))
    print(f"Found {len(files)} text files")
    for f in files:
        if f.name in SKIP:
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_text(text, f.name)
        all_chunks.extend(chunks)
        print(f"  {f.name[:60].encode('ascii', errors='replace').decode()}: {len(chunks)} chunks")
    print(f"\nTotal: {len(all_chunks)} chunks")
    return all_chunks


def main():
    print("=== Step 1: Loading and chunking all books ===")
    chunks = load_all_chunks()

    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)
    print(f"chunks.json saved ({len(chunks)} chunks)")

    print(f"\n=== Step 2: Loading model: {MODEL_NAME} ===")
    print("(First run: auto-downloading model ~120MB)")
    model = SentenceTransformer(MODEL_NAME)

    print(f"\n=== Step 3: Generating embeddings (batch_size={BATCH_SIZE}) ===")
    # e5 requires "passage: " prefix for documents
    texts = [f"passage: {c['text']}" for c in chunks]
    total = len(texts)
    total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

    # Resume support
    start_batch = 0
    all_vectors = []
    if PROGRESS_FILE.exists() and VECTORS_FILE.exists():
        prog = json.loads(PROGRESS_FILE.read_text())
        start_batch = prog["completed_batches"]
        all_vectors = list(np.load(str(VECTORS_FILE)))
        print(f"Resuming from batch {start_batch}/{total_batches} ({len(all_vectors)} vectors done)")

    for i in range(start_batch, total_batches):
        batch_texts = texts[i * BATCH_SIZE : (i + 1) * BATCH_SIZE]
        batch_vecs = model.encode(
            batch_texts,
            batch_size=BATCH_SIZE,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype(np.float32)
        all_vectors.extend(batch_vecs)
        print(f"  Batch {i+1}/{total_batches} ({len(all_vectors)}/{total})", end="\r")

        if (i + 1) % SAVE_EVERY == 0 or i + 1 == total_batches:
            np.save(str(VECTORS_FILE), np.array(all_vectors, dtype=np.float32))
            PROGRESS_FILE.write_text(json.dumps({"completed_batches": i + 1}))

    vectors = np.array(all_vectors, dtype=np.float32)
    print(f"\nDone: {vectors.shape}")

    print(f"\n=== Step 4: Building FAISS IndexFlatIP ===")
    # Vectors already normalized — inner product == cosine similarity
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    faiss.write_index(index, str(INDEX_FILE))
    print(f"Index saved: {INDEX_FILE}  (dim={dim}, total={index.ntotal})")

    with open(MODEL_INFO_FILE, "w") as f:
        json.dump({"model": MODEL_NAME, "dim": dim, "total": index.ntotal, "prefix": "query: "}, f)

    if VECTORS_FILE.exists():
        VECTORS_FILE.unlink()
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()

    print("\nAll done!")


if __name__ == "__main__":
    main()
