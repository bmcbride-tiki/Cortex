# Cortex Session Memories

This folder holds short, high-signal session logs — not raw conversation transcripts. Each file captures what happened in a significant working session on Cortex: what was decided, what was built, what's still open. It travels with the repo (unlike Claude's own per-user memory system, which lives outside the project), so anyone — or any future session — opening this project sees the same decision history.

**At the start of a session working on Cortex:** read `INDEX.md` first, then whichever entries look relevant to the current task. Don't read every entry every time — the index exists so you don't have to.

**Format:** `YYYY-MM-DD-<short-topic>.md`, each with:
- **What happened** — 3-6 sentences, no blow-by-blow
- **Key decisions** — the things a later session must not silently re-litigate
- **What's next** — the concrete handoff point

**When to add an entry:** after a session that made a real architectural decision, finished a development-roadmap stage, or resolved something worth not re-discovering from scratch. Not every session needs one — routine bug fixes and small features don't.

See also, at the repo root: `CORTEX_ARCHITECTURE_BLUEPRINT.md` (current-state reference) and `CORTEX_DEVELOPMENT_ROADMAP.md` (the staged plan). This folder is the narrative connecting them — *why* a decision was made, not just what the decision was.
