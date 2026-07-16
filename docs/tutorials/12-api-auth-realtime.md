# Tutorial 12 — Testing products, not just pages: API, Auth, Live-data & Web-quality

The earlier tutorials test **web pages** (crawl, audit, flow, route-sweep). But the products this agent tests are **API-first, auth-gated, and streaming-heavy** — a dashboard is only the tip. This tutorial covers four capability clusters that test the rest of the product:

1. **API contract** — validate REST endpoints against their OpenAPI schema, and run multi-step API workflows.
2. **Auth & session** — real login → reusable session → logout/expiry/negative-auth checks.
3. **Live data** — assert WebSocket / SSE streams are actually live, not just that the page loads.
4. **Web quality** — Core Web Vitals, device + network emulation, cross-browser.

All four are in the dashboard (their own cards), the CLI, and the ⌘K palette, and each writes a CSV/HTML/PDF report.

---

## 1. API contract testing

Every product exposes an OpenAPI spec. Point the agent at it and it exercises each endpoint, checking the response **status** is declared and the body **validates against the response schema** (a self-contained JSON-Schema validator handles `type`/`required`/`properties`/`items`/`enum`/`nullable`/`$ref`/`oneOf`/`anyOf`/`allOf` — no extra deps).

```bash
# spec mode — validate GET endpoints (add --include-writes for POST/PUT/DELETE)
zyvor-qa api-test https://api.example.com --spec https://api.example.com/openapi.json
zyvor-qa api-test https://api.example.com --spec ./openapi.json --token "$JWT"
```

In the dashboard, the **🔌 API contract** card takes the base URL, a spec URL (or pasted inline JSON), and an optional bearer token. The result is a per-endpoint table with red rows for schema violations (e.g. `$.user.email: required property missing`).

### Multi-step API workflows

For async lifecycles (create → poll-until-Running → delete), pass a **workflow** file — an ordered list of steps with `{{variable}}` interpolation from earlier responses and a `poll` step:

```json
[
  { "name": "create VM", "method": "POST", "path": "/api/v1/vms",
    "body": { "name": "qa-vm", "template": "ubuntu-24" },
    "extract": { "vmid": "metadata.name" }, "expect": { "status": 201 } },
  { "name": "wait until Running", "method": "GET", "path": "/api/v1/vms/default/{{vmid}}",
    "poll": { "json_path": "status.phase", "equals": "Running", "timeout_ms": 60000 } },
  { "name": "delete", "method": "DELETE", "path": "/api/v1/vms/default/{{vmid}}",
    "expect": { "status": 200 } }
]
```

```bash
zyvor-qa api-test https://api.example.com --workflow vm-lifecycle.json --token "$JWT"
```

---

## 2. Auth & session testing

Login in these products lives in `sessionStorage` (JWT), cookies, or one-time tickets. The **🔐 Auth & session** action logs in — either by driving a **login page** in-browser or POSTing an **API login endpoint** — captures a full **storageState** (cookies + localStorage + sessionStorage), and asserts:

- authenticated access to a protected path works,
- **unauthenticated** access is gated (401/redirect) from a fresh context,
- a **tampered token** is rejected,
- **logout** clears the session.

```bash
# API login (token → sessionStorage), then run the checks and save the session
zyvor-qa auth-test https://app.example.com --api-login /api/v1/auth/login \
  --username admin --password 'secret' --protected /dashboard --logout-url /api/v1/auth/logout

# or drive the login form in-browser
zyvor-qa auth-test https://app.example.com --login-url /login --username admin --password 'secret'
```

### Reuse the session everywhere

A passed auth-test saves the session as `reports/artifacts/auth/<host>.json`. Feed its name back into **flow** or **live-data** so they start already logged in — reliable "test behind login" instead of best-effort form-fill:

```bash
zyvor-qa flow https://app.example.com --steps checkout.flow --session app-example-com.json
zyvor-qa realtime https://app.example.com --ws /api/v1/ws/flows --session app-example-com.json
```

In the dashboard, put the session filename in the 🎬 Flow card's "reuse session" field.

---

## 3. Live data — WebSocket & SSE

A dashboard that *loads* isn't the same as one whose live data *updates*. The **📡 Live data** action connects to a stream and asserts it's alive:

```bash
# WebSocket: connect, receive ≥N messages in the window, then survive a forced reconnect
zyvor-qa realtime https://app.example.com --ws /api/v1/ws/flows --expect-messages 3

# JWT via subprotocol (packetwolf): Sec-WebSocket-Protocol: access_token,<jwt>
zyvor-qa realtime https://app.example.com --ws /api/v1/ws/threats --token "$JWT" --subprotocol-jwt

# one-time ticket (veyron): issue a ticket, then connect with ?ticket=
zyvor-qa realtime https://app.example.com --ws /api/v1/vms/default/vm1/vnc --ticket-url /api/v1/ws-ticket

# SSE job/log progress
zyvor-qa realtime https://app.example.com --sse /api/v1/events --expect-messages 1
```

It also does a **browser live-view** check: give a `--live-selector` and it loads the dashboard, counts WebSocket frames via `page.on('websocket')`, and asserts a live region's text actually changed. Crucially it uses **`domcontentloaded` + a per-request latency budget** instead of `networkidle` (always-live dashboards never idle) and classifies the page `ok | crash | api-5xx | slow` — a hung `/api/` call is reported as **slow**, not a false pass.

---

## 4. Web quality

### Core Web Vitals

```bash
zyvor-qa vitals https://app.example.com                 # LCP / CLS / INP / FCP / TTFB, graded
zyvor-qa vitals https://app.example.com --throttle 3g   # under a throttled connection
zyvor-qa vitals https://app.example.com --device "iPhone 14"
```

Each metric is graded good / needs-improvement / poor against Google's thresholds. The **📊 Web Vitals** card has device and throttle dropdowns.

### Device, network & cross-browser (on flow)

The **🎬 Flow** action gained three dropdowns (and CLI flags) so a journey can run under real conditions:

```bash
zyvor-qa flow https://app.example.com --steps signup.flow --browser firefox
zyvor-qa flow https://app.example.com --steps signup.flow --device "Pixel 7"
zyvor-qa flow https://app.example.com --steps signup.flow --throttle offline   # graceful-degradation
```

- **`--browser`** chromium / firefox / webkit — catches Safari/Firefox-specific breakage (Chromium was the only engine before). The deploy script installs all three; if firefox/webkit aren't present it falls back to chromium.
- **`--device`** uses Playwright's real device profiles (touch, UA, viewport).
- **`--throttle`** 3g / offline via CDP — run the same journey and assert the app degrades gracefully.

---

## When to use which

| Surface | Action |
|---------|--------|
| REST API correctness | `api-test` (spec or workflow) |
| Login / session / RBAC | `auth-test` (+ reuse the session elsewhere) |
| Live tables, metrics, consoles, job progress | `realtime` |
| Performance, mobile, Safari/Firefox, offline | `vitals` + flow `--browser/--device/--throttle` |
| A page renders / looks right | crawl, audit, route-sweep, flow (Tutorials 10–11) |

## Configuration

| Variable | Effect |
|----------|--------|
| `ZYVOR_BROWSER` | flow engine: chromium / firefox / webkit (set by `--browser`) |
| `ZYVOR_DEVICE` | Playwright device profile (set by `--device`) |
| `ZYVOR_THROTTLE` | 3g / offline network emulation (set by `--throttle`) |
| `ZYVOR_SLOW_MS` | live-data per-request latency budget before a page is flagged `slow` (default 12000) |
| `ZYVOR_IGNORE_HTTPS_ERRORS` | accept self-signed certs (set by `--insecure`) |

A target-site login password is redacted (`***`) from the job-status API and history — see Tutorial 11.
