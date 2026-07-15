# Configuration Reference

Every environment variable the agent reads, with defaults and the code that consumes it. Copy `.env.example` to `.env` and adjust; the CLI loads `.env` from the repo root automatically.

Boolean flags accept `true`/`false` (case-insensitive).

---

## LLM provider

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | One of `openai`, `anthropic`, `azure`, `google`, `ollama` |
| `LLM_MODEL` | `gpt-4o` | Model name passed to the provider |
| `OPENAI_API_KEY` | — | Required when `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | — | Required when `LLM_PROVIDER=anthropic` |
| `AZURE_OPENAI_API_KEY` | — | Required when `LLM_PROVIDER=azure` |
| `AZURE_OPENAI_ENDPOINT` | — | Required when `LLM_PROVIDER=azure` |
| `AZURE_OPENAI_DEPLOYMENT` | `LLM_MODEL` | Azure deployment name |
| `GOOGLE_API_KEY` | — | Required when `LLM_PROVIDER=google` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server (needs `pip install langchain-community`) |

No key set? Everything still runs — parsing, generation, analysis, and summaries fall back to rule-based/template implementations. Only `zyvor-qa create` (natural-language tests) hard-requires an LLM.

Consumed by: `agents/common/llm.py`, `agents/parser/agent.py`.

---

## GitHub integration

| Variable | Default | Description |
|----------|---------|-------------|
| `ZYVOR_PRODUCT_REPO` | — | Product repo as `owner/repo` (not a URL). Required for `--source github`. |
| `GITHUB_TOKEN` | — | PAT with `Contents: Read` (+ `Pull requests: Write` for PR comments). Optional if `gh auth login` is configured — resolution order is `GITHUB_TOKEN` → `gh auth token`. |
| `GITHUB_WEBHOOK_SECRET` | — | HMAC secret for `zyvor-qa serve`. If empty, signature verification is skipped (do not leave empty in production). |

Consumed by: `github/client.py`, `orchestrator/webhook.py`, `orchestrator/nodes/fetch.py`.

---

## Target environment

| Variable | Default | Description |
|----------|---------|-------------|
| `ZYVOR_BASE_URL` | `https://zyvor.dev` | Base URL all tests run against |
| `ZYVOR_STAGING_URL` | — | Overrides the target for dashboard flows (takes precedence over `ZYVOR_BASE_URL` in `playwright/utils/target.ts`) |
| `ZYVOR_TEST_USER` / `ZYVOR_TEST_PASSWORD` | — | Dashboard login credentials |
| `ENABLE_DASHBOARD_TESTS` | `false` | Allow auth/login flows. When false and the target is zyvor.dev, login-tagged tests are skipped — the marketing site has no login. |

Consumed by: `playwright/utils/target.ts`, `playwright/utils/auth.ts`, `agents/generator/agent.py`.

---

## Visual regression (Phase 2)

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_REGRESSION` | `false` | Compare screenshots against `screenshots/baselines/`. Also switches Playwright to `screenshot: 'on'`. |
| `REGRESSION_THRESHOLD` | `1.0` | Max allowed pixel diff, percent |
| `UPDATE_BASELINES` | `false` | Copy current screenshots as new baselines instead of failing on missing ones (set by `zyvor-qa regression --update-baselines`) |
| `ENABLE_RUST_PROCESSOR` | `false` | Use the Rust `zyvor-diff` binary instead of Pillow (build first: `make rust`) |
| `ZYVOR_DIFF_BINARY` | — | Explicit path to `zyvor-diff` if not in `rust/target/{release,debug}/` |

Consumed by: `orchestrator/nodes/regression.py`, `agents/regression/*`, `playwright/playwright.config.ts`.

---

## API validation & logs (Phase 2)

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_API_VALIDATION` | `false` | Validate HTTP statuses captured by fixtures and HAR files in `traces/` |

Browser log analysis (console errors, network failures) is **always on** and needs no flag. Noise (favicon, analytics, CSP, Cloudflare) is filtered in `agents/logs/analyzer.py`.

---

## LLM analysis, reports, notifications (Phase 3)

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_LLM_ANALYSIS` | `true` | LLM root-cause analysis of failures (stub fallback on error) |
| `ENABLE_LLM_REPORT` | `true` | LLM plain-English report summary (stub fallback) |
| `ENABLE_PDF_REPORT` | `true` | Render `reports/qa-summary.pdf` via headless Chromium |
| `SLACK_WEBHOOK_URL` | — | Slack incoming webhook (block-formatted message) |
| `TEAMS_WEBHOOK_URL` | — | Microsoft Teams webhook (MessageCard) |
| `SMTP_HOST` | — | SMTP server; enables email when set together with `NOTIFY_EMAIL_TO` |
| `SMTP_PORT` | `587` | SMTP port (STARTTLS is used when user+password are set) |
| `SMTP_USER` / `SMTP_PASSWORD` | — | SMTP credentials; also used as From address |
| `NOTIFY_EMAIL_TO` | — | Recipient address (PDF report attached when available) |

Consumed by: `orchestrator/nodes/analyze.py`, `orchestrator/nodes/report.py`, `agents/reporter/*`.

---

## Autofix / self-healing (Phase 4)

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_AUTOFIX` | `false` | Suggest selector repairs after failures |
| `ENABLE_AUTOFIX_APPLY` | `false` | Actually patch spec files and re-run failed tests |
| `AUTOFIX_MAX_RETRIES` | `2` | Max apply→re-execute loops per run |

Consumed by: `orchestrator/graph.py`, `orchestrator/nodes/autofix.py`, `orchestrator/nodes/apply_autofix.py`.

---

## Multi-browser (Phase 4)

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_MULTI_BROWSER` | `false` | Add firefox and webkit projects alongside chromium |

Consumed by: `playwright/playwright.config.ts`. Install browsers first: `npx playwright install --with-deps`.

---

## Coverage expansion

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_COVERAGE_EXPANSION` | `false` | Discover routes/pages/docs from the product repo and generate missing tests on GitHub runs (equivalent to `--expand-coverage`) |
| `COVERAGE_MAX_NEW_TESTS` | `10` | Cap on new `coverage-*.spec.ts` files per run |
| `COVERAGE_DISCOVERY_PATHS` | `docs/, docs/specs/, CHANGELOG.md, README.md, src/pages/, src/routes/, app/` | Comma-separated repo roots to scan |
| `COVERAGE_MAX_DISCOVERY_FILES` | `200` | Max files downloaded per discovery run |
| `COVERAGE_MAX_DISCOVERY_BYTES` | `2000000` | Max total bytes downloaded |

Consumed by: `orchestrator/coverage_config.py`, `github/client.py`, `orchestrator/nodes/{fetch,discover,gap_analyze}.py`.

Note: an explicit `--spec` disables coverage expansion unless you also pass `--expand-coverage`.

---

## Live site crawl

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_LIVE_CRAWL` | `false` | BFS-crawl the deployed site and merge routes into the coverage inventory |
| `CRAWL_MAX_PAGES` | `50` | Page budget |
| `CRAWL_MAX_DEPTH` | `2` | Link depth from `/` |
| `CRAWL_TIMEOUT_SECONDS` | `120` | Subprocess timeout for the crawl script |

Consumed by: `agents/discover/crawl.py`, `playwright/scripts/crawl-site.mjs`. Standalone run: `npm run crawl`.

---

## Mission Control dashboard

| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_NAMESPACE` | in-cluster namespace, else `default` | Kubernetes namespace the dashboard inspects |
| `DASHBOARD_POD_SELECTOR` | *(empty — all pods in namespace)* | Label selector filter, e.g. `app=zyvor-qa-agent` |

The dashboard is served by `zyvor-qa serve` at `/dashboard`. Cluster access resolves in-cluster config first, then local kubeconfig; with neither, the pod panels show an offline state and QA run history still works. See [Tutorial 10](tutorials/10-mission-control-dashboard.md).

Consumed by: `orchestrator/dashboard/k8s.py`.

---

## V8 JS coverage

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_V8_COVERAGE` | `false` | Collect Chromium V8 JS coverage per test; aggregated into the report (`reports/v8-coverage/`) |

Consumed by: `playwright/fixtures/base.ts`, `agents/coverage/v8_report.py`.

---

## Recommended profiles

**Minimal smoke (no LLM, no GitHub):**

```bash
ZYVOR_BASE_URL=https://zyvor.dev
```

**PR bot (webhook or Actions):**

```bash
ZYVOR_PRODUCT_REPO=owner/repo
GITHUB_TOKEN=ghp_...
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-5
ENABLE_API_VALIDATION=true
ENABLE_LLM_ANALYSIS=true
ENABLE_LLM_REPORT=true
```

**Full self-healing nightly:**

```bash
ENABLE_REGRESSION=true
ENABLE_API_VALIDATION=true
ENABLE_AUTOFIX=true
ENABLE_AUTOFIX_APPLY=true
ENABLE_COVERAGE_EXPANSION=true
ENABLE_V8_COVERAGE=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```
