# Copyright 2026 Zyvor AI Labs · https://zyvor.dev
# SPDX-License-Identifier: Apache-2.0
"""Change-based test selection. Honest slice: git path heuristics +
requirement_test_links + quarantine exclusion. Not a coverage profiler
and not a full call-graph.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from orchestrator.intelligence.quarantine import is_quarantined, listing, test_key

_TEST_SUFFIXES = (".spec.ts", ".spec.js", ".test.ts", ".test.js", ".spec.py", ".test.py")
_PRODUCT_HINTS = (
    "app/",
    "src/",
    "web/",
    "frontend/",
    "backend/",
    "server/",
    "api/",
    "templates/",
    "playwright/",
)
_INFRA_HINTS = (
    "orchestrator/",
    "agents/",
    "docker/",
    "kubernetes/",
    "docs/",
    ".github/",
)


def changed_files(base: str = "HEAD~1", head: str = "HEAD", *, cwd: Path | None = None) -> list[str]:
    from orchestrator.paths import repo_root

    workdir = str(cwd or repo_root())
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...{head}"],
            cwd=workdir, capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        # Three-dot can fail on shallow clones / missing base — fall back to two-dot.
        proc = subprocess.run(
            ["git", "diff", "--name-only", base, head],
            cwd=workdir, capture_output=True, text=True, timeout=15,
        )
        if proc.returncode != 0:
            return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _is_test_path(path: str) -> bool:
    name = path.replace("\\", "/").lower()
    return name.endswith(_TEST_SUFFIXES) or "/tests/" in f"/{name}/" or name.startswith("playwright/")


def _looks_product(path: str) -> bool:
    name = path.replace("\\", "/")
    return any(name.startswith(hint) or f"/{hint}" in f"/{name}" for hint in _PRODUCT_HINTS)


def _looks_infra(path: str) -> bool:
    name = path.replace("\\", "/")
    return any(name.startswith(hint) for hint in _INFRA_HINTS) and not _is_test_path(name)


def select_tests(
    changed: list[str],
    *,
    linked_tests: list[str] | None = None,
    known_tests: list[dict[str, str]] | None = None,
    root: Path | None = None,
    include_quarantined: bool = False,
) -> dict[str, Any]:
    """Return the tests worth running for this change set.

    known_tests entries: {title, file}.
    linked_tests: requirement_test_links paths from the store.
    """
    changed = [p.replace("\\", "/") for p in changed if p]
    direct = sorted({p for p in changed if _is_test_path(p)})
    product = sorted({p for p in changed if _looks_product(p) and p not in direct})
    infra = sorted({p for p in changed if _looks_infra(p)})

    selected_files = set(direct)
    reasons: dict[str, str] = {p: "changed-test-file" for p in direct}

    for path in linked_tests or []:
        norm = path.replace("\\", "/")
        selected_files.add(norm)
        reasons.setdefault(norm, "requirement-link")

    # If product files changed but no tests were named, recommend the smoke
    # suite rather than inventing paths we don't have.
    fallback = ""
    if product and not selected_files:
        fallback = "@smoke"
        reasons["@smoke"] = "product-change-smoke-fallback"

    dropped_quarantine: list[dict[str, Any]] = []
    if not include_quarantined:
        for q in listing(root=root):
            qfile = (q.get("file") or "").replace("\\", "/")
            qtitle = q.get("title") or ""
            if qfile and qfile in selected_files:
                selected_files.discard(qfile)
                dropped_quarantine.append(q)
            elif qtitle and any(test_key(qtitle, "") == test_key(qtitle, p) for p in selected_files):
                dropped_quarantine.append(q)

    # known_tests is informational — used by callers that already have a catalog.
    _ = known_tests

    grep = _grep_for(sorted(selected_files), fallback)
    return {
        "changed": changed,
        "selected_files": sorted(selected_files),
        "reasons": reasons,
        "fallback": fallback,
        "infra_only": bool(infra) and not product and not direct and not (linked_tests or []),
        "dropped_quarantine": dropped_quarantine,
        "grep": grep,
        "run_recommended": bool(selected_files or fallback) and not (
            bool(infra) and not product and not direct and not (linked_tests or [])
        ),
    }


def _grep_for(files: list[str], fallback: str) -> str:
    if files:
        # Playwright --grep is a title regex; file selection is better as
        # a path list the runner already understands. We still emit a
        # grep of basenames so `argus test exec --grep` works.
        names = []
        for path in files:
            stem = Path(path).stem
            names.append(stem.replace(".spec", "").replace(".test", ""))
        unique = [n for n in dict.fromkeys(names) if n]
        if unique:
            return "|".join(unique[:20])
    return fallback


def select_from_git(
    *,
    base: str = "HEAD~1",
    head: str = "HEAD",
    linked_tests: list[str] | None = None,
    root: Path | None = None,
    include_quarantined: bool = False,
) -> dict[str, Any]:
    changed = changed_files(base, head, cwd=root)
    result = select_tests(
        changed,
        linked_tests=linked_tests,
        root=root,
        include_quarantined=include_quarantined,
    )
    result["base"] = base
    result["head"] = head
    return result
