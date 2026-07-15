# Tutorial 10 — Mission Control Dashboard

A live, self-refreshing dashboard served by the webhook server: Kubernetes pod health, deployment/cronjob status, pod log tails, and QA run history with a pass-rate trend. Styled to match the HyperSDK dashboard (macOS Tahoe liquid-glass).

**Prerequisites:** [Tutorial 1](01-getting-started.md). A Kubernetes cluster is optional — without one the QA runs panel still works and the pod panel shows an offline state.

---

## 1. Open it locally

```bash
zyvor-qa serve --port 8080
# then browse to:
open http://localhost:8080/dashboard
```

What you'll see:

- **Status hero** — one glanceable verdict with stat tiles for pods, replicas, last QA run, and a countdown to the next scheduled smoke run:
  - `ALL SYSTEMS GO` — every pod healthy, last QA run green
  - `DEGRADED` — some pods unhealthy or the last QA run failed
  - `SYSTEMS DOWN` — every pod unhealthy
  - `CLUSTER OFFLINE` — no Kubernetes API reachable (normal on a laptop)
- **Workloads** — per-deployment replica readiness; per-cronjob schedule, last run, and "in 4h 12m" countdown
- **Pods** — one card per pod: phase, ready containers, restart count, age, node, image, recent Warning events. **Click a pod** to open the log drawer (last 100 lines, live-refreshing; hover pauses refresh).
- **QA Runs** — latest result, pass-rate sparkline over the last 30 runs (hover for per-run detail), and a recent-runs table

Keyboard: `r` refreshes immediately, `esc` closes the log drawer. Everything auto-refreshes every 5 seconds.

## 2. Where run history comes from

Every pipeline run (`zyvor-qa run`, webhook-triggered runs) appends one JSON entry to `reports/history/` (kept to the most recent 200). Generate some data:

```bash
zyvor-qa run --source local
```

Refresh the dashboard — the run appears in the table and the sparkline.

## 3. Point it at a cluster

The Kubernetes panel activates automatically when an API is reachable, in this order:

1. **In-cluster** service account (when running as the K8s webhook Deployment)
2. **Local kubeconfig** (`~/.kube/config` or `KUBECONFIG`) — so `zyvor-qa serve` on your laptop can watch any cluster you can

Configuration:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DASHBOARD_NAMESPACE` | in-cluster namespace, else `default` | Namespace to inspect |
| `DASHBOARD_POD_SELECTOR` | *(all pods in namespace)* | Label selector, e.g. `app=zyvor-qa-agent` |

Try it with a local cluster:

```bash
kind create cluster --name zyvor-qa
DASHBOARD_NAMESPACE=kube-system zyvor-qa serve --port 8080
```

## 4. Deploy on Kubernetes

The manifests already wire this up: `kubernetes/rbac.yaml` grants the `zyvor-qa` service account read-only access (pods, logs, events, deployments, cronjobs) and the webhook Deployment uses it.

```bash
make k8s-validate
make k8s-apply
```

**Access is deliberately not exposed through the ingress** — the dashboard can read pod logs, which don't belong on the public internet. Use a port-forward:

```bash
kubectl port-forward svc/zyvor-qa-webhook 8080:80
open http://localhost:8080/dashboard
```

If you do want it on the ingress, add an authenticated path — see [`kubernetes/README.md`](../../kubernetes/README.md#dashboard-optional-ingress-exposure).

## 5. API endpoints

The page is a thin client over JSON endpoints you can script against:

| Endpoint | Returns |
|----------|---------|
| `GET /api/dashboard/overview` | banner status, namespace, workloads, latest run |
| `GET /api/dashboard/pods` | pod list with health details |
| `GET /api/dashboard/pods/{name}/logs?lines=100` | log tail |
| `GET /api/dashboard/runs?limit=30` | QA run history |

All endpoints are read-only and degrade gracefully (`"available": false`) instead of erroring when no cluster is reachable.
