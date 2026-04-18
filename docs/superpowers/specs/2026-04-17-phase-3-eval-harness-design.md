# Phase 3 — Evaluation Harness + Benchmark Run

Design spec for the Phase 3 eval harness. Covers schema changes, runner architecture, summarizer logic, result storage, and testing strategy.

**PLAN.md mapping:** Phase 3
**Branch:** `feature/phase-3-eval-harness`
**Dependencies:** Phase F (foundation), Phase 1 (service layer), Phase 2 (retry + guardrail for E3)

---

## 1. Schema Changes

### TraceRecord

Add one new optional field:

- `ticket_id: str | None = None` — set by eval runners when processing labeled data, null for live Triage-tab and API traffic.

### traces table (SQLite)

Add one new nullable column and index:

```sql
ALTER TABLE traces ADD COLUMN ticket_id TEXT;
CREATE INDEX IF NOT EXISTS idx_traces_ticket_id ON traces(ticket_id);
```

Applied via `init_schema()` in `storage/db.py` (add column to CREATE TABLE IF NOT EXISTS).

### run_triage() signature

Add three new parameters with defaults that preserve existing behavior:

```python
def run_triage(
    ticket_body: str,
    ticket_subject: str,
    provider: LlmProvider,
    prompt_version: str,
    trace_repo: TraceRepository,
    guardrail_max_length: int = 10_000,
    skip_validation: bool = False,    # NEW — E3 no-validation mode
    run_id: str | None = None,        # NEW — eval run grouping key
    ticket_id: str | None = None,     # NEW — ground truth join key
) -> tuple[TriageResult, TraceRecord]:
```

**`skip_validation=True` behavior:**
1. Guardrail still runs (it's pre-LLM, independent of validation).
2. Provider is called normally.
3. Instead of `validate_or_retry()`, does a best-effort `parse_json()` + `validate_schema()` for the trace record only.
4. If parse+schema succeeds, returns `TriageSuccess` with `retry_count=0`.
5. If parse fails, returns `TriageFailure(category="parse_failure", ...)` with `retry_count=0`.
6. If schema fails, returns `TriageFailure(category="schema_failure", ...)` with `retry_count=0`.
7. `validation_status` is set to `"skipped"` on the trace regardless of outcome.
8. No retry is attempted.

**`run_id` and `ticket_id`** are passed through to the `TraceRecord` constructor.

### SqliteTraceRepository

- `save_trace()` — include `ticket_id` in the INSERT statement.
- `get_traces_by_run(run_id)` — implement (currently `NotImplementedError`).
- `get_all_traces()` — implement (currently `NotImplementedError`).

---

## 2. Data Structures

### eval/datasets.py (new module)

```python
@dataclass
class GroundTruth:
    category: str
    severity: str
    routing_team: str
    escalation: bool

@dataclass
class TicketRecord:
    id: str
    subject: str
    body: str
    ground_truth: GroundTruth
```

`load_dataset(path: Path) -> list[TicketRecord]` — reads a JSONL file, returns typed records.

### eval/results.py (new module)

```python
@dataclass
class ModelMetrics:
    model: str
    run_id: str
    category_accuracy: float
    severity_accuracy: float
    routing_accuracy: float
    escalation_accuracy: float
    json_valid_rate: float
    schema_pass_rate: float
    retry_rate: float
    retry_success_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    avg_tokens_per_second: float | None
    avg_tokens_input: float
    avg_tokens_output: float
    avg_tokens_total: float
    total_tickets: int
    successful_tickets: int

@dataclass
class ExperimentSummary:
    experiment_id: str          # "E1", "E2", "E3", "E4"
    experiment_name: str
    date: str
    dataset_size: int
    prompt_version: str
    model_metrics: list[ModelMetrics]
```

Both dataclasses support `asdict()` for JSON serialization to `data/phase3/`.

---

## 3. Eval Runner Architecture

### Shared infrastructure: eval/runners/common.py (new module)

```python
def run_experiment_pass(
    tickets: list[TicketRecord],
    provider: LlmProvider,
    prompt_version: str,
    trace_repo: TraceRepository,
    run_id: str,
    skip_validation: bool = False,
    guardrail_max_length: int = 10_000,
) -> list[TraceRecord]:
```

Iterates tickets, calls `run_triage()` per ticket (passing `run_id`, `ticket_id`, `skip_validation`), collects and returns traces. Logs progress to stdout (`[{i}/{n}] ticket {ticket_id} — {status} — {latency_ms:.0f}ms`).

### E1 — run_local_comparison.py

**Function:** `run_local_comparison(providers: list[LlmProvider], tickets: list[TicketRecord], trace_repo: TraceRepository) -> ExperimentSummary`

- Runs full normal set (35 tickets) through each of 3 providers (2B, 4B, 9B) with `prompt_version="v1"`, full validation.
- One `run_id` per model: `e1-{model_tag}-{timestamp}` (e.g., `e1-2b-20260417T1430`).
- Returns one `ExperimentSummary` with `experiment_id="E1"` and 3 `ModelMetrics` entries.

### E3 — run_validation_impact.py

**Function:** `run_validation_impact(provider_4b: LlmProvider, provider_9b: LlmProvider, tickets: list[TicketRecord], trace_repo: TraceRepository) -> tuple[ExperimentSummary, str]`

Three passes:
1. 4B with full validation — `run_id`: `e3-4b-validated-{timestamp}`
2. 4B with `skip_validation=True` — `run_id`: `e3-4b-skipped-{timestamp}`
3. 9B with `skip_validation=True` — `run_id`: `e2-9b-noval-{timestamp}` (the E2 data point)

Returns the E3 summary (2 `ModelMetrics` for the 4B comparison) and the E2 9B no-validation `run_id` (consumed by the summarizer for E2 composition).

### E4 — run_prompt_comparison.py

**Function:** `run_prompt_comparison(provider: LlmProvider, tickets: list[TicketRecord], trace_repo: TraceRepository) -> ExperimentSummary`

- Runs normal set with `prompt_version="v1"` (and `"v2"` when available after Phase 6).
- Phase 3 run is partial: v1 only. Re-run after Phase 6 adds v2.
- `run_id`: `e4-v1-{timestamp}` (and `e4-v2-{timestamp}` later).

### summarize_results.py

**Core function (TDD target):**

```python
def summarize_run(
    run_id: str,
    tickets: list[TicketRecord],
    trace_repo: TraceRepository,
) -> ModelMetrics:
```

1. Fetches traces by `run_id`.
2. For each trace with a `ticket_id`, looks up the ground truth from `tickets`.
3. Parses `triage_output_json` and compares `category`, `severity`, `routing_team` (via `routingTeam` alias), `escalation` against ground truth.
4. Computes all metrics in `ModelMetrics`.

**Accuracy calculation details:**
- Only traces with `status="success"` AND a matching `ticket_id` in the dataset contribute to accuracy. Failed traces (parse/schema/guardrail failures) count as incorrect for all accuracy fields.
- `json_valid_rate` = traces where `parse_json(raw_model_output)` is not None / total traces.
- `schema_pass_rate` = traces where `validation_status` in (`"valid"`, `"valid_after_retry"`) / total traces.
- `retry_rate` = traces where `retry_count > 0` / total traces.
- `retry_success_rate` = traces where `retry_count > 0` AND `status="success"` / traces where `retry_count > 0`.
- Latency percentiles computed from `latency_ms` across all traces in the run.

**E2 composition:**

```python
def compose_e2(
    e1_summary: ExperimentSummary,
    e2_9b_noval_run_id: str,
    tickets: list[TicketRecord],
    trace_repo: TraceRepository,
) -> ExperimentSummary:
```

Picks the 2B `ModelMetrics` from E1 (smallest model + full validation) and computes the 9B-no-validation `ModelMetrics` from the dedicated run.

**CLI `__main__` block:**
- Accepts `--db-path` and `--dataset-path` arguments.
- Prints formatted tables to stdout.
- Writes JSON summaries to `data/phase3/`.

---

## 4. Result Storage

### data/phase3/ (new directory, mirroring data/phase0/)

- `data/phase3/e1-local-comparison.json` — E1 ExperimentSummary
- `data/phase3/e2-size-vs-controls.json` — E2 ExperimentSummary (composed)
- `data/phase3/e3-validation-impact.json` — E3 ExperimentSummary
- `data/phase3/e4-prompt-comparison.json` — E4 ExperimentSummary (partial, v1 only)

Each file is the `dataclasses.asdict()` JSON serialization of the corresponding `ExperimentSummary`.

### SQLite traces

All traces are also persisted in the `traces` table with `run_id` tags, so the Metrics/Experiments tabs (Phase 5) can query them later.

---

## 5. docs/evaluation-checklist.md Updates

After each experiment completes, the runner fills in the corresponding table in the Phase 3 section:

- E1: "Experiment 1: Model Size Comparison" table
- E2: "Experiment 2: Model Size vs Engineering Controls" table
- E3: "Experiment 3: Validation Impact" table
- E4: "Experiment 4: Prompt Comparison" table (v1 row only)

After all experiments, write a "Phase 3 Observations" subsection per CLAUDE.md requirements, covering:
1. Unexpected findings
2. Patterns in the data
3. Implementation implications
4. Cost or performance implications
5. Limitations at this sample size

---

## 6. Phase Exit Checklist (docs updated at phase completion)

- `SUMMARY.md` — new Phase 3 entry
- `TODO.md` — mark Phase 3 complete, adjust downstream phases if needed
- `README.md` — update Commands section (eval runner commands now functional)
- `docs/evaluation-checklist.md` — experiment tables + Phase 3 Observations filled in

---

## 7. Testing Strategy

### TDD-required (service and business logic)

- **`summarize_run()` aggregation** — given known traces + ground truth dataset, verify accuracy calculations, latency percentile math, retry rate, retry success rate, token averages.
- **`compose_e2()`** — verify it picks the 2B row from E1 and computes the 9B-no-validation row correctly.
- **Ground truth matching** — verify `ticket_id` join: traces with matching IDs get accuracy scored, traces without IDs are handled gracefully.
- **`run_triage()` with `skip_validation=True`** — verify it sets `validation_status="skipped"`, does not call `validate_or_retry()`, still produces a valid trace, handles parse success and failure cases.
- **`load_dataset()`** — verify JSONL parsing, field mapping, error on malformed lines.
- **`run_experiment_pass()`** — verify it calls `run_triage()` per ticket with correct args, collects traces, passes through `run_id`/`ticket_id`/`skip_validation`.
- **`SqliteTraceRepository.get_traces_by_run()`** — verify it filters by `run_id`.
- **`SqliteTraceRepository.get_all_traces()`** — verify it returns all rows.

### Judgment-based (not strict TDD)

- Runner CLI entry points (`__main__` blocks)
- JSON file output formatting
- Progress logging format
- evaluation-checklist.md formatting

### Test fakes

- Reuse existing `FakeProvider` / `FakeTraceRepo` from Phase 1/2 tests.
- Add `GroundTruthAlignedProvider` — a fake that, given a `ticket_id`, returns `triage_output_json` matching the ground truth for that ticket. This makes accuracy calculations deterministic in unit tests.
- Add `PartiallyCorrectProvider` — a fake that returns correct category but wrong severity for specific ticket IDs, so accuracy tests can verify partial-match scoring.

---

## 8. What This Phase Does NOT Include

- **Prompt v2** — E4 runs v1 only. v2 is Phase 6.
- **Adversarial evaluation** — the adversarial set is not run in Phase 3. Phase 4.
- **Dashboard/UI** — no Metrics/Experiments tab work. Phase 5.
- **Checklist observation authoring** — observations are written after the real experiments are run on Ollama, not during the code-build portion of Phase 3.
