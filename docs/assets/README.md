# docs/assets

Committed demo artifacts for docs and the README (not under gitignored `reports/`).

| File | What it is |
|------|------------|
| [`zyvor-dev-mission-control-demo.webm`](zyvor-dev-mission-control-demo.webm) | Playwright journey recording against [zyvor.dev](https://zyvor.dev) (home → assert HyperSDK → Products) |
| [`zyvor-dev-demo.steps`](zyvor-dev-demo.steps) | Step file used to produce that video |

Regenerate:

```bash
zyvor-qa flow https://zyvor.dev --steps docs/assets/zyvor-dev-demo.steps --video
cp reports/artifacts/flows/cli/journey.webm docs/assets/zyvor-dev-mission-control-demo.webm
```
