"""
build_gemini_index.py — 把 data/processed_texts/ 里的书切块、向量化，存成 FAISS 索引。
支持断点续跑：中断后重新运行会从上次进度继续。

用法：
    cd astrology_api
    python build_gemini_index.py

输出：
    data/gemini_index/index.faiss   — 向量索引
    data/gemini_index/chunks.json   — 文本块 + 来源元数据
    data/gemini_index/progress.json — 进度存档（断点续跑用）
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
INDEX_DIR   = pathlib.Path("data/gemini_index")
CHUNK_SIZE  = 600
OVERLAP     = 100
BATCH_SIZE  = 50
EMBED_MODEL = "gemini-embedding-2-preview"

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


def load_all_chunks() -> list[dict]:
    all_chunks = []
    files = sorted(TEXTS_DIR.glob("*.txt"))
    skip = {"exemplo_interpretacoes.txt"}
    print(f"找到 {len(files)} 个文本文件")
    for f in files:
        if f.name in skip:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
            chunks = chunk_text(text, f.name)
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"  跳过 {f.name}: {e}")
    print(f"总计 {len(all_chunks)} 块")
    return all_chunks


# ── 嵌入（带重试 + 断点续跑）────────────────────────────────────

def embed_batch_with_retry(texts: list[str]) -> list[list[float]]:
    """调用 Gemini 嵌入，失败等 60 秒后重试一次（避免 SDK 内部重试叠加消耗 RPD）。"""
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
                print(f"\n  ⏳ 请求失败，等待 60 秒后重试...")
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

    # 加载已有向量
    if start_batch > 0 and VECTORS_FILE.exists():
        all_vectors = list(np.load(str(VECTORS_FILE)))
        print(f"▶ 续跑：已完成 {start_batch}/{total_batches} 批，跳过 {len(all_vectors)} 块")
    else:
        all_vectors = []

    for batch_idx in range(start_batch, total_batches):
        i = batch_idx * BATCH_SIZE
        batch = texts[i : i + BATCH_SIZE]
        print(f"  批次 {batch_idx+1}/{total_batches}（{len(batch)} 块）...", end=" ", flush=True)

        vectors = embed_batch_with_retry(batch)
        all_vectors.extend(vectors)
        print("✓")

        # 每批保存一次进度
        np.save(str(VECTORS_FILE), np.array(all_vectors, dtype=np.float32))
        save_progress(batch_idx + 1, len(all_vectors))

        # 速率控制：每批后等 2 秒（≈30 RPM，远低于 100 RPM 上限）
        if batch_idx + 1 < total_batches:
            time.sleep(2)

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
    print("=== 第1步：加载并分块文本 ===")
    chunks = load_all_chunks()

    # 保存 chunks（只在第一次或块数变化时重写）
    if not CHUNKS_FILE.exists():
        with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False)
        print(f"chunks.json 已保存")

    print("\n=== 第2步：生成嵌入向量（断点续跑）===")
    total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE
    est_minutes = total_batches * 32 / 60
    print(f"预计总时间：约 {est_minutes:.0f} 分钟（速率限制下）\n")

    vectors = embed_all(chunks)

    print("\n=== 第3步：构建并保存 FAISS 索引 ===")
    index = build_faiss(vectors)
    faiss.write_index(index, str(INDEX_FILE))
    print(f"已保存 {INDEX_FILE}")

    # 清理临时文件
    if VECTORS_FILE.exists():
        VECTORS_FILE.unlink()
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()

    print("\n✓ 全部完成！")


if __name__ == "__main__":
    main()
