"""Tests for the autonomous AI tester (agents/aiflow/engine.py) + ai_flow validation."""

from __future__ import annotations

import pytest

from agents.aiflow.engine import _goal_specs, heuristic_decider, llm_decider


def _obs(elements, step=1, texts=None):
    return {"step": step, "url": "/vms/new", "title": "", "elements": elements, "texts": texts or []}


def _el(i, role, name, enabled=True, value=""):
    return {"i": i, "role": role, "name": name, "enabled": enabled, "value": value}


# ── goal parsing ──
def test_goal_specs_extracts_os_cpu_mem():
    s = _goal_specs("create a ubuntu vm with 1 vcpu and 2gb ram")
    assert s["os"] == "ubuntu" and s["cpu"] == "1" and s["mem"] == "2"


def test_goal_specs_variants():
    assert _goal_specs("2 cpus 8 Gi fedora")["cpu"] == "2"
    assert _goal_specs("windows server 4 cores 16gb")["os"] == "windows"
    assert _goal_specs("just a plain goal")["os"] is None


# ── heuristic decisions ──
def test_heuristic_opens_wizard_first():
    obs = _obs([_el(0, "button", "Create VM"), _el(1, "a", "Docs")])
    act = heuristic_decider("create a ubuntu vm", obs, [])
    assert act["action"] == "click" and act["i"] == 0


def test_heuristic_fills_name():
    obs = _obs([_el(0, "input:text", "my-vm name")])
    act = heuristic_decider("create a ubuntu vm", obs, ["click 3 (open wizard via 'New VM')"])
    assert act["action"] == "fill" and act["i"] == 0 and "ubuntu" in act["value"]


def test_heuristic_never_fills_a_checkbox():
    # a checkbox whose label contains "ram" must not be chosen as the memory field
    obs = _obs([_el(0, "input:checkbox", "keep ram reserved"), _el(1, "button", "Next")])
    act = heuristic_decider("create a ubuntu vm 2gb ram", obs, ["fill 9 (set the name)", "click 5 (open wizard via new)"])
    assert not (act["action"] == "fill" and act["i"] == 0)


def test_heuristic_picks_os_template():
    obs = _obs([_el(0, "button", "Ubuntu 24.04"), _el(1, "button", "Fedora 40")])
    act = heuristic_decider("create a ubuntu vm", obs, ["click 2 (open wizard via new)", "fill 4 (set the name)"])
    assert act["action"] == "click" and act["i"] == 0


def test_heuristic_advances_then_submits():
    nxt = _obs([_el(0, "button", "Next")])
    act = heuristic_decider("create a ubuntu vm", nxt, ["click 2 (open wizard via new)", "fill 4 (set the name)"])
    assert act["action"] == "click" and act["i"] == 0  # Next
    review = _obs([_el(0, "button", "Create VM")], step=7)
    act2 = heuristic_decider("create a ubuntu vm", review, ["click 2 (open wizard via new)", "fill 4 (set name)", "click 8 (next)"])
    assert act2["action"] == "click"


# ── LLM decider parses the model's JSON (mocked) ──
class _FakeResp:
    def __init__(self, content):
        self.content = content


class _FakeLLM:
    def __init__(self, content):
        self._c = content

    def invoke(self, _messages):
        return _FakeResp(self._c)


def _patch_llm(monkeypatch, content):
    from agents.common import llm as llm_mod

    monkeypatch.setattr(llm_mod, "get_llm", lambda: _FakeLLM(content))
    monkeypatch.setattr(llm_mod, "load_prompt", lambda _n: "system")


def test_llm_decider_parses_plain_json(monkeypatch):
    _patch_llm(monkeypatch, '{"action":"click","i":3,"reason":"open wizard"}')
    act = llm_decider("goal", _obs([_el(3, "button", "Create VM")]), [])
    assert act["action"] == "click" and act["i"] == 3


def test_llm_decider_parses_fenced_json(monkeypatch):
    _patch_llm(monkeypatch, 'Here you go:\n```json\n{"action":"done","success":true,"summary":"ok"}\n```')
    act = llm_decider("goal", _obs([]), [])
    assert act["action"] == "done" and act["success"] is True


# ── job validation ──
def test_ai_flow_validation():
    from orchestrator.dashboard.jobs import VALID_KINDS, _validate

    assert "ai_flow" in VALID_KINDS
    with pytest.raises(ValueError):
        _validate("ai_flow", {"url": "https://x.io"})  # missing goal
    clean = _validate("ai_flow", {"url": "https://x.io", "goal": "create a vm", "max_steps": 999})
    assert clean["goal"] == "create a vm" and clean["max_steps"] == 40  # clamped
