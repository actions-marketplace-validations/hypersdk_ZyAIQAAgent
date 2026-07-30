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

"""Dashboard knowledge proxy smoke tests (no Qdrant/LLM required)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from orchestrator.webhook import create_app


def test_knowledge_status_reports_unavailable_without_extras() -> None:
    client = TestClient(create_app())
    response = client.get("/api/dashboard/knowledge/status")
    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload
    assert "deps_installed" in payload


def test_knowledge_suggestions_are_non_empty() -> None:
    client = TestClient(create_app())
    response = client.get("/api/dashboard/knowledge/suggestions")
    assert response.status_code == 200
    assert len(response.json()["suggestions"]) >= 1


def test_ask_without_extras_returns_501() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/dashboard/ask",
        json={"question": "How does PacketWolf egress work?"},
    )
    # 501 when extras missing; 503 if extras present but unconfigured.
    assert response.status_code in {501, 503}
    assert "detail" in response.json()
