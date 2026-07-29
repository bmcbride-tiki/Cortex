---
tool_id: 'list_sharepoint_sites'
title: 'List SharePoint Sites'
classification: '05_Processes'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/process, domain/03-process, tier/zero-input, function/m365, scope/sharepoint]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# list-sharepoint-sites

> **Status:** Active. Zero-input, click-and-run Process (like [[generate_vault_map]]) — lists SharePoint Online sites.

## Purpose

Lists SharePoint Online sites (optionally pre-filtered). Mock-mode until
an Azure AD app registration exists (see [[m365_graph_bridge]]).

## Input

None. Running the script processes with no arguments.

## Processing Logic

Imports and calls `list_sharepoint_sites()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "query": "", "sites": [{"id", "name", "web_url"}, ...]}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`. Feed a `site.id`
into [[get_sharepoint_site]]/[[list_sharepoint_lists]].
