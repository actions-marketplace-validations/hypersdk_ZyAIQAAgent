"""Zyvor citation-first technical knowledge QA agent."""

from __future__ import annotations


def knowledge_deps_available() -> bool:
    """Return True when optional [knowledge] extras are importable."""
    try:
        import langchain_qdrant  # noqa: F401
        import qdrant_client  # noqa: F401
        from langchain.agents import create_agent  # noqa: F401
    except ImportError:
        return False
    return True


def knowledge_configured() -> bool:
    """Return True when LLM credentials are present for answering."""
    if not knowledge_deps_available():
        return False
    try:
        from knowledge.config import get_settings

        return get_settings().has_llm_credentials()
    except Exception:
        return False
