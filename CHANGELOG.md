# Changelog

## [0.3.0](https://github.com/hypersdk/ZyAIQAAgent/releases/tag/v0.3.0) — 2026-07-30

### Added
- **Ask Zyvor** — optional citation-first knowledge RAG (`knowledge/` package, Qdrant hybrid retrieval) in Mission Control; Tutorial 14
- Streaming ask (`POST /v1/qa/stream`, dashboard SSE), query understanding, evidence-based confidence
- Optional read-only live cluster diagnostic tools (namespaced allowlist)
- Separate HITL remediation planner + allowlisted pod-restart executor
- Mission Control → GuestKit YouTube demo: https://youtu.be/ys7SvKKqf9w
- Sample knowledge corpus, ingest/evaluate CLIs, unit tests for knowledge

### Docs
- YouTube thumbnail embeds in README, Tutorial 10/13, customer manuals
- Configuration + `.env.knowledge.example` for knowledge / remediation flags
- Feature guide: Ask Zyvor + demo links

### Container
- `ghcr.io/hypersdk/zyaiqaagent:v0.3.0` (+ `:latest`)

## [0.2.0](https://github.com/hypersdk/ZyAIQAAgent/releases/tag/v0.2.0) — 2026-07-29

Initial GHCR-published feature release with Mission Control journeys, HAR/codegen, and zyvor.dev demo assets.
