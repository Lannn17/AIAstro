"""
app/prompt_log.py — Prompt 调用日志（内存环形缓冲）
"""

import time
import threading
import uuid
from dataclasses import dataclass, field, asdict
from collections import deque


@dataclass
class PromptLogEntry:
    """单次 Gemini 调用的完整记录"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)

    # 调用方
    caller: str = ""

    # 输入
    model: str = ""
    system_instruction: str = ""
    temperature: float = 0.0
    contents: list = field(default_factory=list)
    prompt_text: str = ""
    prompt_tokens_est: int = 0

    # RAG
    rag_query: str = ""
    rag_chunks: list = field(default_factory=list)

    # 输出
    model_used: str = ""
    response_text: str = ""
    finish_reason: str = ""
    response_tokens_est: int = 0
    latency_ms: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp_readable"] = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp)
        )
        return d


class PromptLogStore:
    """线程安全的内存环形缓冲，保留最近 N 条记录。"""

    def __init__(self, maxlen: int = 200):
        self._buffer: deque[PromptLogEntry] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def append(self, entry: PromptLogEntry):
        with self._lock:
            self._buffer.append(entry)

    def get_all(self, limit: int = 50) -> list[dict]:
        with self._lock:
            items = list(self._buffer)[-limit:]
        return [e.to_dict() for e in reversed(items)]

    def get_by_id(self, log_id: str) -> dict | None:
        with self._lock:
            for e in self._buffer:
                if e.id == log_id:
                    return e.to_dict()
        return None

    def get_by_caller(self, caller: str, limit: int = 20) -> list[dict]:
        with self._lock:
            items = [e for e in self._buffer if e.caller == caller][-limit:]
        return [e.to_dict() for e in reversed(items)]

    def clear(self):
        with self._lock:
            self._buffer.clear()


# 全局单例
prompt_store = PromptLogStore(maxlen=200)