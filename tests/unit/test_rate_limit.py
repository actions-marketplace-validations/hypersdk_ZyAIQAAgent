# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest

from orchestrator.security import rate_limit


@pytest.fixture(autouse=True)
def _clean_rate_limit_state():
    rate_limit.reset()
    yield
    rate_limit.reset()


def test_allows_requests_under_the_limit(monkeypatch):
    monkeypatch.setenv("ZYVOR_API_RATE_LIMIT", "3")
    monkeypatch.setenv("ZYVOR_API_RATE_WINDOW_S", "60")

    for _ in range(3):
        assert rate_limit.check("1.2.3.4") == 0


def test_blocks_once_the_limit_is_exceeded(monkeypatch):
    monkeypatch.setenv("ZYVOR_API_RATE_LIMIT", "2")
    monkeypatch.setenv("ZYVOR_API_RATE_WINDOW_S", "60")

    assert rate_limit.check("1.2.3.4") == 0
    assert rate_limit.check("1.2.3.4") == 0
    wait = rate_limit.check("1.2.3.4")
    assert wait > 0


def test_keys_are_independent(monkeypatch):
    monkeypatch.setenv("ZYVOR_API_RATE_LIMIT", "1")
    monkeypatch.setenv("ZYVOR_API_RATE_WINDOW_S", "60")

    assert rate_limit.check("1.2.3.4") == 0
    assert rate_limit.check("1.2.3.4") > 0
    # A different key has its own budget.
    assert rate_limit.check("5.6.7.8") == 0


def test_check_trims_a_stale_entry_inline_even_when_prune_is_skipped(monkeypatch):
    """check()'s own per-key trim (separate from the periodic _prune sweep)
    must still drop a stale leading entry on a call that arrives too soon
    after the last prune to trigger a fresh sweep."""
    monkeypatch.setenv("ZYVOR_API_RATE_LIMIT", "5")
    monkeypatch.setenv("ZYVOR_API_RATE_WINDOW_S", "60")
    times = iter([1000.0, 1000.5])
    monkeypatch.setattr(rate_limit.time, "time", lambda: next(times))

    assert rate_limit.check("1.2.3.4") == 0  # establishes _last_prune = 1000.0
    # Age this key's only hit well past the window without advancing real
    # time enough for the next call to re-trigger the periodic sweep.
    rate_limit._hits["1.2.3.4"][0] = 1000.0 - 61
    assert rate_limit.check("1.2.3.4") == 0


def test_window_expiry_allows_requests_again(monkeypatch):
    monkeypatch.setenv("ZYVOR_API_RATE_LIMIT", "1")
    monkeypatch.setenv("ZYVOR_API_RATE_WINDOW_S", "60")

    times = iter([1000.0, 1000.0, 1061.0])
    monkeypatch.setattr(rate_limit.time, "time", lambda: next(times))

    assert rate_limit.check("1.2.3.4") == 0
    assert rate_limit.check("1.2.3.4") > 0
    assert rate_limit.check("1.2.3.4") == 0
