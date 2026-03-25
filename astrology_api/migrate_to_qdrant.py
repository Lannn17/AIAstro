"""
migrate_to_qdrant.py — 把本地 e5_index 一次性迁移到 Qdrant Cloud

运行：
    venv/Scripts/python migrate_to_qdrant.py               # 续传模式
    venv/Scripts/python migrate_to_qdrant.py --force       # 删除旧 collection 重建
"""
import os, json, pathlib, sys
import numpy as np
import faiss
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

load_dotenv()

QDRANT_URL     = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
COLLECTION     = "astro_chunks"
BATCH_SIZE     = 200
FORCE_RECREATE = "--force" in sys.argv

if not QDRANT_URL or not QDRANT_API_KEY:
    raise RuntimeError("请在 .env 中设置 QDRANT_URL 和 QDRANT_API_KEY")

BASE      = pathlib.Path(__file__).parent / "data" / "e5_index"
IDX_FILE  = BASE / "index.faiss"
CHUNK_FILE = BASE / "chunks.json"

if not IDX_FILE.exists():
    raise RuntimeError(f"找不到 {IDX_FILE}，请确认 e5_index 目录存在")

print("=== Step 1: 连接 Qdrant Cloud ===")
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)
print(f"✅ 连接成功：{QDRANT_URL}")

print("\n=== Step 2: 加载本地索引 ===")
index = faiss.read_index(str(IDX_FILE))
with open(CHUNK_FILE, encoding="utf-8") as f:
    chunks = json.load(f)
dim = index.d
total = index.ntotal
print(f"✅ 向量维度: {dim}, 总数: {total}, chunks: {len(chunks)}")

print(f"\n=== Step 3: 创建 Qdrant Collection ({COLLECTION}) ===")
existing = [c.name for c in client.get_collections().collections]
if COLLECTION in existing:
    if FORCE_RECREATE:
        client.delete_collection(COLLECTION)
        print(f"🗑️  已删除旧 collection '{COLLECTION}'")
    else:
        print(f"⚠️  collection '{COLLECTION}' 已存在，续传模式（用 --force 强制重建）")

if COLLECTION not in existing or FORCE_RECREATE:
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    print(f"✅ Collection 创建成功")

# 检查已有向量数
info = client.get_collection(COLLECTION)
already_uploaded = info.points_count
print(f"   已有向量数: {already_uploaded}/{total}")

if already_uploaded >= total:
    print("✅ 已全部上传，无需重复操作")
    exit(0)

print(f"\n=== Step 4: 上传向量（续传：从 {already_uploaded} 开始）===")
# 从 FAISS 提取所有向量
all_vectors = np.zeros((total, dim), dtype=np.float32)
index.reconstruct_n(0, total, all_vectors)

uploaded = 0
start_from = already_uploaded  # 支持续传
batch_num = 0

for i in range(start_from, total, BATCH_SIZE):
    batch_end = min(i + BATCH_SIZE, total)
    points = []
    for j in range(i, batch_end):
        chunk = chunks[j] if j < len(chunks) else {}
        points.append(PointStruct(
            id=j,
            vector=all_vectors[j].tolist(),
            payload={
                "text":   chunk.get("text", ""),
                "source": chunk.get("source", ""),
                "start":  chunk.get("start", 0),
            }
        ))
    client.upsert(collection_name=COLLECTION, points=points)
    uploaded += len(points)
    batch_num += 1
    print(f"  批次 {batch_num}：上传 {batch_end}/{total} ({batch_end*100//total}%)")

print(f"\n✅ 迁移完成！共上传 {uploaded} 条向量到 Qdrant")
info = client.get_collection(COLLECTION)
print(f"   Qdrant 确认向量数: {info.points_count}")
