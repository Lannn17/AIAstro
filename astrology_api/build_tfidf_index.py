"""
build_local_index.py — 纯本地方案，无需 API，无 DLL 依赖。

用 TF-IDF + SVD (LSA) 生成 384 维密集向量，存入 FAISS。
依赖：scikit-learn + faiss-cpu（均已在 requirements.txt 中）

输出:
  data/local_index/index.faiss
  data/local_index/chunks.json
  data/local_index/vectorizer.pkl   (TF-IDF + SVD 模型，查询时复用)
"""

import json
import pickle
import pathlib
import numpy as np
import faiss
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import Normalizer

TEXTS_DIR  = pathlib.Path("data/processed_texts")
INDEX_DIR  = pathlib.Path("data/local_index")
CHUNK_SIZE = 600
OVERLAP    = 100
N_DIMS     = 384   # SVD降维后的维度
SKIP       = {"exemplo_interpretacoes.txt"}

INDEX_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_FILE     = INDEX_DIR / "chunks.json"
INDEX_FILE      = INDEX_DIR / "index.faiss"
VECTORIZER_FILE = INDEX_DIR / "vectorizer.pkl"


# ── 分块 ────────────────────────────────────────────────────────

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
        print(f"  {f.name[:55]}: {len(chunks)} chunks")
    print(f"Total: {len(all_chunks)} chunks")
    return all_chunks


# ── 主流程 ───────────────────────────────────────────────────────

def main():
    print("=== Step 1: Loading and chunking all books ===")
    chunks = load_all_chunks()

    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)
    print(f"chunks.json saved ({len(chunks)} chunks)")

    print(f"\n=== Step 2: Building TF-IDF + SVD pipeline (dims={N_DIMS}) ===")
    texts = [c["text"] for c in chunks]

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=50000,
            sublinear_tf=True,
            min_df=2,
        )),
        ("svd",  TruncatedSVD(n_components=N_DIMS, random_state=42)),
        ("norm", Normalizer(norm="l2")),
    ])

    print("Fitting pipeline (may take 1-2 minutes)...")
    vectors = pipeline.fit_transform(texts).astype(np.float32)
    print(f"Vectors shape: {vectors.shape}")

    with open(VECTORIZER_FILE, "wb") as f:
        pickle.dump(pipeline, f)
    print(f"Pipeline saved: {VECTORIZER_FILE}")

    print(f"\n=== Step 3: Building FAISS index ===")
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    faiss.write_index(index, str(INDEX_FILE))

    print(f"\nDone! dim={dim}, total={index.ntotal}")
    print(f"  Index:      {INDEX_FILE}")
    print(f"  Chunks:     {CHUNKS_FILE}")
    print(f"  Vectorizer: {VECTORIZER_FILE}")


if __name__ == "__main__":
    main()
