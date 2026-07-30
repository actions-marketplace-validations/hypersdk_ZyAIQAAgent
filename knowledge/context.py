from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str
    access_levels: tuple[str, ...]
    product: str | None = None
    document_type: str | None = None


_context: ContextVar[RequestContext | None] = ContextVar("qa_request_context", default=None)


def current_context() -> RequestContext:
    value = _context.get()
    if value is None:
        raise RuntimeError("Request context is not configured")
    return value


@contextmanager
def request_context(context: RequestContext) -> Iterator[None]:
    token = _context.set(context)
    try:
        yield
    finally:
        _context.reset(token)
