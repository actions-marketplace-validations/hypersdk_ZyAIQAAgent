# docs/assets

Committed demo artifacts for docs and the README (not under gitignored `reports/`).

| File | What it is |
|------|------------|
| [`zyvor-dev-mission-control-demo.gif`](zyvor-dev-mission-control-demo.gif) | README inline preview (GitHub renders GIFs) |
| [`zyvor-dev-mission-control-demo.mp4`](zyvor-dev-mission-control-demo.mp4) | H.264 recording — play on GitHub blob page |
| [`zyvor-dev-mission-control-demo.webm`](zyvor-dev-mission-control-demo.webm) | Original Playwright journey capture |
| [`zyvor-dev-demo.steps`](zyvor-dev-demo.steps) | Step file used to produce that video |
| [`guestkit-github-demo.webm`](guestkit-github-demo.webm) / [`.mp4`](guestkit-github-demo.mp4) | Journey through [hypersdk/guestkit](https://github.com/hypersdk/guestkit) README |
| [`guestkit-github.steps`](guestkit-github.steps) | Steps for the GitHub recording |
| [`guestkit-product-demo.webm`](guestkit-product-demo.webm) / [`.mp4`](guestkit-product-demo.mp4) | Journey through [zyvor.dev/guestkit](https://zyvor.dev/guestkit) |
| [`guestkit-product.steps`](guestkit-product.steps) | Steps for the product-page recording |

Regenerate:

```bash
zyvor-qa flow https://zyvor.dev --steps docs/assets/zyvor-dev-demo.steps --video
cp reports/artifacts/flows/cli/journey.webm docs/assets/zyvor-dev-mission-control-demo.webm
ffmpeg -y -i docs/assets/zyvor-dev-mission-control-demo.webm -c:v libx264 -pix_fmt yuv420p -movflags +faststart -an docs/assets/zyvor-dev-mission-control-demo.mp4
ffmpeg -y -i docs/assets/zyvor-dev-mission-control-demo.webm -vf "fps=8,scale=720:-1:flags=lanczos" -loop 0 docs/assets/zyvor-dev-mission-control-demo.gif
```
