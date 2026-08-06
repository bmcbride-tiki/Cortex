# 2026-07-31 — gbrain/gstack Setup

## What Happened

Investigated and declined `claude-mem` (unauthenticated local HTTP API found in a third-party security audit) as a memory tool, then set up `gbrain` instead at the user's request. Found that `.claude/skills/gstack/` was a full vendored copy of the `gstack` dev monorepo sitting untracked inside Cortex — not a lightweight skill, but Garry Tan's entire AI-dev-tooling product (browser automation, ML classifiers, cloud provisioning, ~50 skills), and its own docs call vendoring "deprecated." Migrated it to a proper global install at `~/.claude/skills/gstack/`, removed the vendored copy from Cortex, and gitignored it. Installed and initialized `gbrain` with a local-only PGLite engine (no cloud account), registered it as a user-scope MCP server, imported Cortex's markdown docs with a read-write repo policy, and declined embedding-provider setup and artifacts sync to keep everything local-only. Hit and worked around two Windows-only environment gaps (`jq` missing; two gstack/gbrain scripts report false failures on Windows even when things work).

## Key Decisions

- **gbrain lives outside Cortex, globally on this machine** — `~/.claude/skills/gstack/`, `~/gbrain/`, `~/.gbrain/brain.pglite`. Nothing gbrain-related should be vendored back into this repo; `.claude/skills/gstack/` is now in `.gitignore` specifically to prevent that.
- **Local PGLite only, no cloud, no embedding provider (yet).** Consistent with the project's low-footprint/no-unnecessary-dependencies stance (see Claude's own memory `user_cortex_drift_concern`). Semantic search is disabled until an OpenAI/Voyage/ZeroEntropy key is added later.
- **Cortex repo policy: read-write.** gbrain can index and write pages from this repo; still entirely local since the engine is PGLite.
- **Artifacts sync declined.** No private GitHub repo created, no cross-machine sync — everything stays on this machine.
- Full setup detail, install paths, and the two Windows false-negative warnings (safe to ignore) are recorded in Claude's own cross-session memory (`reference_gbrain_gstack_setup`), not duplicated here.

## What's Next

Restart Claude Code to pick up the `mcp__gbrain__*` tools (they load at session start only). Roadmap Stage 0 (archiving the dormant Path B files under `data_processing/`) is still the next open Cortex-development task from the prior session — untouched by today's gbrain work.
