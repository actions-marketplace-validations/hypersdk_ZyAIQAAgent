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

"""Unit tests for dashboard job parameter validation (orchestrator/dashboard/jobs.py)."""

from __future__ import annotations

import pytest

from orchestrator.dashboard.jobs import VALID_KINDS, _redact_params, _validate


def test_password_redacted_but_url_kept():
    red = _redact_params({"url": "https://x.io", "username": "admin", "password": "s3cret"})
    assert red["password"] == "***"
    assert red["username"] == "admin"
    assert red["url"] == "https://x.io"


def test_redact_leaves_empty_password_untouched():
    red = _redact_params({"password": ""})
    assert red["password"] == ""  # nothing to hide


def test_redact_does_not_mutate_original():
    orig = {"password": "s3cret"}
    _redact_params(orig)
    assert orig["password"] == "s3cret"


def test_redact_bearer_token_and_api_key():
    red = _redact_params({"url": "https://x.io", "token": "eyJhbGci...", "apiKey": "sk-123"})
    assert red["token"] == "***" and red["apiKey"] == "***"
    assert red["url"] == "https://x.io"


def test_redact_nested_auth_secrets():
    red = _redact_params({"url": "https://x.io", "auth": {"token": "eyJ...", "header": "x-api-key", "apiKey": "k"}})
    assert red["auth"]["token"] == "***"
    assert red["auth"]["apiKey"] == "***"
    assert red["auth"]["header"] == "x-api-key"  # non-secret preserved


def test_flow_and_route_sweep_registered():
    assert "flow" in VALID_KINDS
    assert "route_sweep" in VALID_KINDS


def test_flow_requires_url_scheme():
    with pytest.raises(ValueError):
        _validate("flow", {"url": "zyvor.dev", "description": "go to /"})


def test_flow_requires_description():
    with pytest.raises(ValueError):
        _validate("flow", {"url": "https://zyvor.dev", "description": "  "})


def test_flow_clean_defaults():
    clean = _validate("flow", {"url": "https://zyvor.dev", "description": "go to /"})
    # TargetPolicy normalizes empty path to "/"
    assert clean["url"] in {"https://zyvor.dev", "https://zyvor.dev/"}
    assert clean["record"] is True  # default on
    assert clean["steps_mode"] is False
    assert clean["insecure"] is False


def test_flow_record_toggle_off():
    clean = _validate("flow", {"url": "https://x.io", "description": "go to /", "record": False})
    assert clean["record"] is False


def test_route_sweep_routes_filtered_and_defaulted():
    clean = _validate("route_sweep", {"url": "https://x.io", "routes": "/, /a, bad, /b"})
    assert clean["routes"] == ["/", "/a", "/b"]
    # empty → defaults to root
    clean2 = _validate("route_sweep", {"url": "https://x.io", "routes": "nothing-valid"})
    assert clean2["routes"] == ["/"]


def test_route_sweep_viewports_whitelist():
    clean = _validate("route_sweep", {"url": "https://x.io", "viewports": ["desktop", "mobile", "watch"]})
    assert clean["viewports"] == ["desktop", "mobile"]


def test_route_sweep_auto_and_max_pages():
    clean = _validate("route_sweep", {"url": "https://x.io", "auto": True, "max_pages": 999})
    assert clean["auto"] is True
    assert clean["max_pages"] == 40  # clamped


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        _validate("not_a_real_kind", {})


def test_new_kinds_registered():
    for k in ("api_contract", "auth_test", "realtime", "vitals", "har_replay", "import_codegen"):
        assert k in VALID_KINDS


def test_har_replay_requires_url_and_mode():
    with pytest.raises(ValueError):
        _validate("har_replay", {"url": "not-a-url", "mode": "record"})
    with pytest.raises(ValueError):
        _validate("har_replay", {"url": "https://x.io", "mode": "replay"})  # no har
    clean = _validate("har_replay", {"url": "https://x.io", "mode": "record", "routes": "/,/a"})
    assert clean["mode"] == "record"
    assert clean["routes"] == ["/", "/a"]


def test_import_codegen_requires_script():
    with pytest.raises(ValueError):
        _validate("import_codegen", {"script": "  "})
    clean = _validate("import_codegen", {"script": "await page.goto('/');"})
    assert clean["run"] is False
    with pytest.raises(ValueError):
        _validate("import_codegen", {"script": "await page.goto('/');", "run": True})


def test_smoke_shard_and_grep():
    clean = _validate("smoke", {"grep": "@smoke", "shard": "1/2"})
    assert clean["grep"] == "@smoke"
    assert clean["shard"] == "1/2"
    with pytest.raises(ValueError):
        _validate("smoke", {"shard": "bad"})


def test_api_contract_requires_spec_in_spec_mode():
    with pytest.raises(ValueError):
        _validate("api_contract", {"url": "https://api.x.io", "mode": "spec"})


def test_api_contract_requires_workflow_in_workflow_mode():
    with pytest.raises(ValueError):
        _validate("api_contract", {"url": "https://api.x.io", "mode": "workflow"})


def test_api_contract_clean_spec():
    clean = _validate("api_contract", {"url": "https://api.x.io", "mode": "spec", "spec": "https://api.x.io/openapi.json"})
    assert clean["mode"] == "spec"
    assert clean["spec"] == "https://api.x.io/openapi.json"
    assert clean["max_endpoints"] == 60


def test_api_contract_max_endpoints_clamped():
    clean = _validate("api_contract", {"url": "https://api.x.io", "mode": "spec",
                                        "spec": {"paths": {}}, "max_endpoints": 9999})
    assert clean["max_endpoints"] == 200


def test_vitals_requires_url_scheme():
    with pytest.raises(ValueError):
        _validate("vitals", {"url": "x.io"})


def test_vitals_throttle_whitelist():
    assert _validate("vitals", {"url": "https://x.io", "throttle": "3g"})["throttle"] == "3g"
    assert _validate("vitals", {"url": "https://x.io", "throttle": "bogus"})["throttle"] == ""


def test_auth_test_requires_a_login_method():
    with pytest.raises(ValueError):
        _validate("auth_test", {"url": "https://x.io"})
    ok = _validate("auth_test", {"url": "https://x.io", "api_login": "https://x.io/api/login"})
    assert ok["api_login"].endswith("/login")


def test_realtime_requires_a_target():
    with pytest.raises(ValueError):
        _validate("realtime", {"url": "https://x.io"})
    ok = _validate("realtime", {"url": "https://x.io", "ws": "/ws/flows", "expect_messages": 3})
    assert ok["ws"] == "/ws/flows" and ok["expect_messages"] == 3
