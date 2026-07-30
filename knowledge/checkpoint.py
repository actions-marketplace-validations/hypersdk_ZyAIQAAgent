"""Conversation checkpointer for the knowledge QA agent."""

from __future__ import annotations

import logging
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

from knowledge.config import get_settings

LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_checkpointer() -> Any:
    """Return a process-lifetime checkpointer (SQLite when configured, else memory)."""
    settings = get_settings()
    path = (settings.knowledge_checkpoint_path or "").strip()

    if not path or path == ":memory:":
        from langgraph.checkpoint.memory import InMemorySaver

        LOGGER.info("Knowledge checkpointer: InMemorySaver")
        return InMemorySaver()

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError:
        from langgraph.checkpoint.memory import InMemorySaver

        LOGGER.warning(
            "langgraph-checkpoint-sqlite not installed; falling back to InMemorySaver"
        )
        return InMemorySaver()

    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    LOGGER.info("Knowledge checkpointer: SqliteSaver (%s)", db_path)
    return saver


def clear_checkpointer_cache() -> None:
    get_checkpointer.cache_clear()
