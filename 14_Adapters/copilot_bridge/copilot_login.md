---
tool_id: 'copilot_login'
title: 'Copilot Login (Manual Fallback)'
classification: '00_System_Core/adapters'
data_policy: 'internal'
execution_engine: 'browser_automation'
tags: [type/script, domain/system-core, tier/manual-setup, function/authentication, scope/m365-copilot, connects/copilot-bridge]
---

# copilot-login

> **Status:** Active, manual fallback only. Superseded by [[copilot_bridge]]'s `initialize_edge_profile()` (the same flow, wired into Cortex's "Initialize Session Auth" button) -- kept as a standalone script you can run directly from a terminal if that button ever stops working.

## Purpose

Opens a real, visible Microsoft Edge window at the M365 Copilot chat site so a human can sign in by hand once; Edge saves that login session to a `copilot_browser_profile/` folder on disk. Every other Copilot-related script reuses that saved profile afterward without asking for a login again.

## Processing Logic

Single top-to-bottom script, no functions: launches `p.chromium.launch_persistent_context(user_data_dir="copilot_browser_profile", headless=False, ...)`, navigates to `https://m365.cloud.microsoft/chat/`, then holds the window open for up to 5 minutes (`page.wait_for_timeout(300000)`) so the user has time to complete their organization's login/MFA steps. Closing the window early is fine; nothing else needs to happen after login.

## Output

No return value / no file written directly by this script -- the side effect is Edge's own saved session data inside `copilot_browser_profile/`, which [[copilot_bridge]] and [[copilot_ask]] both read.

## Notes for AI reuse

If this needs updating (e.g. the target URL changes), also check whether [[copilot_bridge]]'s `initialize_edge_profile()` needs the identical change -- the two have drifted into near-duplicate implementations of the same one-time sign-in flow.
