"""
app/rag/__init__.py — 公共接口 re-export，保持所有调用方零改动
"""
from .client import (
    client,
    GENERATE_MODEL,
    set_thread_region,
    get_thread_region,
    get_last_model_used,
)
from .retrieval import retrieve, _load, _parse_json, _index_source
from .analytics import classify_query
from .prompts import (
    _SYSTEM_PROMPT_UNIFIED,
    _build_rag_section,
    _parse_answer_with_refs,
    _detect_citations,
    _clean_source_name,
)
from .chart_summary import (
    format_chart_summary,
    _SIGN_ELEMENT,
    _SIGN_MODALITY,
    _SIGN_RULER,
    _get_dignity,
)
from .chat import (
    generate,
    rag_query,
    rag_generate,
    chat_with_chart,
    summarize_messages,
    _build_contents,
)
from .transit import analyze_transits, analyze_active_transits_full
from .rectification import analyze_rectification, generate_asc_quiz, calc_confidence
from .solar_return import analyze_solar_return, _compute_sr_theme_scores
from .planets import analyze_planets, _compute_chart_facts
from .synastry import analyze_synastry

__all__ = [
    # client
    "client", "GENERATE_MODEL",
    "set_thread_region", "get_thread_region", "get_last_model_used",
    # retrieval
    "retrieve", "_load", "_parse_json", "_index_source",
    # analytics
    "classify_query",
    # prompts
    "_SYSTEM_PROMPT_UNIFIED", "_build_rag_section",
    "_parse_answer_with_refs", "_detect_citations", "_clean_source_name",
    # chart_summary
    "format_chart_summary", "_SIGN_ELEMENT", "_SIGN_MODALITY", "_SIGN_RULER", "_get_dignity",
    # chat
    "generate", "rag_query", "rag_generate",
    "chat_with_chart", "summarize_messages", "_build_contents",
    # analysis modules
    "analyze_transits", "analyze_active_transits_full",
    "analyze_rectification", "generate_asc_quiz", "calc_confidence",
    "analyze_solar_return", "_compute_sr_theme_scores",
    "analyze_planets", "_compute_chart_facts",
    "analyze_synastry",
]
