"""Lightweight recurring-job scheduler — turns the console into a monitor.

Each schedule re-triggers a job kind on a fixed interval. A single background
thread checks due schedules; if a job is already running it simply waits for
the next tick (respects the runner's single-flight lock).
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

_lock = threading.Lock()
_schedules: dict[str, dict[str, Any]] = {}
_seq = 0
_thread_started = False


def _now() -> float:
    return time.time()


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def add(kind: str, params: dict[str, Any], interval_s: int) -> dict[str, Any]:
    global _seq
    interval_s = max(30, min(int(interval_s), 86400))
    with _lock:
        _seq += 1
        sid = f"s{_seq}"
        _schedules[sid] = {
            "id": sid,
            "kind": kind,
            "params": params,
            "interval_s": interval_s,
            "next_at": _now() + interval_s,
            "runs": 0,
            "last_at": None,
            "created": _iso(),
        }
        entry = dict(_schedules[sid])
    _ensure_thread()
    return entry


def remove(sid: str) -> bool:
    with _lock:
        return _schedules.pop(sid, None) is not None


def listing() -> list[dict[str, Any]]:
    with _lock:
        out = []
        now = _now()
        for s in _schedules.values():
            e = dict(s)
            e["due_in_s"] = max(0, round(e["next_at"] - now))
            e.pop("next_at", None)
            out.append(e)
    return out


def _ensure_thread() -> None:
    global _thread_started
    with _lock:
        if _thread_started:
            return
        _thread_started = True
    threading.Thread(target=_loop, daemon=True).start()


def _loop() -> None:
    from orchestrator.dashboard import jobs

    while True:
        time.sleep(10)
        now = _now()
        due = []
        with _lock:
            for s in _schedules.values():
                if now >= s["next_at"]:
                    due.append(s)
        for s in due:
            try:
                started, _ = jobs.trigger(s["kind"], dict(s["params"]))
            except Exception:
                started = False
            with _lock:
                cur = _schedules.get(s["id"])
                if not cur:
                    continue
                # reschedule regardless; if the runner was busy we just try again
                cur["next_at"] = now + cur["interval_s"]
                if started:
                    cur["runs"] += 1
                    cur["last_at"] = _iso()
