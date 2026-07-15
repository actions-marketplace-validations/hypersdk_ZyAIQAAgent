# zyvor-diff — Rust Screenshot Processor (Phase 4)

Fast pixel-diff utility for visual regression, called from Python when `ENABLE_RUST_PROCESSOR=true`. Much faster than the default Pillow path on large screenshot suites.

## Build

```bash
make rust
# or:
cd rust && cargo build --release
```

Produces `rust/target/release/zyvor-diff`. The Python bridge (`agents/regression/rust_bridge.py`) finds it automatically in `target/release/` or `target/debug/`, or via the `ZYVOR_DIFF_BINARY` env var.

## Usage

```bash
zyvor-diff \
  --baseline screenshots/baselines/homepage-hero.png \
  --current  screenshots/current/homepage-hero.png \
  --diff-output screenshots/diffs/diff-homepage-hero.png \
  --threshold 1.0
```

Behavior:

- Images with mismatched dimensions are resized (current → baseline size) before comparison.
- Writes a per-pixel absolute-difference image to `--diff-output`.
- Prints a JSON result to stdout and exits non-zero when the diff exceeds the threshold:

```json
{"baseline":"…","current":"…","diff_output":"…","diff_percent":0.42,"threshold":1.0,"passed":true}
```

Note: `diff_percent` counts *changed pixels* (any channel differs), unlike the Pillow path which weights by intensity delta — expect slightly different values around the threshold.

## Enable in the pipeline

```bash
# .env
ENABLE_REGRESSION=true
ENABLE_RUST_PROCESSOR=true
```

See [Tutorial 6 — Visual regression](../docs/tutorials/06-visual-regression.md).

## Possible extensions

- HAR / network log parsing at scale
- Trace file analysis
- Perceptual (SSIM-style) diffing to reduce anti-aliasing noise
