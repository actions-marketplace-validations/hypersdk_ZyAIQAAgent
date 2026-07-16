"""Turn a journey (English prose or one-step-per-line) into flow steps."""

from __future__ import annotations

import json
import re
from typing import Any


def _step(action: str, target: str = "", value: str = "", assertion: str = "") -> dict[str, Any]:
    return {"action": action, "target": target, "value": value, "assertion": assertion}


# ── explicit step lines: `click "Create VM"`, `fill name = test`, `assert "running"` ──
def parse_step_lines(text: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^(?:goto|go\s+to|open|navigate)\s+(?:to\s+)?(\S+)", line, re.I)
        if m:
            steps.append(_step("goto", m.group(1).strip("\"'")))
            continue
        m = re.match(r"^click\s+[\"']?(.+?)[\"']?$", line, re.I)
        if m:
            steps.append(_step("click", m.group(1).strip()))
            continue
        m = re.match(r"^(?:fill|type|enter)\s+(.+?)\s*[=:]\s*[\"']?(.+?)[\"']?$", line, re.I)
        if m:
            steps.append(_step("fill", m.group(1).strip(), m.group(2).strip()))
            continue
        m = re.match(r"^press\s+(.+)$", line, re.I)
        if m:
            steps.append(_step("press", value=m.group(1).strip()))
            continue
        m = re.match(r"^wait\s+(?:for\s+)?(.+)$", line, re.I)
        if m:
            arg = m.group(1).strip()
            steps.append(_step("wait", value=arg) if arg.replace("ms", "").isdigit() else _step("wait", arg))
            continue
        m = re.match(r"^(?:assert|verify|expect|check)\s+[\"']?(.+?)[\"']?$", line, re.I)
        if m:
            steps.append(_step("assert", assertion=m.group(1).strip()))
            continue
        # bare line → treat as an assertion of visible text
        steps.append(_step("assert", assertion=line.strip("\"'")))
    return steps


# ── heuristic prose → steps (no LLM) ──
def parse_prose_heuristic(text: str) -> list[dict[str, Any]]:
    # split into clauses on sentence/comma/"then"/"and"
    clauses = re.split(r"[.;\n,]|\s+then\s+|\s+and\s+", text, flags=re.I)
    steps: list[dict[str, Any]] = []
    for clause in clauses:
        c = clause.strip()
        if not c:
            continue
        low = c.lower()
        pm = re.search(r"(/[a-z0-9][a-z0-9\-/]*)", c, re.I)
        if re.search(r"\b(go to|open|navigate|visit)\b", low) and pm:
            steps.append(_step("goto", pm.group(1)))
        elif re.search(r"\blog ?in|sign ?in\b", low):
            steps.append(_step("goto", "/"))
        elif re.search(r"\bclick|press the|tap\b", low):
            q = re.search(r"[\"'“]([^\"'”]+)[\"'”]", c) or re.search(r"(?:click|tap)(?:\s+the|\s+on)?\s+([A-Z][\w ]+?)(?:\s+button|\s+link)?$", c, re.I)
            steps.append(_step("click", (q.group(1) if q else c).strip()))
        elif re.search(r"\b(fill|type|enter|input)\b", low):
            q = re.search(r"[\"'“]([^\"'”]+)[\"'”]", c)
            fm = re.search(r"(?:fill|type|enter|input)\s+(?:in\s+)?(\w+)", c, re.I)
            steps.append(_step("fill", fm.group(1) if fm else "field", q.group(1) if q else ""))
        elif re.search(r"\b(verify|assert|expect|check|see|should)\b", low):
            q = re.search(r"[\"'“]([^\"'”]+)[\"'”]", c)
            steps.append(_step("assert", assertion=(q.group(1) if q else c).strip()))
        elif pm:
            steps.append(_step("goto", pm.group(1)))
        else:
            steps.append(_step("assert", assertion=c[:60]))
    if not any(s["action"] == "goto" for s in steps):
        steps.insert(0, _step("goto", "/"))
    return steps


def parse_prose_llm(text: str) -> list[dict[str, Any]]:
    from agents.common.llm import get_llm, load_prompt
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm()
    resp = llm.invoke([
        SystemMessage(content=load_prompt("flow")),
        HumanMessage(content=f"Turn this journey into steps:\n\n{text}"),
    ])
    raw = resp.content.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if fence:
        raw = fence.group(1)
    data = json.loads(raw)
    steps = data.get("steps", data) if isinstance(data, dict) else data
    return [
        _step(s.get("action", "assert"), s.get("target", ""), s.get("value", ""), s.get("assertion", ""))
        for s in steps
        if s.get("action")
    ]


def parse_flow(text: str, *, steps_mode: bool = False) -> tuple[list[dict[str, Any]], str]:
    """Return (steps, mode). steps_mode forces the explicit line parser."""
    text = (text or "").strip()
    if not text:
        raise ValueError("describe the journey or provide steps")
    # explicit step lines: every non-empty line starts with a known verb
    verbs = re.compile(r"^\s*(goto|go\s+to|open|navigate|click|fill|type|enter|press|wait|assert|verify|expect|check)\b", re.I)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    looks_like_steps = steps_mode or (len(lines) > 1 and all(verbs.match(ln) for ln in lines))
    if looks_like_steps:
        return parse_step_lines(text), "steps"

    from agents.parser.agent import _llm_available

    if _llm_available():
        try:
            return parse_prose_llm(text), "llm"
        except Exception:
            pass
    return parse_prose_heuristic(text), "heuristic"
