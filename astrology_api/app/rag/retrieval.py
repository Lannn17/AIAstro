"""
app/rag/retrieval.py — Qdrant 检索 + E5 embedding
"""
import os
import re
import json

from dotenv import load_dotenv

load_dotenv()

QDRANT_URL     = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
if not QDRANT_URL or not QDRANT_API_KEY:
    raise RuntimeError("请在 .env 中设置 QDRANT_URL 和 QDRANT_API_KEY")

from .client import _local

COLLECTION_NAME = "astro_chunks"
E5_MODEL        = "intfloat/multilingual-e5-small"
E5_PREFIX       = "query: "
_index_source   = "qdrant"

_qdrant   = None
_e5_model = None


def _load():
    global _qdrant, _e5_model
    if _qdrant is not None:
        return
    from qdrant_client import QdrantClient
    from sentence_transformers import SentenceTransformer
    _qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=30)
    _e5_model = SentenceTransformer(E5_MODEL)
    print(f"[RAG] Qdrant connected, e5 model loaded")


def retrieve(query: str, k: int = 5) -> list[dict]:
    """
    向量检索，返回 top-k 相关 chunks。
    每条结果格式: {text, source, start, score}
    """
    _load()

    query_vec = _e5_model.encode(
        [E5_PREFIX + query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )[0].tolist()

    response = _qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=k,
        with_payload=True,
    )

    results = []
    for hit in response.points:
        p = hit.payload or {}
        results.append({
            "text":   p.get("text", ""),
            "source": p.get("source", ""),
            "start":  p.get("start", 0),
            "score":  round(float(hit.score), 4),
        })

    # 暂存供 _ModelsWithFallback 日志读取
    _local.pending_rag_query = query
    _local.pending_rag_chunks = results

    return results


def _parse_json(text: str) -> dict | list:
    """Strip optional markdown code fences then parse JSON."""
    text = text.strip()
    text = re.sub(r'^```[a-z]*\s*', '', text)
    text = re.sub(r'\s*```$', '', text.strip())
    return json.loads(text.strip())
