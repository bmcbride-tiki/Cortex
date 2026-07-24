---
tool_id: 'user_identity'
title: 'User Identity & Entitlements'
classification: '00_System_Core/data_processing'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, domain/data-processing, tier/zero-input, function/license-gating, function/user-identity, scope/workflow-builder, connects/workflow-schema, connects/core-router, connects/server]
---

# user-identity

> **Status:** Active, mock-mode. No `__main__` block. Imported by [[workflow_schema]], [[core_router]], and [[server]].

## Purpose

Figures out "what is this signed-in user actually allowed to use?" -- which M365/Google licenses (SKUs) they hold, and which Cortex building blocks that unlocks. Lets the Workflow Builder grey out a block the current user isn't licensed for, instead of letting them build a workflow that would fail the moment it tried to run.

Real license lookup (Microsoft Graph's `/me/licenseDetails`) isn't wired up yet, per CLAUDE.md's mock-mode principle -- `resolve_current_user()` simulates entitlements from environment variables, with the real Graph call as a drop-in replacement later.

## Processing Logic

### `CapabilityFlag` (enum)

The fixed list of Cortex-recognized capabilities: `M365_BASE`, `COPILOT_BASIC` (baseline -- every resolved user gets both automatically), `COPILOT_PREMIUM`, `POWER_PLATFORM`, `VISIO_EXPORT`, `GOOGLE_ENTERPRISE` (only granted when their matching environment flag is set).

### `UserEntitlements.has_capability(capability) -> bool`

Plain membership check against the user's resolved capability list -- the one method everything else calls to answer "is this user licensed for X?"

### `UserIdentityManager.resolve_current_user(auth_references=None) -> UserEntitlements`

Reads `CORTEX_USER_UPN`/`M365_TENANT_ID` for identity, then `HAS_COPILOT_PREMIUM`/`HAS_POWER_PLATFORM`/`HAS_VISIO`/`HAS_GOOGLE_ENTERPRISE` (or matching `auth_references` entries) to decide which non-baseline capabilities to add.

## Output

A `UserEntitlements` object, cached on a workflow's `WorkflowContext.user_entitlements` (see [[workflow_schema]]) for the run's lifetime.

## Notes for AI reuse

To wire up real license checking later: replace the body of `resolve_current_user` with an actual Graph `/me/licenseDetails` call, mapping returned SKU IDs to `CapabilityFlag`s via `KNOWN_SKUS`. Every caller already goes through this one function, so no other file needs to change.
