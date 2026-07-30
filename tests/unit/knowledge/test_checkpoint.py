"""Checkpoint helper tests (offline)."""

from __future__ import annotations

from pathlib import Path

import pytest

from knowledge.checkpoint import clear_checkpointer_cache, get_checkpointer
from knowledge.config import clear_settings_cache


def test_memory_checkpointer_when_path_is_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KNOWLEDGE_CHECKPOINT_PATH", ":memory:")
    clear_settings_cache()
    clear_checkpointer_cache()
    saver = get_checkpointer()
    assert saver.__class__.__name__ == "InMemorySaver"
    clear_checkpointer_cache()
    clear_settings_cache()


def test_sqlite_checkpointer_when_package_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pytest.importorskip("langgraph.checkpoint.sqlite")
    db = tmp_path / "checkpoints.sqlite"
    monkeypatch.setenv("KNOWLEDGE_CHECKPOINT_PATH", str(db))
    clear_settings_cache()
    clear_checkpointer_cache()
    saver = get_checkpointer()
    assert saver.__class__.__name__ == "SqliteSaver"
    assert db.exists()
    clear_checkpointer_cache()
    clear_settings_cache()
