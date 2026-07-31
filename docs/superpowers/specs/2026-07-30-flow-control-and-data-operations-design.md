# Flow Control & Data Operations Function Nodes — Design

## Goal

Add the Power Automate-style "Built-In" and "Data Operations" actions that Cortex's Workflow Builder doesn't have yet, as new `Function` nodes: **Compose, Parse JSON, HTTP, Response, Terminate, Delay, Delay Until**, and the array family **Filter Array, Select, Join, Sort, Union, Chunk, Length, First, Last, Take, Skip, Create CSV Table, Create HTML Table**.

This is the first of several planned slices toward full Power Automate action parity (see conversation scoping). Explicitly deferred to later slices: `Initialize/Set/Increment/Append Variable` and `Apply to Each`/`Do Until` (both need a real mutable variable store and a loop-execution model the engine doesn't have — see "Explicitly out of scope"), the Google Workspace connector bridge, and the AI capability stubs (sentiment, translation, OCR, etc.).

Three Power Automate primitives requested in the original ask are **already covered by existing nodes** and get no new work here: `Scope` (the existing `container` node kind), `Condition`/`Switch` (the existing `function_logic_gate` and `function_conditions` nodes), and `Approval` (the existing `human_review_checkpoint` function in `13_Functions`).

Touches: `00_System/workflow_engine.py`, `00_System/server.py`, `00_System/templates/workflow-builder.html`.

## Shared mechanics

### Data-shape nodes read upstream text directly, not a bound field

Every array/data node below (`Filter Array` through `Create HTML Table`, plus `Parse JSON`) operates on `self._gather_upstream_text(node_id)` — the same convention `function_logic_gate`, `function_conditions`, and `function_concatenate` already use for "the thing connected into me." No new "Input" field is added; wiring a node's single input edge *is* the binding. This matches the existing rule that these nodes expect exactly one meaningful predecessor — feeding two predecessors into e.g. `Filter Array` joins their text with `"\n\n"` first (via `_gather_upstream_text`), which will simply fail `json.loads` as invalid JSON, the same failure shape every other multi-predecessor misuse already produces today. `Union` is the one exception (see below) — it explicitly needs each predecessor's array kept separate, so it uses `_direct_predecessor_texts(node_id)` instead.

Prompt-style nodes (`Compose`, `HTTP`'s uri/headers/body, `Terminate`'s message, `Delay`'s duration) keep explicit param fields with `{{label}}` substitution, matching `function_gemini_ask`/`function_claude_ask` etc. — these mix a fixed template with dynamic data, so they need a field to type that template into.

### New shared helpers in `workflow_engine.py`

```python
def _parse_json_array(self, node_id: str, friendly_name: str) -> list:
    """Shared by every array-op node below. Raises WorkflowRunError naming the
    node type on invalid JSON or a non-list top-level value."""
    text = self._gather_upstream_text(node_id)
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError) as e:
        raise WorkflowRunError(f"{friendly_name} requires a JSON array as input; got invalid JSON: {e}")
    if not isinstance(parsed, list):
        raise WorkflowRunError(f"{friendly_name} requires a JSON array as input; got {type(parsed).__name__}.")
    return parsed

def _dotted_get(self, obj: Any, path: str) -> Any:
    """Dict-only dotted-path lookup (no list indices, no expressions) -- used by
    Select/Join/Sort/Union for 'pull this nested field out of each item.' Missing
    key at any level returns None rather than raising: a per-item lookup miss
    just produces a null field on that item, consistent with Select's
    row-independent design (one bad item shouldn't kill the whole array)."""
    if not path:
        return obj
    current = obj
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current
```

`_dotted_get` is deliberately dict-keys-only, no list indices and no expression language. *Ponytail ceiling: if a workflow ever needs `items[0].name`-style paths or computed columns in Select, reuse the existing `_eval_condition_expression` safe evaluator (already used by Conditions and, below, Filter Array) instead of building a second expression language.*

## Part 1 — Compose & Parse JSON

**Compose** (`function_compose`) — passes its `value` field through `_substitute_tokens` unchanged. This is the plain "named checkpoint value" building block Power Automate's Compose is; nothing more.
- params: `{ "value": string }`
- Engine: `return self._substitute_tokens(params.get("value", "")), None`
- Field schema: `[{ key: "value", label: "Value", type: "textarea", placeholder: "e.g. {{label}} or a literal value" }]`

**Parse JSON** (`function_parse_json`) — validates the connected input is valid JSON and (optionally) that a set of top-level keys are present, then re-emits it pretty-printed. *Ponytail ceiling: this is a required-keys check, not real JSON Schema validation — `jsonschema` isn't in `requirements.txt` and nothing else in this repo needs full schema validation. Upgrade path: add the `jsonschema` dependency and a "Schema" field if a workflow ever needs type/format constraints, not just key presence.*
- params: `{ "required_keys": string }` — newline-separated, optional
- Engine:
  ```python
  text = self._gather_upstream_text(node_id)
  try:
      parsed = json.loads(text)
  except (TypeError, ValueError) as e:
      raise WorkflowRunError(f"Parse JSON: invalid JSON input: {e}")
  required = [k.strip() for k in self._substitute_tokens(params.get("required_keys", "")).splitlines() if k.strip()]
  if required:
      if not isinstance(parsed, dict):
          raise WorkflowRunError(f"Parse JSON: required keys given but input is a {type(parsed).__name__}, not an object.")
      missing = [k for k in required if k not in parsed]
      if missing:
          raise WorkflowRunError(f"Parse JSON: missing required key(s): {', '.join(missing)}")
  return json.dumps(parsed, indent=2), None
  ```
- Field schema: `[{ key: "required_keys", label: "Required Keys (optional, one per line)", type: "textarea", mono: true }]`

## Part 2 — HTTP & Response

**HTTP** (`function_http`) — a real, working generic REST call using `requests` (already a dependency, already used by the Web Scrape node per `workflow_engine.py`'s own module docstring). Unlike the AI bridges, HTTP needs no OAuth/credentials plumbing, so it's fully functional now, not mocked.
- params: `{ "method": "GET"|"POST"|"PUT"|"PATCH"|"DELETE", "uri": string, "headers": string, "body": string }` — `uri`/`headers`/`body` all get `{{label}}` substitution; `headers` is a JSON object as text (blank = no extra headers).
- Engine:
  ```python
  method = (params.get("method") or "GET").upper()
  uri = self._substitute_tokens(params.get("uri", ""))
  if not uri.strip():
      raise WorkflowRunError("HTTP requires a URI.")
  headers_text = self._substitute_tokens(params.get("headers", "")).strip()
  headers = {}
  if headers_text:
      try:
          headers = json.loads(headers_text)
      except (TypeError, ValueError) as e:
          raise WorkflowRunError(f"HTTP: Headers must be a JSON object: {e}")
  body = self._substitute_tokens(params.get("body", ""))

  if self.dry_run:
      return f"[DRY RUN] Would {method} {uri}", None

  import requests
  try:
      resp = requests.request(method, uri, headers=headers, data=body or None, timeout=30)
  except requests.exceptions.RequestException as e:
      raise WorkflowRunError(f"HTTP {method} {uri} failed: {e}")

  if resp.status_code >= 400:
      raise WorkflowRunError(f"HTTP {method} {uri} failed: {resp.status_code} {resp.reason}\n{resp.text[:1000]}")

  return json.dumps({
      "status_code": resp.status_code,
      "headers": dict(resp.headers),
      "body": resp.text[:5000],
  }, indent=2), None
  ```
  A non-2xx response raises `WorkflowRunError` instead of returning "successful" text — this is what makes a failed downstream call show up as a **failed** step in the run log (red, with the status code and body snippet in the tooltip), directly surfacing whether an application call succeeded or failed for troubleshooting, per your requirement. 30s timeout and 5000-char response-body cap are fixed. *Ponytail ceiling: no retry/backoff — Power Automate's HTTP action doesn't retry by default either; add if a specific flow needs it.*
- Field schema (needs the new `select` type — see Part 5):
  ```js
  function_http: [
      { key: "method", label: "Method", type: "select", options: ["GET", "POST", "PUT", "PATCH", "DELETE"] },
      { key: "uri", label: "URI", type: "text", mono: true, placeholder: "https://api.example.com/..." },
      { key: "headers", label: "Headers (JSON object, optional)", type: "textarea", mono: true, placeholder: '{"Authorization": "Bearer {{token}}"}' },
      { key: "body", label: "Body (optional)", type: "textarea", mono: true },
  ],
  ```

**Response** (`function_response`) — zero configuration. Passes its connected input through unchanged, and is separately recorded as one of the workflow's declared outputs, since Cortex workflows have no external caller to literally respond to yet (per your decision).
- params: `{}`
- Engine: `return self._gather_upstream_text(node_id), None` — identical to Compose's pass-through role but with no template field, since a caller of Response just wants "mark this as an output," not "type a value."
- `run()` bookkeeping: `self.responses: List[Dict[str, str]] = []` added to `__init__` alongside `self.terminated` (see Part 3). In `run()`'s loop, right after a node's `try` block succeeds and `self.context[label]` is set (`workflow_engine.py` ~line 886, before `finished.add(node_id)`):
  ```python
  if node.get("tool_id") == "function_response":
      self.responses.append({"node_id": node_id, "label": label, "output": output_text})
  ```
  Returned in the top-level result as `"responses": self.responses` (see Part 3's updated `run()` return statement — both keys are added together).
- Field schema: `function_response: []` — must be an explicit empty array in `FUNCTION_FIELD_SCHEMAS` (not just "missing"), so `renderFunctionPanel` shows the existing "needs no configuration" message instead of the "No config UI defined" error path.

## Part 3 — Terminate, Delay, Delay Until

**Terminate** (`function_terminate`) — ends the entire run immediately with a declared status, distinct from an ordinary step failure.
- params: `{ "status": "Succeeded"|"Failed"|"Cancelled", "message": string }` — `message` gets `{{label}}` substitution.
- New exception in `workflow_engine.py`, alongside `WorkflowRunError`/`MissingInputError`:
  ```python
  class WorkflowTerminate(Exception):
      def __init__(self, status: str, message: str):
          self.status = status
          self.message = message
          super().__init__(message)
  ```
  Deliberately **not** a `WorkflowRunError` subclass — it must not fall into the generic per-step failure handling in `run()`'s loop; it needs its own `except` clause that stops the whole run rather than continuing to the next queued node.
- Handler: `_execute_function_node` raises it directly rather than returning a tuple:
  ```python
  if tool_id == "function_terminate":
      status = params.get("status", "Failed")
      message = self._substitute_tokens(params.get("message", ""))
      raise WorkflowTerminate(status, message)
  ```
- `run()` loop change (`workflow_engine.py`, inside the existing per-node `try`/`except Exception` block, ~line 883-899): add a new `except WorkflowTerminate` **before** the existing `except Exception`:
  ```python
  try:
      output_text, jump_to = self._execute_node(node_id, node)
      ...
  except WorkflowTerminate as e:
      self.log.append({
          "node_id": node_id, "title": node["title"], "kind": node["kind"],
          "status": "terminated", "output": e.message,
      })
      self.terminated = {"status": e.status, "message": e.message}
      break
  except Exception as e:
      ...
  ```
  `self.terminated: Optional[Dict[str, str]] = None` added to `__init__` (alongside `self.responses: List[Dict[str, str]] = []`, per Part 2). `run()`'s final result gains `"terminated": self.terminated` and its `overall_success` computation becomes:
  ```python
  if self.terminated:
      overall_success = self.terminated["status"] == "Succeeded"
  else:
      overall_success = bool(self.log) and all(s["status"] == "success" for s in self.log)
  return {"success": overall_success, "steps": self.log, "responses": self.responses, "terminated": self.terminated}
  ```
  Both `responses` and `terminated` are additive keys — `server.py`'s `run_workflow` endpoint (`server.py:1188`) returns `JSONResponse(content=result)` verbatim, so no backend contract change is needed there.
- Field schema:
  ```js
  function_terminate: [
      { key: "status", label: "Status", type: "select", options: ["Succeeded", "Failed", "Cancelled"] },
      { key: "message", label: "Message", type: "textarea" },
  ],
  ```

**Delay** (`function_delay`) — a real `time.sleep`, capped, per your decision.
- `import time` added to `workflow_engine.py`'s imports (not currently imported).
- `MAX_DELAY_SECONDS = 300` module constant (5 minutes), alongside the existing `MAX_TOTAL_STEPS`.
- params: `{ "duration": number, "unit": "Seconds"|"Minutes"|"Hours" }`
- Engine:
  ```python
  UNIT_SECONDS = {"Seconds": 1, "Minutes": 60, "Hours": 3600}
  duration = float(params.get("duration") or 0)
  unit = params.get("unit", "Seconds")
  seconds = duration * UNIT_SECONDS.get(unit, 1)
  if seconds > MAX_DELAY_SECONDS:
      raise WorkflowRunError(f"Delay of {seconds:.0f}s exceeds the {MAX_DELAY_SECONDS}s cap (workflows run synchronously inside one request).")
  if self.dry_run:
      return f"[DRY RUN] Would delay {duration} {unit}", None
  time.sleep(max(seconds, 0))
  return f"Delayed {duration} {unit}", None
  ```
- Field schema: `function_delay: [{ key: "duration", label: "Duration", type: "number", placeholder: "5" }, { key: "unit", label: "Unit", type: "select", options: ["Seconds", "Minutes", "Hours"] }]`

**Delay Until** (`function_delay_until`) — same cap, computed against a target ISO8601 timestamp. A timestamp already in the past does not error — it just continues immediately, matching Power Automate's own behavior.
- `from datetime import datetime` added to imports.
- params: `{ "timestamp": string }` (ISO8601; a trailing `Z` is normalized to `+00:00` before `fromisoformat`, since `Z` isn't accepted by `datetime.fromisoformat` on all supported Python versions)
- Engine:
  ```python
  raw = self._substitute_tokens(params.get("timestamp", "")).strip()
  if not raw:
      raise WorkflowRunError("Delay Until requires a timestamp.")
  try:
      target = datetime.fromisoformat(raw.replace("Z", "+00:00"))
  except ValueError as e:
      raise WorkflowRunError(f"Delay Until: invalid ISO8601 timestamp: {e}")
  now = datetime.now(target.tzinfo) if target.tzinfo else datetime.now()
  seconds = (target - now).total_seconds()
  if seconds <= 0:
      return f"Target timestamp {raw} already passed; continuing immediately.", None
  if seconds > MAX_DELAY_SECONDS:
      raise WorkflowRunError(f"Delay Until is {seconds:.0f}s away, exceeding the {MAX_DELAY_SECONDS}s cap.")
  if self.dry_run:
      return f"[DRY RUN] Would delay until {raw}", None
  time.sleep(seconds)
  return f"Delayed until {raw}", None
  ```
- Field schema: `function_delay_until: [{ key: "timestamp", label: "Timestamp (ISO8601)", type: "text", mono: true, placeholder: "2026-08-01T14:00:00" }]`

## Part 4 — Data Operations (array family)

All use `_parse_json_array(node_id, friendly_name)` from the shared mechanics section above unless noted.

| tool_id | params | Engine behavior |
|---|---|---|
| `function_filter_array` | `{ "condition": string }` | Reuses the **existing** `_eval_condition_expression` safe AST evaluator (already powering the Conditions node) — no new expression engine. For each item, namespace = `dict(item)` if `item` is a dict else `{}`, plus `namespace["item"] = item` always. Keeps items where the condition evaluates true. Output: `json.dumps([...], indent=2)`. |
| `function_select` | `{ "columns": string }` (JSON text: `{"outputKey": "dotted.path", ...}`) | For each item, builds `{out_key: self._dotted_get(item, path) for out_key, path in columns.items()}`. Output: `json.dumps([...], indent=2)`. |
| `function_join` | `{ "field": string (optional), "separator": string }` | `values = [str(self._dotted_get(item, field) if field else item) for item in arr]`; output is the joined **string** (not JSON — matches Power Automate's Join, which produces text), `separator.join(values)`. |
| `function_sort` | `{ "field": string (optional), "direction": "asc"\|"desc" }` | `sorted(arr, key=lambda item: self._dotted_get(item, field) if field else item, reverse=(direction == "desc"))`, wrapped in `try/except TypeError` raising `WorkflowRunError("Sort: items aren't consistently comparable ...")` for mixed-type arrays. Output: `json.dumps([...], indent=2)`. |
| `function_union` | `{ "key": string (optional) }` | Uses `_direct_predecessor_texts(node_id)` (existing helper), **not** `_gather_upstream_text` — each predecessor's own array must stay separate before merging. Requires ≥2 predecessors (`WorkflowRunError` otherwise). Each predecessor text is independently `json.loads`'d and validated as a list (error names which predecessor by index if invalid). Dedup key is `json.dumps(self._dotted_get(item, key) if key else item, sort_keys=True)`; first occurrence wins, order preserved across predecessors in edge order. |
| `function_chunk` | `{ "size": number }` | `size = int(params.get("size") or 0)`; `WorkflowRunError` if `size <= 0`. `[arr[i:i+size] for i in range(0, len(arr), size)]`. |
| `function_length` | none | `str(len(arr))` — plain string, not JSON (Power Automate's Length returns a bare number too). |
| `function_first` | none | `WorkflowRunError("First: array is empty.")` if empty, else `self._array_item_to_text(arr[0])` (see below). |
| `function_last` | none | Same as First with `arr[-1]`. |
| `function_take` | `{ "count": number }` | `json.dumps(arr[:max(int(params.get("count") or 0), 0)], indent=2)`. |
| `function_skip` | `{ "count": number }` | `json.dumps(arr[max(int(params.get("count") or 0), 0):], indent=2)`. |
| `function_create_csv_table` | `{ "columns": string }` (optional, newline-separated; blank = keys of `arr[0]` in first-seen order, or `[]` if `arr` is empty) | Every item must be a dict (`WorkflowRunError` naming the first offending index otherwise). `csv.DictWriter` (stdlib `csv` + `io.StringIO`, `extrasaction="ignore"`, `restval=""`) writes header + rows; returns the buffer text. Empty `arr` returns `""`. |
| `function_create_html_table` | same `columns` param as CSV | Hand-built `<table>` string (no new dependency): `<tr><th>...</th></tr>` header from the resolved column list, one `<tr><td>...</td></tr>` per item, every cell value passed through stdlib `html.escape`. |

`function_first`/`function_last` use one more small helper, for the same reason `Length`/`Join` return plain text instead of a quoted JSON string for scalar results — so `{{first_item}}` substituted into a later prompt reads as `Alice`, not `"Alice"`:
```python
def _array_item_to_text(self, value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2)
    return "" if value is None else str(value)
```
Object/array items still round-trip through JSON (so a later Parse JSON node still works on them); only bare scalars (string/number/bool/null) get the unquoted plain-text treatment.

New stdlib imports in `workflow_engine.py`: `csv`, `io`, `html` (module name `html` doesn't collide with anything else in this file).

Field schemas (all fit the declarative `FUNCTION_FIELD_SCHEMAS` table, no bespoke panels):
```js
function_filter_array: [{ key: "condition", label: "Condition (e.g. status == 'active' and total > 100)", type: "text", mono: true }],
function_select: [{ key: "columns", label: 'Columns (JSON: {"outputKey": "dotted.path"})', type: "textarea", mono: true, placeholder: '{"name": "user.name"}' }],
function_join: [
    { key: "field", label: "Field (optional dotted path; blank = whole item)", type: "text", mono: true },
    { key: "separator", label: "Separator", type: "text", mono: true, placeholder: ", " },
],
function_sort: [
    { key: "field", label: "Field (optional dotted path; blank = whole item)", type: "text", mono: true },
    { key: "direction", label: "Direction", type: "select", options: ["asc", "desc"] },
],
function_union: [{ key: "key", label: "Dedup Key (optional dotted path; blank = whole item)", type: "text", mono: true }],
function_chunk: [{ key: "size", label: "Chunk Size", type: "number", placeholder: "10" }],
function_length: [],
function_first: [],
function_last: [],
function_take: [{ key: "count", label: "Count", type: "number", placeholder: "5" }],
function_skip: [{ key: "count", label: "Count", type: "number", placeholder: "5" }],
function_create_csv_table: [{ key: "columns", label: "Columns (optional, one per line; blank = auto-detect from first row)", type: "textarea", mono: true }],
function_create_html_table: [{ key: "columns", label: "Columns (optional, one per line; blank = auto-detect from first row)", type: "textarea", mono: true }],
```

## Part 5 — Frontend: `select` field type

`FUNCTION_FIELD_SCHEMAS`' renderer/reader currently only handles `text`/`number`/`textarea` (`workflow-builder.html:570-604`). Four new node types need a dropdown (`function_http.method`, `function_terminate.status`, `function_delay.unit`, `function_sort.direction`), so one addition is made once and reused by all four:

- `renderGenericFunctionFields` (`workflow-builder.html:570-592`): add an `f.type === "select"` branch alongside the existing `textarea` branch, rendering `<select data-panel-field="${f.key}">` with `f.options.map(o => \`<option value="${o}" ${o === val ? "selected" : ""}>${o}</option>\`)`.
- `readGenericFunctionFields` (`workflow-builder.html:594-604`): **no change needed** — `el.value` already reads correctly off a `<select>` element the same as an `<input>`.

## Part 6 — Registries & icons (`server.py`)

- `FUNCTIONS_REGISTRY` (`server.py:203-276`): one new entry per tool_id above (`title`, `description`, `"model": None`), following the existing entry shape.
- `TOOL_FA_ICON_MAP` (`server.py:440-483`): one Font Awesome glyph per new tool_id. Per this file's own stated convention ("checked against the actual installed all.min.css, not guessed" — `server.py:367`), pick icon names during implementation by grepping the vendored `templates/static/vendor/fontawesome` CSS for candidates (e.g. something http/globe-shaped for HTTP, a clock/hourglass for Delay, a filter funnel for Filter Array, a table glyph for the two Create Table nodes) rather than assuming FA6 Free class names sight-unseen.
- `DEFAULT_FA_ICON` (`"fa-code"`) already covers any of these left unassigned, so this is a polish step, not a blocker.

## Testing

Following this repo's convention (`00_System/test_workflow_engine_conditions.py`, `test_workflow_engine_tokens.py` — co-located `test_<module>.py`, plain `assert`, run directly, no fixtures/pytest-only features):

New file `00_System/test_workflow_engine_flow_and_data_ops.py`:
1. **Compose** — `{{label}}` substitution happens; a literal value with no tokens passes through unchanged.
2. **Parse JSON** — valid JSON passes through re-serialized; invalid JSON raises `WorkflowRunError`; missing required key raises `WorkflowRunError` naming it; present required keys pass.
3. **HTTP** — dry-run returns a `[DRY RUN]` string without importing `requests`' network path; a mocked `requests.request` (via `unittest.mock.patch`) returning a 200 produces the expected `{status_code, headers, body}` JSON; a mocked 404 raises `WorkflowRunError` containing the status code.
4. **Response** — output passes through unchanged; `run()`'s result dict contains it under `responses`.
5. **Terminate** — a graph with `Terminate(status="Failed")` wired before a later node: `run()` stops before that later node executes, `result["terminated"] == {"status": "Failed", "message": ...}`, and `result["success"] is False`. Same test repeated for `status="Succeeded"` asserting `result["success"] is True`.
6. **Delay** — dry-run returns immediately (no real sleep) for a 1-hour request; a live-mode request over the 300s cap raises `WorkflowRunError` without sleeping; a live-mode request under the cap actually sleeps roughly the requested duration (small value, e.g. 0.1s, to keep the test fast).
7. **Delay Until** — a past timestamp returns immediately with no sleep; a future timestamp beyond the cap raises `WorkflowRunError`.
8. **Filter Array / Select / Join / Sort / Union / Chunk / Length / First / Last / Take / Skip / Create CSV Table / Create HTML Table** — one happy-path case each against a small fixed JSON array, plus: invalid-JSON-input raises `WorkflowRunError` (shared `_parse_json_array` path, tested once generically is enough — doesn't need repeating per node type), empty-array edge case for First/Last (raises) and Length/Take/Skip (doesn't).

Client-side (`select` field type rendering/reading, new panel schemas) has no browser test harness in this repo (same as every other panel, per the Conditions design doc) — verified by running the app directly and configuring one of each new node type, not claimed from reading the code alone.

## Explicitly out of scope

- **Variables** (`Initialize`/`Set`/`Increment`/`Append Variable`) and **Apply to Each**/**Do Until** — these need a real mutable variable store (distinct from the current per-node-label `self.context`) and a loop-execution model (run a subgraph N times over a collection, or until a condition holds) that the engine's single-pass DAG walker doesn't have. Separate design, separate slice.
- **Scope, Condition/Switch, Approval** — already exist as `container`, `function_logic_gate`/`function_conditions`, and `human_review_checkpoint` respectively. No changes made to any of them here.
- **Google Workspace connectors, AI capability stub actions (sentiment/translation/OCR/etc.), M365 connectors not yet built (Planner, Forms, Dataverse, Word Online populate, Power BI execute-query)** — separate slices per the earlier scoping conversation.
- **HTTP action authentication helpers** (OAuth/API-key connection references) — this HTTP node is the generic, credential-less REST requester only, same as Power Automate's own "HTTP" (as opposed to "HTTP with Azure AD" or a licensed connector). A user supplies their own `Authorization` header manually via the Headers field.
- **Retry policies, exponential backoff, or per-node timeout configuration** for HTTP/Delay — fixed constants (30s HTTP timeout, 300s Delay cap) for this slice.
- **Publishing workflows as externally-callable APIs** — Response marks a declared output in the run log/result only; there is still no mechanism for an external caller to trigger a workflow and receive that response synchronously. Revisit if that capability is ever built.
- **Migrating any existing saved workflow** — none of these tool_ids exist yet, so there's nothing to migrate.
