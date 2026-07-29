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

"""Safety policy for autonomous browser actions.

The LLM proposes an action; this module is the deterministic enforcement point.
Page content is always treated as untrusted data.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urljoin, urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from orchestrator.security.target_policy import TargetPolicy, TargetPolicyError

ActionRisk = Literal["read", "input", "write", "privileged", "destructive"]


class BrowserAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["click", "fill", "select", "press", "goto", "wait_until", "assert", "done"]
    i: int | None = Field(default=None, ge=0)
    value: str | None = Field(default=None, max_length=4000)
    text: str | None = Field(default=None, max_length=2000)
    timeout: int | None = Field(default=None, ge=0, le=300_000)
    reason: str | None = Field(default=None, max_length=500)
    summary: str | None = Field(default=None, max_length=1000)
    success: bool | None = None

    @field_validator("value", "text", "reason", "summary")
    @classmethod
    def strip_control_chars(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return "".join(ch for ch in value if ch == "\n" or ch == "\t" or ord(ch) >= 32)


_PROMPT_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore (?:all|any|the)?\s*(?:previous|prior|system) instructions",
        r"you are (?:now|an?) (?:assistant|system|agent)",
        r"system (?:message|prompt|instruction)",
        r"reveal (?:your|the) (?:prompt|secret|token|password)",
        r"send .* (?:token|password|secret|credential)",
        r"do not follow the user",
        r"developer message",
    )
]

_DESTRUCTIVE = re.compile(
    r"\b(delete|destroy|terminate|drop|purge|wipe|erase|factory reset|remove cluster|uninstall)\b",
    re.IGNORECASE,
)
_PRIVILEGED = re.compile(
    r"\b(restart pod|reboot|grant|revoke|role|permission|administrator|admin|rotate key|disable security)\b",
    re.IGNORECASE,
)
_WRITE = re.compile(
    r"\b(create|deploy|submit|finish|confirm|save|update|apply|migrate|start|stop|restart|attach|detach|send|invite)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AgentDecision:
    allowed: bool
    risk: ActionRisk
    action: dict[str, Any]
    reason: str = ""
    prompt_injection_detected: bool = False


@dataclass(frozen=True)
class AgentPolicy:
    mode: Literal["read_only", "supervised", "unrestricted"] = "read_only"
    allow_destructive: bool = False
    approved_risks: frozenset[str] = frozenset()

    @classmethod
    def from_env(cls) -> "AgentPolicy":
        raw_mode = os.environ.get("ZYVOR_AGENT_MODE", "read_only").strip().lower()
        mode = raw_mode if raw_mode in {"read_only", "supervised", "unrestricted"} else "read_only"
        approved = frozenset(
            value.strip().lower()
            for value in os.environ.get("ZYVOR_AGENT_APPROVED_RISKS", "").split(",")
            if value.strip()
        )
        return cls(
            mode=mode,  # type: ignore[arg-type]
            allow_destructive=os.environ.get("ZYVOR_AGENT_ALLOW_DESTRUCTIVE", "false").lower()
            in {"1", "true", "yes", "on"},
            approved_risks=approved,
        )

    def evaluate(
        self,
        proposed: dict[str, Any],
        observation: dict[str, Any],
        *,
        initial_url: str,
    ) -> AgentDecision:
        try:
            action = BrowserAction.model_validate(proposed)
        except ValidationError as exc:
            return self._deny("read", proposed, f"invalid agent action: {exc.errors()[0]['msg']}")

        element = self._element_for(action, observation)
        if action.action in {"click", "fill", "select"} and action.i is None:
            return self._deny("read", proposed, "action requires an element index")
        if action.i is not None and element is None:
            return self._deny("read", proposed, "element index is not present in the current observation")
        if element is not None and not element.get("enabled", True) and action.action == "click":
            return self._deny("read", proposed, "element is disabled")

        injection = detect_prompt_injection(observation)
        risk = classify_action(action, element)

        if action.action == "goto":
            destination = urljoin(initial_url, action.value or "")
            try:
                TargetPolicy.from_env().validate_url(destination)
            except TargetPolicyError as exc:
                return self._deny(risk, proposed, f"navigation blocked: {exc}", injection)
            if urlsplit(destination).netloc != urlsplit(initial_url).netloc:
                allowed_origins = {
                    v.strip().lower()
                    for v in os.environ.get("ZYVOR_AGENT_ALLOWED_ORIGINS", "").split(",")
                    if v.strip()
                }
                if urlsplit(destination).netloc.lower() not in allowed_origins:
                    return self._deny(risk, proposed, "cross-origin navigation is not approved", injection)

        if injection and risk in {"write", "privileged", "destructive"}:
            return self._deny(risk, proposed, "write action blocked because page content resembles prompt injection", True)

        if risk == "destructive" and not self.allow_destructive:
            return self._deny(risk, proposed, "destructive browser actions are disabled", injection)
        if self.mode == "read_only" and risk in {"write", "privileged", "destructive"}:
            return self._deny(risk, proposed, "agent is in read-only mode", injection)
        if self.mode == "supervised" and risk in {"write", "privileged", "destructive"}:
            if risk not in self.approved_risks:
                return self._deny(risk, proposed, f"{risk} action requires operator approval", injection)

        # Return the exact validated action for execution. Redaction belongs in
        # status/audit serialization; mutating a fill value here could break a test.
        clean = action.model_dump(exclude_none=True)
        return AgentDecision(True, risk, clean, prompt_injection_detected=injection)

    @staticmethod
    def _element_for(action: BrowserAction, observation: dict[str, Any]) -> dict[str, Any] | None:
        if action.i is None:
            return None
        return next((e for e in observation.get("elements", []) if e.get("i") == action.i), None)

    @staticmethod
    def _deny(
        risk: ActionRisk,
        proposed: dict[str, Any],
        reason: str,
        injection: bool = False,
    ) -> AgentDecision:
        blocked = {
            "action": "done",
            "success": False,
            "summary": f"safety policy blocked action: {reason}",
        }
        return AgentDecision(False, risk, blocked, reason, injection)


def detect_prompt_injection(observation: dict[str, Any]) -> bool:
    content = "\n".join(str(v) for v in observation.get("texts", []))[:50_000]
    return any(pattern.search(content) for pattern in _PROMPT_INJECTION_PATTERNS)


def classify_action(action: BrowserAction, element: dict[str, Any] | None) -> ActionRisk:
    if action.action in {"assert", "wait_until", "done", "goto"}:
        return "read"
    if action.action in {"fill", "select"}:
        return "input"
    label = " ".join(
        str(v or "")
        for v in (
            element.get("name") if element else "",
            action.value,
            action.reason,
        )
    )
    if _DESTRUCTIVE.search(label):
        return "destructive"
    if _PRIVILEGED.search(label):
        return "privileged"
    if _WRITE.search(label) or action.action == "press":
        return "write"
    return "read"


def enforce_agent_action(
    proposed: dict[str, Any],
    observation: dict[str, Any],
    *,
    initial_url: str,
) -> dict[str, Any]:
    """Compatibility helper used directly by `agents/aiflow/engine.py`."""
    return AgentPolicy.from_env().evaluate(proposed, observation, initial_url=initial_url).action
