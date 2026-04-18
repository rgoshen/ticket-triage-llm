# Phase 5 — Dashboard, Traces, and Live Monitoring: Design Spec

## Overview

Phase 5 implements the three remaining UI tabs (Metrics, Traces, Experiments) and the metrics service layer that powers them. All data is computed from the SQLite `traces` table on the fly (ADR 0005). Monitoring is visually distinct from benchmarking (ADR 0009).

### Scope

**Tier 1 (must-have for demo):**
- Metrics tab with Benchmark Results and Live Metrics sections
- Traces tab with filtering and click-to-inspect detail
- Metrics service layer (aggregation logic over trace repo)
- Trace repo stub implementations (`get_traces_by_provider`, `get_traces_since`, `get_distinct_run_ids`)
- App.py wiring: outer `gr.Tabs` wrapping all four tabs
- `docs/future-improvements.md` updates for deferred items

**Tier 2 (strong-to-have):**
- Experiments tab with side-by-side experiment comparison

**Deferred to future-improvements.md:**
- Category-distribution drift indicator
- Log-based alerts (`WARN [monitoring] threshold_breached: ...`)

### Not in scope
- No new database tables (ADR 0005)
- No external charting libraries (Gradio built-ins only)
- No prompt v2 (Phase 6)

---

## 1. Metrics Service Layer

**File:** `src/ticket_triage_llm/services/metrics.py`

A stateless aggregation layer over the trace repository. No state of its own — pure functions that query traces and compute summaries.

### Functions

#### `list_run_ids(trace_repo: TraceRepository) -> list[dict]`

Queries distinct `run_id` values from traces (excluding `None`). Returns a list of dicts with:
- `run_id: str`
- `model: str`
- `timestamp: str` (earliest trace in that run)
- `ticket_count: int`

This powers the Metrics tab's run selector and the Experiments tab's grouping.

**Implementation:** New method `get_distinct_run_ids()` on the trace repo that executes:
```sql
SELECT run_id, model, MIN(timestamp) as first_ts, COUNT(*) as ticket_count
FROM traces
WHERE run_id IS NOT NULL
GROUP BY run_id
ORDER BY first_ts DESC
```

#### `get_live_summary(trace_repo: TraceRepository, window_hours: int | None) -> dict`

Queries recent traces where `run_id IS NULL` (live traffic only). If `window_hours` is None, includes all live traffic.

Returns:
- `total_requests: int`
- `success_rate: float`
- `avg_latency_ms: float`
- `p50_latency_ms: float`
- `p95_latency_ms: float`
- `retry_rate: float`
- `error_rate: float`

**Implementation:** Uses `get_traces_since()` if window specified, otherwise `get_all_traces()`, then filters to `run_id is None` and computes stats in Python.

#### `group_runs_by_experiment(run_ids: list[dict]) -> dict[str, list[dict]]`

Parses the prefix from each `run_id` string and clusters them into experiment groups:
- `e1-*` -> "E1: Model Size Comparison"
- `e2-*` -> "E2: Model Size vs Engineering Controls"
- `e3-*` -> "E3: Validation Impact"
- `e4-*` -> "E4: Prompt Comparison"
- `adv-*` -> "Adversarial: Injection Defense"

Within each group, runs are sorted by timestamp (newest first).

### Reuse of existing summarizer

The existing `summarize_run()` in `eval/runners/summarize_results.py` computes `ModelMetrics` from a run_id + ground truth tickets. The metrics service calls it directly — no duplication. The Experiments tab will also need the dataset loaded for ground-truth correlation.

---

## 2. Trace Repository Additions

**File:** `src/ticket_triage_llm/services/trace.py`

### Implement stubbed methods

#### `get_traces_by_provider(provider: str) -> list[TraceRecord]`
```sql
SELECT * FROM traces WHERE provider = ? ORDER BY timestamp DESC
```

#### `get_traces_since(since: datetime) -> list[TraceRecord]`
```sql
SELECT * FROM traces WHERE timestamp >= ? ORDER BY timestamp DESC
```

### New method

#### `get_distinct_run_ids() -> list[dict]`
```sql
SELECT run_id, model, MIN(timestamp) as first_ts, COUNT(*) as ticket_count
FROM traces WHERE run_id IS NOT NULL
GROUP BY run_id ORDER BY first_ts DESC
```

Returns list of dicts (not TraceRecord — this is a summary query).

### Protocol update

Add `get_distinct_run_ids()` to the `TraceRepository` Protocol in `storage/trace_repo.py`.

---

## 3. Metrics Tab UI

**File:** `src/ticket_triage_llm/ui/metrics_tab.py`

**Build function:** `build_metrics_tab_content(trace_repo: TraceRepository) -> None`

Builds components into the current `gr.Tab` context (does not return a Blocks object — see Section 6 for the outer tabbed layout).

### Benchmark Results section (top)

- **Run selector dropdown** — populated from `list_run_ids()`. Display format: `"{run_id} — {model} ({ticket_count} tickets)"`. Refresh button beside it.
- **KPI cards row** — `gr.Markdown` blocks showing: Category Accuracy, JSON Validity, Schema Pass Rate, p95 Latency, Retry Rate, Success Rate (X/Y). Populated from `summarize_run()` for the selected run_id.
- **Comparison table** — `gr.Dataframe` with one row per model in the run. Columns: Model, Cat Acc, Sev Acc, Route Acc, JSON Valid %, Schema Pass %, Retry %, p50 ms, p95 ms, Tok/s, Success.

**Event flow:** User selects a run_id from dropdown -> calls `summarize_run(run_id, tickets, trace_repo)` -> populates KPI cards and table. Refresh button re-queries `list_run_ids()` to pick up new runs. The `tickets` (ground truth) are loaded once at tab build time from `data/normal_set.jsonl` via `load_dataset()`.

**Edge case:** If no eval runs exist, show "No benchmark runs found. Run an experiment to see results here."

### Live Metrics section (bottom)

- **Window selector** — Radio buttons: 1h, 24h, 7d, All
- **KPI cards** — Total Requests, Success Rate, Avg Latency, p50 Latency, p95 Latency, Retry Rate
- **Refresh button** — re-queries for the selected window

**Edge case:** If no live traffic exists, show "No live traffic recorded yet. Submit tickets through the Triage tab to see live metrics."

---

## 4. Traces Tab UI

**File:** `src/ticket_triage_llm/ui/traces_tab.py`

**Build function:** `build_traces_tab_content(trace_repo: TraceRepository) -> None`

Builds components into the current `gr.Tab` context (see Section 6).

### Filter bar (top row)

Dropdowns for:
- **Provider** — populated from distinct providers in traces, plus "All"
- **Validation status** — All, valid, valid_after_retry, invalid, skipped
- **Status** — All, success, failure
- **Limit** — 25, 50, 100

Plus a **Refresh** button.

### Trace list (middle)

`gr.Dataframe` with columns: Timestamp, Model, Status, Validation, Latency (ms), Tokens, Retry, Guardrail.

Sorted by timestamp DESC. Clicking a row populates the detail pane.

**Filtering:** Query `get_recent_traces(limit)` and filter in Python. The dataset is small enough (hundreds of traces) that this is simpler than building parameterized SQL for every combination.

### Trace detail pane (bottom)

`gr.Accordion` (collapsed by default, opens on row click) or a dedicated column. Displays:

- **Metadata:** request_id, run_id, ticket_id, model, provider, prompt_version
- **Timing:** latency_ms, tokens (in/out/total), tokens/sec, estimated_cost
- **Pipeline:** guardrail_result, matched_rules, validation_status, retry_count, failure_category
- **Content:** ticket_body (first 500 chars), raw_model_output (first 1000 chars), triage_output_json (formatted JSON)

---

## 5. Experiments Tab UI

**File:** `src/ticket_triage_llm/ui/experiments_tab.py`

**Build function:** `build_experiments_tab_content(trace_repo: TraceRepository) -> None`

Builds components into the current `gr.Tab` context (see Section 6).

### Experiment selector

Dropdown with options:
- E1: Model Size Comparison
- E2: Model Size vs Engineering Controls
- E3: Validation Impact
- E4: Prompt Comparison
- Adversarial: Injection Defense

Populated from `group_runs_by_experiment()`. Only shows experiments that have at least one run.

### Experiment display (per selection)

- **Description** — one-line markdown explaining what the experiment tests
- **Comparison table** — `gr.Dataframe`, one row per model/config. Same columns as Metrics tab benchmark table.
- For **adversarial** runs: display a different table with columns: Model, Tickets, Guardrail Blocked, Reached Model, Model Complied, Validation Caught, Residual Risk.

### Ground truth loading

The summarizer needs ground truth tickets. The experiments tab loads the dataset from `data/normal_set.jsonl` (or `data/adversarial_set.jsonl` for adversarial runs) at tab build time. Path comes from a constant or the dataset module's default.

### E2 composition

E2 is composed from E1 + E3 data via the existing `compose_e2()` function. The tab calls this when the user selects E2, using the latest E1 and E3 runs.

### Edge case

If no experiment runs exist for a category, show "No runs found for this experiment."

---

## 6. App.py Wiring

**File:** `src/ticket_triage_llm/app.py`

### Change: outer tabbed layout

Currently `build_triage_tab()` returns a standalone `gr.Blocks` mounted at `/`. The change:

1. Create an outer `gr.Blocks` with `gr.Tabs`
2. Each tab contains one of: Triage, Metrics, Traces, Experiments
3. Mount the outer Blocks at `/`

```python
with gr.Blocks(title="Ticket Triage LLM") as gradio_app:
    with gr.Tabs():
        with gr.Tab("Triage"):
            build_triage_tab_content(registry, trace_repo, ...)
        with gr.Tab("Metrics"):
            build_metrics_tab_content(trace_repo)
        with gr.Tab("Traces"):
            build_traces_tab_content(trace_repo)
        with gr.Tab("Experiments"):
            build_experiments_tab_content(trace_repo)
```

This means `build_triage_tab` changes from returning a `gr.Blocks` to building content inside a `gr.Tab` context. The other build functions follow the same pattern — they add components to the current Blocks context rather than returning standalone Blocks.

### Dependencies passed to new tabs

Only `trace_repo` is needed. The metrics service is stateless and imported directly by the tab modules.

---

## 7. Deferred Items — future-improvements.md

Two items to add, matching the existing entry structure:

### Category-distribution drift indicator

- **What it would add:** A chart in the Live Metrics section showing the distribution of assigned categories over time, flagging when a single category dominates recent traffic (>70%) as a signal that input distribution or model behavior has shifted.
- **Why it's deferred:** Requires enough live traffic to produce a meaningful distribution. During a 5-minute demo, the volume of live requests is too low to show drift. The chart would render as single bars or be empty, undermining rather than supporting the demo narrative.
- **What was done instead:** The Metrics tab shows rolling aggregate metrics (success rate, latency, retry rate) that are meaningful even at low traffic volumes. Category distribution can be inferred from the Traces tab's filterable list.
- **Estimated effort to add:** A few hours. The trace data already includes category in `triage_output_json`. Implementation is a time-bucketed aggregation query and a Gradio bar chart.

### Log-based alerting

- **What it would add:** Structured log warnings (`WARN [monitoring] threshold_breached: p95_latency=6200ms > limit=5000ms`) when configured thresholds are crossed (p95 latency > 5s, retry rate > 20%, single category > 70%).
- **Why it's deferred:** Log-based alerts are invisible to the audience during a demo unless specifically surfaced in the UI. The monitoring value is real but the demo impact is low compared to the visible dashboard components.
- **What was done instead:** The Live Metrics section shows the same threshold-relevant numbers (p95 latency, retry rate) as KPI cards, making threshold violations visually apparent without log parsing.
- **Estimated effort to add:** A few hours. The metrics service already computes the values; adding threshold checks and structured log output is straightforward. See ADR 0009 for the threshold values and log format.

---

## 8. Testing Approach

### TDD (service/business logic)
- Metrics service: `list_run_ids()`, `get_live_summary()`, `group_runs_by_experiment()`
- Trace repo: `get_traces_by_provider()`, `get_traces_since()`, `get_distinct_run_ids()`

### Judgment-based (UI)
- Tab build functions — tested by running the app and verifying in browser
- App.py tabbed wiring

### User testing
- After each tab is functional, run the app and verify in browser before moving to the next tab
- Test with real eval data in `data/traces.db` (from Phase 3/4 runs)
- Test edge cases: no eval runs, no live traffic, empty filters
