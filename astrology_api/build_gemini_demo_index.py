"""
build_gemini_demo_index.py — 用3本书构建 Gemini demo FAISS 索引，支持断点续跑。

选书：
  1. KeyWordsforAstrology          — 行星/星座关键词
  2. TheArtofChartInterpretation   — 本命盘综合解读
  3. AspectsandPersonality         — 相位与性格

输出：
  data/gemini_demo_index/index.faiss
  data/gemini_demo_index/chunks.json
  data/gemini_demo_index/progress.json   (运行中，完成后自动删除)
"""

import os
import json
import time
import pathlib
import numpy as np
import faiss
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# ── 配置 ────────────────────────────────────────────────────────
TEXTS_DIR   = pathlib.Path("data/processed_texts")
INDEX_DIR   = pathlib.Path("data/gemini_demo_index")
CHUNK_SIZE  = 600
OVERLAP     = 100
BATCH_SIZE  = 50
EMBED_MODEL = "gemini-embedding-001"

DEMO_FILES = [
    "[EN]KeyWordsforAstrology(HajoBanzhaf,AnnaHaebler).txt",
    "[EN]TheArtofChartInterpretation(3rdedrevised)(TracyMarks).txt",
    "[EN]AspectsandPersonality(KarenHamaker-Zondag).txt",
]

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("请在 .env 中设置 GOOGLE_API_KEY")

client = genai.Client(api_key=GOOGLE_API_KEY)
INDEX_DIR.mkdir(parents=True, exist_ok=True)

PROGRESS_FILE = INDEX_DIR / "progress.json"
CHUNKS_FILE   = INDEX_DIR / "chunks.json"
VECTORS_FILE  = INDEX_DIR / "vectors.npy"
INDEX_FILE    = INDEX_DIR / "index.faiss"


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


def load_demo_chunks() -> list[dict]:
    all_chunks = []
    for filename in DEMO_FILES:
        f = TEXTS_DIR / filename
        if not f.exists():
            print(f"  [警告] 文件不存在，跳过: {filename}")
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_text(text, filename)
        print(f"  {filename[:50]}... → {len(chunks)} 块")
        all_chunks.extend(chunks)
    print(f"Demo 总计 {len(all_chunks)} 块")
    return all_chunks


# ── 嵌入（带重试 + 断点续跑）────────────────────────────────────

def embed_batch_with_retry(texts: list[str]) -> list[list[float]]:
    for attempt in range(2):
        try:
            response = client.models.embed_content(
                model=EMBED_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
            )
            return [e.values for e in response.embeddings]
        except Exception as e:
            if attempt == 0:
                print(f"\n  请求失败 ({e.__class__.__name__})，等待 60 秒后重试...")
                time.sleep(60)
            else:
                raise


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"completed_batches": 0, "total_vectors": 0}


def save_progress(completed_batches: int, total_vectors: int):
    PROGRESS_FILE.write_text(json.dumps({
        "completed_batches": completed_batches,
        "total_vectors": total_vectors,
    }))


def embed_all(chunks: list[dict]) -> np.ndarray:
    progress = load_progress()
    start_batch = progress["completed_batches"]
    texts = [c["text"] for c in chunks]
    total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE

    if start_batch > 0 and VECTORS_FILE.exists():
        all_vectors = list(np.load(str(VECTORS_FILE)))
        print(f"续跑：已完成 {start_batch}/{total_batches} 批，跳过 {len(all_vectors)} 块")
    else:
        all_vectors = []

    for batch_idx in range(start_batch, total_batches):
        i = batch_idx * BATCH_SIZE
        batch = texts[i : i + BATCH_SIZE]
        print(f"  批次 {batch_idx+1}/{total_batches}（{len(batch)} 块）...", end=" ", flush=True)

        vectors = embed_batch_with_retry(batch)
        all_vectors.extend(vectors)
        print("ok")

        np.save(str(VECTORS_FILE), np.array(all_vectors, dtype=np.float32))
        save_progress(batch_idx + 1, len(all_vectors))

        if batch_idx + 1 < total_batches:
            time.sleep(1)

    return np.array(all_vectors, dtype=np.float32)


# ── 建 FAISS 索引 ─────────────────────────────────────────────────

def build_faiss(vectors: np.ndarray) -> faiss.Index:
    dim = vectors.shape[1]
    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    print(f"FAISS 索引构建完成，维度={dim}，共 {index.ntotal} 条")
    return index


# ── 主流程 ───────────────────────────────────────────────────────

def main():
    print("=== Step 1: 加载并分块 3 本 demo 书 ===")
    chunks = load_demo_chunks()

    if not CHUNKS_FILE.exists():
        with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False)
        print(f"chunks.json 已保存 ({len(chunks)} 块)")

    total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"\n=== Step 2: 生成嵌入向量（共 {total_batches} 批）===")

    vectors = embed_all(chunks)

    print("\n=== Step 3: 构建并保存 FAISS 索引 ===")
    index = build_faiss(vectors)
    faiss.write_index(index, str(INDEX_FILE))
    print(f"已保存 {INDEX_FILE}")

    if VECTORS_FILE.exists():
        VECTORS_FILE.unlink()
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()

    print("\nDemo 索引构建完成！")
    print(f"  索引文件: {INDEX_FILE}")
    print(f"  Chunks:   {CHUNKS_FILE}")


if __name__ == "__main__":
    main()
