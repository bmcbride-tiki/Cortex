---
tool_id: 'generate_vault_map'
title: 'Generate Vault Map'
classification: '05_Processes'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/process, domain/03-process, tier/zero-input, function/introspection, scope/vault-map]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# generate-vault-map

> **Status:** Active. Zero-input, click-and-run Process -- no settings, just writes a fresh tree diagram of the whole project folder.

## Purpose

Builds a plain-text tree diagram of the entire Cortex project folder (like the output of the `tree` command), so a quick "what's actually in this vault right now" snapshot exists as a readable file.

## Input

None. Running the script processes with no arguments.

## Processing Logic

Walks the project root (`Path(__file__).resolve().parents[2]` -- two levels up from this script, i.e. the repo root) recursively via `_build_tree()`, skipping `venv`, `.git`, and `__pycache__`. Writes the resulting tree lines to `vault_map.txt`, right next to this script, overwriting any previous run.

## Output

`{"success": true, "mapped_nodes": <count>, "output_file": "vault_map.txt", "errors": []}`, plus the actual `vault_map.txt` file on disk.

## Notes for AI reuse

⚠ **Found during this documentation pass:** this file was previously undocumented beyond a one-line status ("Builds a clean tree topography of the local system configuration partitions[cite: 12]") with no Purpose/Input/Processing Logic/Output sections and a stray citation artifact (`[cite: 12]`) left over from an earlier AI-assisted edit -- likely copy-pasted from a source with citation markers that were never cleaned up. Fixed here to match the documentation shape every sibling Process in this folder uses.

Not tagged with a `model` key in `server.py`'s `TOOL_MODELS` -- this Process is pure filesystem introspection, no AI model involved, so it doesn't affect a workflow's classification ceiling (see [[model_classifications]]).
