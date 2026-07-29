"""Recursive secret redaction for API responses, logs, schedules and audit data."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

REDACTED = "***"

_SECRET_KEY_RE = re.compile(
    r"(?:^|[_\-.])(?:"
    r"password|passwd|pwd|token|access[_-]?token|refresh[_-]?token|"
    r"api[_-]?key|apikey|secret|client[_-]?secret|authorization|"
    r"cookie|session|private[_-]?key|bearer|credential|credentials"
    r")(?:$|[_\-.])",
    re.IGNORECASE,
)

_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_GITHUB_TOKEN_RE = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")
_GENERIC_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|token|api[_-]?key|secret)\s*[:=]\s*([^\s,;]+)"
)


def is_secret_key(key: object) -> bool:
    return bool(_SECRET_KEY_RE.search(str(key)))


def redact_text(value: str) -> str:
    """Redact common token formats that may appear inside free-form strings."""
    value = _BEARER_RE.sub("Bearer ***", value)
    value = _JWT_RE.sub(REDACTED, value)
    value = _GITHUB_TOKEN_RE.sub(REDACTED, value)
    value = _GENERIC_ASSIGNMENT_RE.sub(lambda m: f"{m.group(1)}={REDACTED}", value)
    return value


def redact(value: Any, *, max_depth: int = 20, _depth: int = 0) -> Any:
    """Return a deep redacted copy.

    Handles nested dictionaries, lists, tuples, sets and strings. Unknown objects
    are returned unchanged so callers may still serialize their normal models.
    """
    if _depth > max_depth:
        return "<max-depth>"
    if isinstance(value, Mapping):
        out: dict[Any, Any] = {}
        for key, item in value.items():
            out[key] = REDACTED if is_secret_key(key) and item not in (None, "", [], {}) else redact(
                item, max_depth=max_depth, _depth=_depth + 1
            )
        return out
    if isinstance(value, tuple):
        return tuple(redact(v, max_depth=max_depth, _depth=_depth + 1) for v in value)
    if isinstance(value, set):
        return {redact(v, max_depth=max_depth, _depth=_depth + 1) for v in value}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact(v, max_depth=max_depth, _depth=_depth + 1) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
