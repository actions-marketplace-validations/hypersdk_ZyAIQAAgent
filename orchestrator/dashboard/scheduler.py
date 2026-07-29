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

"""Durable recurring-job scheduler.

This replaces the in-memory scheduler while preserving its public API.
"""

from __future__ import annotations

from typing import Any

from orchestrator.dashboard.durable_jobs import get_service
from orchestrator.persistence.store import get_store


def add(kind: str, params: dict[str, Any], interval_s: int) -> dict[str, Any]:
    entry = get_store().add_schedule(kind, params, interval_s, requested_by="legacy-dashboard")
    get_service().start()
    return entry


def remove(sid: str) -> bool:
    return get_store().remove_schedule(sid)


def listing() -> list[dict[str, Any]]:
    return get_store().list_schedules()


def _ensure_thread() -> None:
    get_service().start()
