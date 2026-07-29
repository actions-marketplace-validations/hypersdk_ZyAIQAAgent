"""Fail-closed runtime configuration checks."""

from __future__ import annotations

import os


class SecurityConfigurationError(RuntimeError):
    pass


def validate_runtime_security() -> None:
    env = os.environ.get("ZYVOR_ENV", "development").strip().lower()
    if env not in {"production", "prod"}:
        return

    problems: list[str] = []
    required = {
        "DASHBOARD_PASSWORD": 12,
        "DASHBOARD_SECRET": 32,
        "GITHUB_WEBHOOK_SECRET": 32,
    }
    for name, minimum in required.items():
        value = os.environ.get(name, "")
        if len(value) < minimum:
            problems.append(f"{name} must contain at least {minimum} characters")
    if not os.environ.get("ZYVOR_TARGET_ALLOWLIST", "").strip():
        problems.append("ZYVOR_TARGET_ALLOWLIST is required in production")
    if os.environ.get("ZYVOR_AGENT_MODE", "read_only").lower() == "unrestricted" and os.environ.get(
        "ZYVOR_ALLOW_UNRESTRICTED_AGENT_IN_PRODUCTION", "false"
    ).lower() not in {"1", "true", "yes", "on"}:
        problems.append("unrestricted AI-agent mode is disabled in production")
    if problems:
        raise SecurityConfigurationError("unsafe production configuration: " + "; ".join(problems))
