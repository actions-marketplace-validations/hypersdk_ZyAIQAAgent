# Test health

## Purpose

Worst-offender ranking by fail count, fail %, and flaky badge from the per-test index.

## When to use it

- Open this card when the job matches the purpose above
- Prefer **Mission Control** (`/dashboard`) and the **⌘K** command palette if you are unsure where to start
- Confirm `ZYVOR_BASE_URL`, dashboard auth, and that Playwright browsers are installed if runs fail immediately

## How to get there

- Surface: `/dashboard/test-health`
- UI: Mission Control → **Operations** panel → **Test health** (side rail, or ⌘K / Ctrl-K **Search**)

## What you can do

1. Open `/dashboard` (sign in at `/login` when `DASHBOARD_PASSWORD` is set).
2. Open **Operations → Test health** for the worst-offender ranking (fail count, fail %, flaky badge) from the per-test index.
3. For a classified overlay (healthy / failing / flaky / …) plus quarantine status, use `GET /api/v2/intel/health` or `argus intel health`.
4. For a red job's cases + on-disk video/trace + category, use `GET /api/v2/intel/studio/{job_id}`.

If the panel stays empty, hit `GET /health`, confirm `argus serve` is up, and ensure runs have written `reports/test-index.jsonl` / `reports/history/`.

## Related pages

- [Flaky check](../quality/dashboard-actions-flaky.md)
- [Getting Started](../../getting-started.md)
- [Using the Dashboard](../../using-the-dashboard.md)
- [Mission Control](../overview/dashboard.md)
- [Page index](../../PAGE_INDEX.md)
