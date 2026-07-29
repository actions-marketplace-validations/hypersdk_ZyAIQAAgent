# Tutorial 13 — Test zyvor.dev with recording

Hands-on recipe that points ZyAIQAAgent at **[https://zyvor.dev](https://zyvor.dev)**. Start by **watching the committed journey video**, then re-run the same steps yourself (smoke, flow with video, HAR, Mission Control UX).

**Prerequisites:** [Tutorial 1](01-getting-started.md) (`make install`, Playwright Chromium). No LLM key required for these steps.

---

## Watch the recording

This is a real Playwright capture of zyvor.dev (home → assert HyperSDK → click Products):

<video src="../assets/zyvor-dev-mission-control-demo.webm" controls width="720" title="zyvor.dev journey recording"></video>

- **Video file:** [`docs/assets/zyvor-dev-mission-control-demo.webm`](../assets/zyvor-dev-mission-control-demo.webm)
- **Steps that produced it:** [`docs/assets/zyvor-dev-demo.steps`](../assets/zyvor-dev-demo.steps)
- **Raw GitHub URL:** https://github.com/hypersdk/ZyAIQAAgent/raw/main/docs/assets/zyvor-dev-mission-control-demo.webm

---

## 0. Point at zyvor.dev

```bash
# .env (minimum)
ZYVOR_BASE_URL=https://zyvor.dev
```

---

## 1. Smoke (no recording)

```bash
zyvor-qa test --grep @smoke
```

Mission Control: ▶ **Smoke** (optional `@smoke` grep).

---

## 2. Re-record the same journey

```bash
zyvor-qa flow https://zyvor.dev \
  --steps docs/assets/zyvor-dev-demo.steps \
  --video
# → reports/artifacts/flows/cli/journey.webm
# optional: refresh the committed demo
# cp reports/artifacts/flows/cli/journey.webm docs/assets/zyvor-dev-mission-control-demo.webm
```

**Mission Control:** Actions → 🎬 **Flow test** → URL `https://zyvor.dev` → paste the steps → **record video** on → Run. Download `journey.webm` from the result panel / 🎬 Videos.

---

## 3. HAR record / replay

```bash
zyvor-qa har-replay https://zyvor.dev --mode record --routes / --har /tmp/zyvor-home.har
zyvor-qa har-replay https://zyvor.dev --mode replay --har /tmp/zyvor-home.har \
  --expect-text Zyvor --not-found-ok
```

---

## 4. Mission Control UX (what to look for)

```bash
zyvor-qa serve --port 8080
open http://localhost:8080/dashboard
```

| Cue | What it means |
|-----|----------------|
| **Boot splash** | Short “warming Mission Control…” intro |
| **Full-bleed layout** | Edge-to-edge console |
| **Glass sticky topbar / footer** | Brand + status while you scroll |
| **Live constellation / signal field** | Canvas behind the hero |
| **Primary Smoke CTA** | One-click ▶ Smoke |
| **⌘K palette** | Jump to Flow, HAR, … |
| **NOC wall** | Double-click the brand |
| **Warp flash** | `` ` `` or type `zyvor` |

---

## Related

- [Tutorial 10 — Mission Control](10-mission-control-dashboard.md)
- [Tutorial 11 — Flow tests](11-flow-tests.md)
- [Customer: test zyvor.dev](../customer/test-zyvor-dev.md)
- [Customer: using the dashboard](../customer/using-the-dashboard.md)
