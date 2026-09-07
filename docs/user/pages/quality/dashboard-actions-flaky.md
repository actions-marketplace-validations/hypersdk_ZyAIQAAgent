# Flaky check

## Purpose

Re-run the suite N times and surface unstable tests.

## When to use it

- Open this card when the job matches the purpose above
- Prefer **Mission Control** (`/dashboard`) and the **⌘K** command palette if you are unsure where to start
- Confirm `ZYVOR_BASE_URL`, dashboard auth, and that Playwright browsers are installed if runs fail immediately

## How to get there

- Surface: `/dashboard/actions/flaky`
- UI: Mission Control → **Quality** → **Flaky check** (side rail panel, or ⌘K / Ctrl-K Search)

## Operate from the console (UX)

1. Open `/dashboard` (sign in at `/login` when `DASHBOARD_PASSWORD` is set).
2. Fill the card fields for **Flaky check**, then start the action and watch the live job panel (✓/✗ chips, Stop, download log).
3. After success, check **Findings**, **QA Runs**, and any video / report links the card produces.
4. Turn recurring checks into a **Schedule** (5 min – 6 h) when you want continuous monitoring.

If the card stays idle or errors, hit `GET /health`, confirm the webhook/dashboard process is up (`argus serve`), and re-check env from [.env.example](../../../../.env.example).

## Next step: quarantine

After Flaky check ranks unstable tests, quarantine them so change-based select
drops them until fixed:

```bash
argus intel quarantine-add "<title>" --reason "INC-… flake" --file <spec> --ttl-hours 72
# or POST /api/v2/intel/quarantine
```

See [Test health](../operations/dashboard-test-health.md) and the feature guide's
**Test intelligence** section.

## Related pages

- [Test health](../operations/dashboard-test-health.md)
- [Getting Started](../../getting-started.md)
- [Using the Dashboard](../../using-the-dashboard.md)
- [Mission Control](../overview/dashboard.md)
- [Page index](../../PAGE_INDEX.md)
