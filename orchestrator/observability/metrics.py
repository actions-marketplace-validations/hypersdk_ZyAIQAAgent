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

"""Dependency-free Prometheus text metrics."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any

_lock = threading.Lock()
_counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
_gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
_started = time.time()


def _key(name: str, labels: dict[str, Any] | None) -> tuple[str, tuple[tuple[str, str], ...]]:
    safe = tuple(sorted((str(k), str(v)) for k, v in (labels or {}).items()))
    return name, safe


def inc(name: str, value: float = 1, **labels: Any) -> None:
    with _lock:
        _counters[_key(name, labels)] += value


def set_gauge(name: str, value: float, **labels: Any) -> None:
    with _lock:
        _gauges[_key(name, labels)] = value


def _format(name: str, labels: tuple[tuple[str, str], ...], value: float) -> str:
    suffix = ""
    if labels:
        escaped = [f'{k}="{v.replace(chr(92), chr(92)+chr(92)).replace(chr(34), chr(92)+chr(34))}"' for k, v in labels]
        suffix = "{" + ",".join(escaped) + "}"
    return f"{name}{suffix} {value}"


def render() -> str:
    with _lock:
        counters = dict(_counters)
        gauges = dict(_gauges)
    lines = ["# TYPE zyvor_qa_uptime_seconds gauge", f"zyvor_qa_uptime_seconds {time.time() - _started:.3f}"]
    for (name, labels), value in sorted(counters.items()):
        lines.append(_format(name, labels, value))
    for (name, labels), value in sorted(gauges.items()):
        lines.append(_format(name, labels, value))
    return "\n".join(lines) + "\n"
