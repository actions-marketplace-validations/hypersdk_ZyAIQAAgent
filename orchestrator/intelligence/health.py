# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""Suite-level health: wrap history.test_health() with classification and
quarantine state. Does not replace the existing /api/dashboard/tests endpoint.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from orchestrator.intelligence.classify import classify_history
from orchestrator.intelligence.quarantine import is_quarantined, listing, prune_expired


def summarize(*, limit: int = 40, root: Path | None = None) -> dict[str, Any]:
    from orchestrator.dashboard import history

    prune_expired(root=root)
    rows = history.test_health(limit=max(limit, 40))
    enriched = []
    counts = {"healthy": 0, "failing": 0, "flaky": 0, "other": 0}
    for rec in rows:
        # history.test_health does not keep the raw status stream; reconstruct
        # a coarse one from runs/fails so classify_history still works.
        fails = int(rec.get("fails") or 0)
        runs = int(rec.get("runs") or 0)
        passes = max(runs - fails, 0)
        statuses = (["failed"] * fails) + (["passed"] * passes)
        classified = classify_history(statuses)
        title = rec.get("title") or ""
        q = is_quarantined(title, "", root=root)
        verdict = classified["verdict"]
        if verdict in counts:
            counts[verdict] += 1
        else:
            counts["other"] += 1
        enriched.append(
            {
                **rec,
                "verdict": verdict,
                "recommend_quarantine": classified["recommend_quarantine"],
                "quarantined": bool(q),
                "quarantine": q,
            }
        )
    active = listing(root=root)
    return {
        "tests": enriched[:limit],
        "counts": counts,
        "quarantined_count": len(active),
        "quarantine": active,
    }
