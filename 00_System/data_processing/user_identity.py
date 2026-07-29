# =============================================================================
# user_identity.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Figures out "what is this signed-in user actually allowed to use?" --
#   which Microsoft 365 / Google Workspace licenses (SKUs) they hold, and
#   which Cortex building blocks that unlocks (base M365 access, Copilot,
#   Copilot Premium, Power Platform, Visio export, Google Enterprise...).
#   This is what lets the Workflow Builder grey out a block the current
#   user isn't licensed for, instead of letting them build a workflow that
#   would fail the moment it tried to run.
#
#   Real license lookup (querying Microsoft Graph's `/me/licenseDetails`)
#   isn't wired up yet -- see CLAUDE.md's mock-mode principle. Today,
#   `resolve_current_user()` simulates a user's entitlements from
#   environment variables (`CORTEX_USER_UPN`, `HAS_COPILOT_PREMIUM`, etc.),
#   with the real Graph API call being a drop-in replacement for later.
#
# WHAT IT INTERACTS WITH
#   - `workflow_schema.py`'s `WorkflowContext`, which stores one resolved
#     `UserEntitlements` object for the lifetime of a workflow run.
#   - `core_router.py`'s `CoreWorkflowRouter`, which calls
#     `resolve_current_user()` before running a step and checks
#     `has_capability()` against that step's required license.
#   - `server.py`, which uses the same capability checks to decide which
#     Workflow Builder palette entries/canvas nodes get greyed out for the
#     current user, and which real product logo/icon each maps to.
#
# KEY FUNCTIONALITY NOTES
#   - `CapabilityFlag`: the fixed list of Cortex-recognized capabilities.
#     `M365_BASE` and `COPILOT_BASIC` are baseline -- every resolved user
#     gets them automatically, since they represent what any signed-in M365
#     account already has. The others (Copilot Premium, Power Platform,
#     Visio, Google Enterprise) only get added when their matching
#     environment flag is set, simulating a real per-user SKU check.
#   - `UserEntitlements.has_capability()`: the one method everything else
#     calls to answer "is this user licensed for X?" -- a plain membership
#     check against their resolved capability list.
# =============================================================================

import os
from typing import List, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field

class CapabilityFlag(str, Enum):
    M365_BASE = "m365_base"
    COPILOT_BASIC = "copilot_basic"
    COPILOT_PREMIUM = "copilot_premium"
    POWER_PLATFORM = "power_platform"
    VISIO_EXPORT = "visio_export"
    GOOGLE_ENTERPRISE = "google_enterprise"

# Known Enterprise SKU Identifiers (Microsoft Graph Service Plan / SKU IDs)
KNOWN_SKUS = {
    "COPILOT_PREMIUM_SKU": ["64a50465-b17a-4de0-b6d1-ed0c52210343", "M365_COPILOT"],
    "POWER_PLATFORM_SKU": ["POWER_AUTOMATE_P2", "POWERAPPS_VIRIR"],
    "VISIO_SKU": ["VISIOCLIENT", "VISIO_PLAN_2"],
    "GOOGLE_ENTERPRISE": ["google_ent_domain_user"]
}

class UserEntitlements(BaseModel):
    user_principal_name: str
    display_name: str
    tenant_id: str
    assigned_skus: List[str] = Field(default_factory=list)
    capabilities: List[CapabilityFlag] = Field(default_factory=list)

    def has_capability(self, capability: CapabilityFlag) -> bool:
        return capability in self.capabilities

class UserIdentityManager:
    """Acquires user identity and maps Microsoft Graph / SSO entitlements to Cortex building block capabilities."""

    @staticmethod
    def resolve_current_user(auth_references: Optional[Dict[str, str]] = None) -> UserEntitlements:
        auth_refs = auth_references or {}

        upn = os.getenv("CORTEX_USER_UPN", "user@enterprise.com")
        tenant = os.getenv("M365_TENANT_ID", "default_tenant")

        caps = [CapabilityFlag.M365_BASE, CapabilityFlag.COPILOT_BASIC]
        skus = []

        if os.getenv("HAS_COPILOT_PREMIUM", "false").lower() == "true" or "ref://vault/copilot_premium" in auth_refs.values():
            caps.append(CapabilityFlag.COPILOT_PREMIUM)
            skus.append("M365_COPILOT")

        if os.getenv("HAS_POWER_PLATFORM", "false").lower() == "true":
            caps.append(CapabilityFlag.POWER_PLATFORM)
            skus.append("POWER_AUTOMATE_P2")

        if os.getenv("HAS_VISIO", "false").lower() == "true":
            caps.append(CapabilityFlag.VISIO_EXPORT)
            skus.append("VISIO_PLAN_2")

        if os.getenv("HAS_GOOGLE_ENTERPRISE", "false").lower() == "true" or "google_access" in auth_refs:
            caps.append(CapabilityFlag.GOOGLE_ENTERPRISE)
            skus.append("google_ent_domain_user")

        return UserEntitlements(
            user_principal_name=upn,
            display_name=upn.split("@")[0].capitalize(),
            tenant_id=tenant,
            assigned_skus=skus,
            capabilities=caps
        )
