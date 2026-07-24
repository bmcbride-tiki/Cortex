---
tool_id: 'health'
title: 'Health Check Probe'
classification: '00_System_Core'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, tier/zero-input, function/liveness-probe, scope/data-processing, connects/workflow-schema, connects/enterprise-adapters]
---

# health

> **Status:** Active. Runnable directly (`python 00_System/health.py`); also the container health-check command in the project `Dockerfile`.

## Purpose

A basic "is the app's data-processing layer intact?" check -- tries to import `data_processing`'s core modules and reports whether each loaded cleanly. Meant for an external process (a container orchestrator, a monitoring probe, a developer's terminal) that wants a quick UP/DOWN signal without starting the full web server.

## Processing Logic

### `check_health() -> Dict`

Tries importing [[workflow_schema]] and [[enterprise_adapters]], each in its own `try/except`. Any import failure marks that module `UNHEALTHY: <error>` and flips the overall `status` to `DOWN`; success marks it `HEALTHY`. Never raises.

## Output

`{"status": "UP"|"DOWN", "python_version": ..., "modules": {...}}`, printed as JSON when run directly.

## Notes for AI reuse

Adds `00_System` itself to `sys.path` first (same bootstrap pattern as `server.py`), so `data_processing.*` imports resolve regardless of the working directory this script is launched from. To extend the check, add another `try/except` block importing whatever new module needs a liveness guarantee.
