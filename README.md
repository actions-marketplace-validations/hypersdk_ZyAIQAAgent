# Zyvor QA Agent

Autonomous AI testing agent for [Zyvor](https://zyvor.dev) — an AI-first infrastructure platform. Continuously validates the Zyvor platform by reading requirements from GitHub, generating Playwright tests, executing them after deployments, detecting regressions, and producing actionable reports.

Ships with **Mission Control** — a live web console (`zyvor-qa serve` → `/dashboard`) that runs 20+ QA capabilities on demand with streamed output and CSV/HTML/PDF reports: the full test pipeline, site audits (a11y/SEO/perf/security with an A–F grade), ten network & security probes, load and TLS checks, visual/environment diffs, flaky detection, screenshots, and recurring monitors. See [`docs/tutorials/10-mission-control-dashboard.md`](docs/tutorials/10-mission-control-dashboard.md).

## Architecture

```
GitHub (specs, PRs, deploy events)
        │
        ▼
LangGraph Orchestrator (Python)
        │
   fetch → parse → generate → execute → regression → api_validate → log_analyze
        │
   ┌────┴──── pass → report → notify
   └──── fail → analyze → autofix → report → notify
        │
   Playwright (Node.js) + Rust diff (optional)
```

- **Orchestrator**: LangGraph state machine coordinates all pipeline stages
- **AI agents**: LLM-provider agnostic via LangChain (OpenAI, Anthropic, Azure, Google, Ollama)
- **Test execution**: Playwright (TypeScript) with screenshot, video, trace capture
- **Cursor**: development assistant only — not a runtime dependency

## Quick Start

### Prerequisites

- Python 3.9+ (3.11+ recommended)
- Node.js 20+
- Git

### Install

```bash
cp .env.example .env
make install
```

### Run smoke tests (no LLM required)

```bash
zyvor-qa test
```

### Run full pipeline from GitHub (your product repo)

```bash
# Ensure .env has ZYVOR_PRODUCT_REPO=ssahani/hypersdk-web
gh auth login

# Generate + run tests from a specific markdown file in the repo
zyvor-qa run --source github --spec docs/specs/my-feature.md

# Generate tests only
zyvor-qa generate --source github --spec docs/specs/my-feature.md
```

See [**Writing Tests & GitHub Integration**](docs/test-authoring.md) for the full command reference.

## Documentation

**New here? Start with the [step-by-step tutorials](docs/tutorials/README.md)** — nine hands-on guides from install to Kubernetes.

| Guide | Description |
|-------|-------------|
| [**Tutorials**](docs/tutorials/README.md) | Getting started, spec-to-test, NL tests, GitHub, coverage, regression, autofix, notifications, CI/CD, dashboard |
| [**Architecture**](docs/architecture.md) | Pipeline internals: LangGraph nodes, state, agents, fallback design |
| [**Configuration**](docs/configuration.md) | Complete environment variable reference with defaults |
| [**Writing Tests & GitHub Integration**](docs/test-authoring.md) | Command reference; manual, spec-driven, and NL test creation |
| [**Mission Control dashboard**](docs/tutorials/10-mission-control-dashboard.md) | The live console: 20+ QA actions, audits, probes, schedules, reports |
| [**Remote deployment**](docs/remote-deploy.md) | `deploy-remote.sh` — bare host, container, or k3s in one command |
| [**Troubleshooting**](docs/troubleshooting.md) | Common errors and fixes |
| [**Contributing**](CONTRIBUTING.md) | Dev setup, conventions, how to add a pipeline stage |
| [`kubernetes/README.md`](kubernetes/README.md) | Kubernetes deployment |
| [`rust/README.md`](rust/README.md) | Rust `zyvor-diff` screenshot processor |
| [`prompts/examples/vm-create.md`](prompts/examples/vm-create.md) | Example requirement spec |

## CLI Commands

Full examples: [**docs/test-authoring.md**](docs/test-authoring.md)

| Command | Description |
|---------|-------------|
| `zyvor-qa test` | Run hand-written smoke tests only |
| `zyvor-qa run --source local --spec <path>` | Full pipeline from a local markdown spec |
| `zyvor-qa run --source github --spec <path>` | Full pipeline from a GitHub markdown file |
| `zyvor-qa run --source github` | Full pipeline from all GitHub specs/issues |
| `zyvor-qa generate --spec <path>` | Generate tests from local spec (no run) |
| `zyvor-qa generate --source github --spec <path>` | Generate tests from GitHub `.md` (no run) |
| `zyvor-qa discover --source github` | List coverage candidates and gaps (no generation) |
| `zyvor-qa run --source github --expand-coverage` | Pipeline + generate tests for uncovered routes/pages |
| `zyvor-qa create "description"` | Generate tests from plain English |
| `zyvor-qa create "description" --execute` | Generate and run NL tests |
| `zyvor-qa regression` | Visual regression check |
| `zyvor-qa regression --update-baselines` | Capture new screenshot baselines |
| `zyvor-qa serve` | GitHub webhook server + Mission Control dashboard (`/dashboard`) |

## Phase Features

### Phase 2 — Regression, API, Logs

| Feature | Flag | Description |
|---------|------|-------------|
| Screenshot regression | `ENABLE_REGRESSION=true` | Pixel diff against baselines in `screenshots/baselines/` |
| API validation | `ENABLE_API_VALIDATION=true` | Validates HTTP status codes from captured API calls |
| Browser log analysis | always on | Console errors and network failures flagged in report |

```bash
# Capture baselines
make regression-update

# Compare against baselines
make regression
```

### Phase 3 — LLM Analysis & Notifications

| Feature | Flag | Description |
|---------|------|-------------|
| LLM failure analysis | `ENABLE_LLM_ANALYSIS=true` | Root cause + fix suggestions from traces/screenshots |
| LLM report summary | `ENABLE_LLM_REPORT=true` | Plain-English PR comment summary |
| PDF report export | `ENABLE_PDF_REPORT=true` | Generates `reports/qa-summary.pdf` from HTML |
| Slack notifications | `SLACK_WEBHOOK_URL` | Rich block-formatted messages |
| Teams notifications | `TEAMS_WEBHOOK_URL` | Adaptive card messages |
| Email notifications | `SMTP_*` env vars | HTML email with PDF attachment |
| K8s deployment | `kubernetes/` | CronJob, Deployment, Service, Ingress |

```bash
# Deploy to Kubernetes (cluster must be running)
make k8s-validate   # offline manifest check
make k8s-apply      # apply to cluster
```

### Phase 4 — Autofix, NL Tests, Multi-browser, Rust

| Feature | Flag | Description |
|---------|------|-------------|
| Autofix suggestions | `ENABLE_AUTOFIX=true` | LLM-powered selector repair after failures |
| Autofix apply + re-run | `ENABLE_AUTOFIX_APPLY=true` | Patch spec files and re-execute (self-healing) |
| NL test creation | `zyvor-qa create` | Generate tests from plain English |
| Multi-browser | `ENABLE_MULTI_BROWSER=true` | Chromium + Firefox + WebKit |
| Rust diff processor | `ENABLE_RUST_PROCESSOR=true` | Fast screenshot diff via `zyvor-diff` binary |
| Coverage expansion | `ENABLE_COVERAGE_EXPANSION=true` | Discover untested routes/pages from repo code/docs |
| Live site crawl | `ENABLE_LIVE_CRAWL=true` | BFS crawl of the deployed site into coverage inventory |
| V8 JS coverage | `ENABLE_V8_COVERAGE=true` | Measure JS coverage of test runs, reported as % |
| Mission Control dashboard | `zyvor-qa serve` → `/dashboard` | Live K8s pod health, log tails, QA run history + trends |

```bash
# Natural language test
zyvor-qa create "Verify homepage shows all 14 products" --execute

# Build Rust diff tool
make rust

# Multi-browser (manual)
ENABLE_MULTI_BROWSER=true npx playwright test
```

## Environment Variables

See [**docs/configuration.md**](docs/configuration.md) for the complete annotated reference, and [`.env.example`](.env.example) for a starting template. Key variables:

| Variable | Description |
|----------|-------------|
| `LLM_PROVIDER` | `openai`, `anthropic`, `azure`, `google`, `ollama` |
| `ENABLE_REGRESSION` | Enable screenshot visual regression |
| `ENABLE_API_VALIDATION` | Enable API response validation |
| `ENABLE_LLM_ANALYSIS` | LLM-powered failure analysis |
| `ENABLE_AUTOFIX` | Selector repair suggestions |
| `ENABLE_MULTI_BROWSER` | Run tests on chromium, firefox, webkit |
| `ENABLE_RUST_PROCESSOR` | Use Rust `zyvor-diff` for screenshot comparison |

## Project Structure

```
├── orchestrator/       # LangGraph pipeline, CLI, webhook
│   └── nodes/          # One node per pipeline stage
├── agents/
│   ├── common/         # Shared Pydantic models + LLM factory
│   ├── parser/         # Requirement parsing (LLM + rule-based)
│   ├── generator/      # Playwright test generation + quality gate
│   ├── execution/      # Playwright subprocess bridge + artifacts
│   ├── discover/       # Coverage discovery from code/docs + live crawl
│   ├── coverage/       # Gap analysis + V8 coverage aggregation
│   ├── regression/     # Screenshot diff (Pillow / Rust) (Phase 2)
│   ├── api_validation/ # API response checks (Phase 2)
│   ├── logs/           # Console/network log analysis (Phase 2)
│   ├── analyzer/       # LLM failure analysis (Phase 3)
│   ├── autofix/        # Selector repair + apply (Phase 4)
│   ├── nl_create/      # NL test creation (Phase 4)
│   └── reporter/       # HTML/PDF reports + GitHub/Slack/Teams/email
├── github/             # GitHub API client, token resolution
├── playwright/         # Config, fixtures, utils, crawl + PDF scripts
├── prompts/            # LLM system prompts (markdown)
├── templates/          # Jinja2 fallback test + HTML report
├── tests/manual/       # Hand-written smoke + visual regression tests
├── tests/generated/    # Generated tests (disposable)
├── docs/               # Guides + tutorials
├── rust/               # zyvor-diff screenshot processor (Phase 4)
├── kubernetes/         # K8s manifests (Phase 3)
└── docker/             # Container image
```

## CI/CD

- **Smoke tests**: `.github/workflows/qa-smoke.yml` — push, PR, nightly
- **Multi-browser**: manual `workflow_dispatch` trigger in same workflow
- **Post-deploy**: `.github/workflows/qa-post-deploy.yml` — `repository_dispatch: staging-deployed`

## Roadmap Status

| Phase | Status | Features |
|-------|--------|----------|
| **1** | Complete | GitHub integration, Playwright, test gen, CI/CD, HTML + PDF reports |
| **2** | Complete | Screenshot regression, API validation, browser log analysis |
| **3** | Complete | LLM failure analysis, Slack/Teams/email, K8s deployment |
| **4** | Complete | Autofix, NL test creation, multi-browser, Rust processor |

## License

Apache 2.0 — see [LICENSE](LICENSE).
