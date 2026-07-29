"""Install enterprise controls into the existing FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI, Request

from orchestrator.dashboard.durable_jobs import get_service
from orchestrator.dashboard.v2_routes import router as v2_router
from orchestrator.security.config import validate_runtime_security


def install_enterprise(app: FastAPI) -> None:
    validate_runtime_security()
    app.include_router(v2_router)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'",
        )
        return response

    @app.on_event("startup")
    async def _start_enterprise_services() -> None:
        get_service().start()

    @app.on_event("shutdown")
    async def _stop_enterprise_services() -> None:
        get_service().stop()
