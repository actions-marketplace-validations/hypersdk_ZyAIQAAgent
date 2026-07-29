# Copyright 2026 ZyvorAI Labs Private Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
