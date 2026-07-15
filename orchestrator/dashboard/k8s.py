"""Read-only Kubernetes inspector for the Mission Control dashboard.

Every public function degrades to an ``{"available": False}`` payload instead of
raising, so the dashboard works identically in-cluster, with a local kubeconfig,
or with no cluster at all.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

NAMESPACE_FILE = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")

_client_cache: dict[str, Any] = {}


def _load_clients() -> Optional[dict[str, Any]]:
    """Return cached API clients, or None when no cluster is reachable."""
    if "clients" in _client_cache:
        return _client_cache["clients"]

    # Imported via importlib: the repo's kubernetes/ manifest directory can shadow
    # the installed client package when cwd is on sys.path.
    import importlib

    try:
        client = importlib.import_module("kubernetes.client")
        config = importlib.import_module("kubernetes.config")
    except ImportError:
        _client_cache["clients"] = None
        return None

    try:
        config.load_incluster_config()
    except Exception:
        try:
            config.load_kube_config()
        except Exception:
            _client_cache["clients"] = None
            return None

    clients = {
        "core": client.CoreV1Api(),
        "apps": client.AppsV1Api(),
        "batch": client.BatchV1Api(),
    }
    _client_cache["clients"] = clients
    return clients


def reset_client_cache() -> None:
    """Drop cached clients (used by tests and after kubeconfig changes)."""
    _client_cache.clear()


def get_namespace() -> str:
    """Resolve the namespace to inspect."""
    env_ns = os.environ.get("DASHBOARD_NAMESPACE", "").strip()
    if env_ns:
        return env_ns
    if NAMESPACE_FILE.exists():
        try:
            return NAMESPACE_FILE.read_text(encoding="utf-8").strip() or "default"
        except OSError:
            pass
    return "default"


def _pod_selector() -> Optional[str]:
    selector = os.environ.get("DASHBOARD_POD_SELECTOR", "").strip()
    return selector or None


def _age_seconds(start: Optional[datetime]) -> Optional[int]:
    if not start:
        return None
    return max(0, int((datetime.now(timezone.utc) - start).total_seconds()))


def _pod_restart_count(pod: Any) -> int:
    statuses = pod.status.container_statuses or []
    return sum(s.restart_count or 0 for s in statuses)


def _pod_ready(pod: Any) -> tuple[int, int]:
    statuses = pod.status.container_statuses or []
    total = len(pod.spec.containers or [])
    ready = sum(1 for s in statuses if s.ready)
    return ready, total


def _pod_images(pod: Any) -> list[str]:
    return [c.image for c in (pod.spec.containers or [])]


def list_pods() -> dict[str, Any]:
    """List pods in the dashboard namespace with health details."""
    clients = _load_clients()
    namespace = get_namespace()
    if not clients:
        return {"available": False, "namespace": namespace, "pods": []}

    try:
        result = clients["core"].list_namespaced_pod(
            namespace,
            label_selector=_pod_selector(),
        )
        warnings = _recent_warning_events(clients, namespace)
    except Exception as exc:
        return {"available": False, "namespace": namespace, "pods": [], "error": str(exc)}

    pods: list[dict[str, Any]] = []
    for pod in result.items:
        ready, total = _pod_ready(pod)
        name = pod.metadata.name
        pods.append(
            {
                "name": name,
                "phase": pod.status.phase or "Unknown",
                "ready": ready,
                "total": total,
                "restarts": _pod_restart_count(pod),
                "age_seconds": _age_seconds(pod.status.start_time),
                "node": pod.spec.node_name,
                "pod_ip": pod.status.pod_ip,
                "images": _pod_images(pod),
                "warnings": warnings.get(name, []),
            }
        )

    pods.sort(key=lambda p: p["name"])
    return {"available": True, "namespace": namespace, "pods": pods}


def _recent_warning_events(clients: dict[str, Any], namespace: str) -> dict[str, list[str]]:
    """Map pod name -> recent Warning event messages (best effort)."""
    warnings: dict[str, list[str]] = {}
    try:
        events = clients["core"].list_namespaced_event(
            namespace,
            field_selector="type=Warning",
        )
    except Exception:
        return warnings

    for event in events.items[-100:]:
        involved = event.involved_object
        if involved and involved.kind == "Pod" and involved.name:
            message = f"{event.reason}: {event.message or ''}".strip()
            warnings.setdefault(involved.name, []).append(message[:200])
    return {name: msgs[-3:] for name, msgs in warnings.items()}


def pod_logs(name: str, lines: int = 100) -> dict[str, Any]:
    """Return the log tail for a pod."""
    clients = _load_clients()
    namespace = get_namespace()
    if not clients:
        return {"available": False, "name": name, "lines": []}

    try:
        raw = clients["core"].read_namespaced_pod_log(
            name,
            namespace,
            tail_lines=max(1, min(lines, 1000)),
            timestamps=True,
        )
    except Exception as exc:
        return {"available": False, "name": name, "lines": [], "error": str(exc)}

    return {
        "available": True,
        "name": name,
        "lines": raw.splitlines(),
    }


def get_workloads() -> dict[str, Any]:
    """Deployment replica health and CronJob schedule status."""
    clients = _load_clients()
    namespace = get_namespace()
    if not clients:
        return {"available": False, "namespace": namespace, "deployments": [], "cronjobs": []}

    deployments: list[dict[str, Any]] = []
    cronjobs: list[dict[str, Any]] = []

    try:
        for dep in clients["apps"].list_namespaced_deployment(namespace).items:
            deployments.append(
                {
                    "name": dep.metadata.name,
                    "ready": dep.status.ready_replicas or 0,
                    "desired": dep.spec.replicas or 0,
                }
            )
        for cron in clients["batch"].list_namespaced_cron_job(namespace).items:
            last = cron.status.last_schedule_time
            last_success = cron.status.last_successful_time
            cronjobs.append(
                {
                    "name": cron.metadata.name,
                    "schedule": cron.spec.schedule,
                    "suspend": bool(cron.spec.suspend),
                    "last_schedule": last.isoformat() if last else None,
                    "last_successful": last_success.isoformat() if last_success else None,
                    "active": len(cron.status.active or []),
                }
            )
    except Exception as exc:
        return {
            "available": False,
            "namespace": namespace,
            "deployments": deployments,
            "cronjobs": cronjobs,
            "error": str(exc),
        }

    return {
        "available": True,
        "namespace": namespace,
        "deployments": deployments,
        "cronjobs": cronjobs,
    }
