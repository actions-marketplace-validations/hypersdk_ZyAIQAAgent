# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime, timedelta, timezone

import pytest

from orchestrator.intelligence import quarantine as q
from orchestrator.intelligence.quarantine import add, is_quarantined, listing, prune_expired, release


def test_add_list_release_round_trip(tmp_path):
    entry = add("login should work", file="playwright/login.spec.ts", reason="intermittent timeout", root=tmp_path)
    assert entry["status"] == "active"
    assert entry["key"] == q.test_key("login should work", "playwright/login.spec.ts")
    rows = listing(root=tmp_path)
    assert len(rows) == 1
    assert is_quarantined("login should work", "playwright/login.spec.ts", root=tmp_path)
    assert release(entry["key"], root=tmp_path) is True
    assert listing(root=tmp_path) == []
    assert is_quarantined("login should work", "playwright/login.spec.ts", root=tmp_path) is None


def test_add_requires_title_and_reason(tmp_path):
    with pytest.raises(ValueError, match="title"):
        add("", reason="flake", root=tmp_path)
    with pytest.raises(ValueError, match="reason"):
        add("login", reason="  ", root=tmp_path)


def test_expiry_is_pruned(tmp_path):
    add("flaky cart", reason="race", ttl_hours=1, root=tmp_path)
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    assert prune_expired(root=tmp_path, now=future) == 1
    assert listing(root=tmp_path) == []
    inactive = listing(root=tmp_path, include_inactive=True)
    assert inactive[0]["status"] == "expired"


def test_release_missing_is_false(tmp_path):
    assert release("does-not-exist", root=tmp_path) is False
