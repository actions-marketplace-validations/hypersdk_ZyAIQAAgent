# Using the Dashboard

ZyAIQAAgent’s **Mission Control** is a single live console at `/dashboard` (login at `/login` when password auth is on).

## Surfaces

| Element | Purpose |
|---------|---------|
| **Hero** | Health banner + stat tiles (pods, replicas, last run, pass rate, cron) |
| **Workloads / Pods** | K8s strip and pod cards with log drawer (needs kube SA or kubeconfig) |
| **Actions grid** | Every job card — smoke, flow, HAR, codegen, API, auth, vitals, probes, … |
| **Live job panel** | Streaming log, case chips, Stop, copy/download log |
| **Schedules** | Loop smoke / audit / ping / TLS / flow / sweep / API / realtime / vitals |
| **Findings** | Aggregated issues from quality jobs |
| **QA Runs / Videos** | History and recorded journeys |
| **Command palette** | ⌘K / Ctrl-K to find any action by name |

## Browse vs act

Reading pods, history, and findings is safe. Starting jobs mutates the target under test and writes reports under `reports/` — confirm URL, credentials, and scope before Run.

## Related

- [Getting Started](getting-started.md)
- [Page-by-page guides](pages/README.md)
- [Common workflows](workflows.md)
