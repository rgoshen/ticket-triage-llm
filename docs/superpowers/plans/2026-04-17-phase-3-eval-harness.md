# Phase 3 — Evaluation Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the eval harness that runs four experiments (E1–E4) against the triage pipeline, stores results as tagged traces, computes accuracy metrics against ground truth, and writes summaries to `data/phase3/`.

**Architecture:** Eval runners are thin CLI wrappers over testable core functions. Each runner calls `run_experiment_pass()` (shared loop) which calls `run_triage()` per ticket with `run_id`/`ticket_id` set. The summarizer computes `ModelMetrics` by joining traces on `ticket_id` to ground truth from the JSONL dataset. Results serialize to JSON in `data/phase3/`.

**Tech Stack:** Python 3.11+, pytest, pydantic, sqlite3, dataclasses

**Spec:** `docs/superpowers/specs/2026-04-17-phase-3-eval-harness-design.md`

---

## File Map

### New files

| File | Responsibility |
|---|---|
| `src/ticket_triage_llm/eval/datasets.py` | `GroundTruth`, `TicketRecord` dataclasses + `load_dataset()` |
| `src/ticket_triage_llm/eval/results.py` | `ModelMetrics`, `ExperimentSummary` dataclasses |
| `src/ticket_triage_llm/eval/runners/common.py` | `run_experiment_pass()` shared loop |
| `tests/unit/test_datasets.py` | Tests for `load_dataset()` |
| `tests/unit/test_summarize_results.py` | Tests for `summarize_run()`, `compose_e2()` |
| `tests/unit/test_eval_common.py` | Tests for `run_experiment_pass()` |

### Modified files

| File | What changes |
|---|---|
| `src/ticket_triage_llm/schemas/trace.py` | Add `ticket_id: str \| None = None` field to `TraceRecord` |
| `src/ticket_triage_llm/storage/db.py` | Add `ticket_id TEXT` column to `CREATE TABLE` |
| `src/ticket_triage_llm/services/trace.py` | Add `ticket_id` to INSERT; implement `get_traces_by_run()`, `get_all_traces()` |
| `src/ticket_triage_llm/services/triage.py` | Add `skip_validation`, `run_id`, `ticket_id` params; skip-validation logic |
| `src/ticket_triage_llm/eval/runners/run_local_comparison.py` | E1 runner implementation |
| `src/ticket_triage_llm/eval/runners/run_validation_impact.py` | E3 runner + E2 data point |
| `src/ticket_triage_llm/eval/runners/run_prompt_comparison.py` | E4 runner (v1 only) |
| `src/ticket_triage_llm/eval/runners/summarize_results.py` | Summarizer: `summarize_run()`, `compose_e2()`, CLI |
| `tests/unit/test_triage_service.py` | Add `skip_validation` tests; update `FakeTraceRepo` |
| `tests/unit/test_sqlite_trace_repo.py` | Add `get_traces_by_run()`, `get_all_traces()`, `ticket_id` round-trip tests |

---

## Task 1: Add `ticket_id` to TraceRecord and traces table

**Files:**
- Modify: `src/ticket_triage_llm/schemas/trace.py:43-65`
- Modify: `src/ticket_triage_llm/storage/db.py:12-58`
- Modify: `src/ticket_triage_llm/services/trace.py:14-52`
- Test: `tests/unit/test_trace_record.py`
- Test: `tests/unit/test_sqlite_trace_repo.py`

- [ ] **Step 1: Write failing test for ticket_id on TraceRecord**

In `tests/unit/test_trace_record.py`, add:

```python
class TestTraceRecordTicketId:
    def test_ticket_id_defaults_to_none(self):
        trace = TraceRecord(
            request_id="req-1",
            timestamp=datetime(2026, 4, 17, tzinfo=UTC),
            model="qwen3.5:4b",
            provider="ollama:qwen3.5:4b",
            prompt_version="v1",
            ticket_body="test",
            guardrail_result="pass",
            validation_status="valid",
            latency_ms=100.0,
            status="success",
        )
        assert trace.ticket_id is None

    def test_ticket_id_can_be_set(self):
        trace = TraceRecord(
            request_id="req-2",
            timestamp=datetime(2026, 4, 17, tzinfo=UTC),
            model="qwen3.5:4b",
            provider="ollama:qwen3.5:4b",
            prompt_version="v1",
            ticket_body="test",
            guardrail_result="pass",
            validation_status="valid",
            latency_ms=100.0,
            status="success",
            ticket_id="n-001",
        )
        assert trace.ticket_id == "n-001"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_trace_record.py::TestTraceRecordTicketId -v`
Expected: FAIL — `ticket_id` is not a recognized field on `TraceRecord`.

- [ ] **Step 3: Add `ticket_id` to TraceRecord**

In `src/ticket_triage_llm/schemas/trace.py`, add after the `run_id` field (line 46):

```python
    ticket_id: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_trace_record.py::TestTraceRecordTicketId -v`
Expected: PASS

- [ ] **Step 5: Update traces table schema**

In `src/ticket_triage_llm/storage/db.py`, in the `CREATE TABLE IF NOT EXISTS traces` block, add after the `run_id TEXT,` line:

```python
            ticket_id TEXT,
```

And add a new index after the existing ones:

```python
        CREATE INDEX IF NOT EXISTS idx_traces_ticket_id
            ON traces(ticket_id);
```

- [ ] **Step 6: Update SqliteTraceRepository.save_trace() to include ticket_id**

In `src/ticket_triage_llm/services/trace.py`, update the INSERT column list and VALUES to include `ticket_id`. Add `ticket_id` right after `run_id` in both the column list and the values tuple:

Column list addition (after `run_id,`):
```python
                request_id, run_id, ticket_id, timestamp, model, provider,
```

Values tuple addition (after `trace.run_id,`):
```python
                trace.run_id,
                trace.ticket_id,
```

- [ ] **Step 7: Write failing test for ticket_id round-trip in SqliteTraceRepository**

In `tests/unit/test_sqlite_trace_repo.py`, add:

```python
class TestTicketId:
    def test_save_and_retrieve_ticket_id(self, repo):
        trace = _make_trace(request_id="req-tid", ticket_id="n-042")
        repo.save_trace(trace)
        retrieved = repo.get_recent_traces(1)[0]
        assert retrieved.ticket_id == "n-042"

    def test_ticket_id_defaults_to_none(self, repo):
        trace = _make_trace(request_id="req-no-tid")
        repo.save_trace(trace)
        retrieved = repo.get_recent_traces(1)[0]
        assert retrieved.ticket_id is None
```

- [ ] **Step 8: Run test to verify it passes** (should pass now with the schema + INSERT changes)

Run: `uv run pytest tests/unit/test_sqlite_trace_repo.py::TestTicketId -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/ticket_triage_llm/schemas/trace.py src/ticket_triage_llm/storage/db.py src/ticket_triage_llm/services/trace.py tests/unit/test_trace_record.py tests/unit/test_sqlite_trace_repo.py
git commit -m "feat(trace): add ticket_id field for ground truth joins"
```

---

## Task 2: Implement `get_traces_by_run()` and `get_all_traces()`

**Files:**
- Modify: `src/ticket_triage_llm/services/trace.py:63-73`
- Test: `tests/unit/test_sqlite_trace_repo.py`

- [ ] **Step 1: Write failing test for get_traces_by_run**

In `tests/unit/test_sqlite_trace_repo.py`, replace `TestUnimplementedMethods.test_get_traces_by_run_raises` and `test_get_all_traces_raises` with new test classes:

```python
class TestGetTracesByRun:
    def test_filters_by_run_id(self, repo):
        repo.save_trace(_make_trace(request_id="r1", run_id="run-A"))
        repo.save_trace(_make_trace(request_id="r2", run_id="run-B"))
        repo.save_trace(_make_trace(request_id="r3", run_id="run-A"))
        traces = repo.get_traces_by_run("run-A")
        assert len(traces) == 2
        assert all(t.run_id == "run-A" for t in traces)

    def test_returns_empty_for_unknown_run_id(self, repo):
        repo.save_trace(_make_trace(request_id="r1", run_id="run-X"))
        traces = repo.get_traces_by_run("run-Y")
        assert traces == []


class TestGetAllTraces:
    def test_returns_all_traces(self, repo):
        for i in range(3):
            repo.save_trace(_make_trace(request_id=f"all-{i}"))
        traces = repo.get_all_traces()
        assert len(traces) == 3

    def test_returns_empty_when_no_traces(self, repo):
        traces = repo.get_all_traces()
        assert traces == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_sqlite_trace_repo.py::TestGetTracesByRun tests/unit/test_sqlite_trace_repo.py::TestGetAllTraces -v`
Expected: FAIL — both methods raise `NotImplementedError`.

- [ ] **Step 3: Implement get_traces_by_run and get_all_traces**

In `src/ticket_triage_llm/services/trace.py`, replace the two `NotImplementedError` methods:

```python
    def get_traces_by_run(self, run_id: str) -> list[TraceRecord]:
        cursor = self._conn.execute(
            "SELECT * FROM traces WHERE run_id = ? ORDER BY timestamp",
            (run_id,),
        )
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [self._row_to_trace(columns, row) for row in rows]

    def get_all_traces(self) -> list[TraceRecord]:
        cursor = self._conn.execute(
            "SELECT * FROM traces ORDER BY timestamp DESC",
        )
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [self._row_to_trace(columns, row) for row in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_sqlite_trace_repo.py::TestGetTracesByRun tests/unit/test_sqlite_trace_repo.py::TestGetAllTraces -v`
Expected: PASS

- [ ] **Step 5: Remove the now-stale NotImplementedError tests**

In `tests/unit/test_sqlite_trace_repo.py`, remove `test_get_traces_by_run_raises` and `test_get_all_traces_raises` from `TestUnimplementedMethods`. Keep the remaining two (`test_get_traces_by_provider_raises` and `test_get_traces_since_raises`).

- [ ] **Step 6: Run full test suite to verify no regressions**

Run: `uv run pytest tests/unit/test_sqlite_trace_repo.py -v`
Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add src/ticket_triage_llm/services/trace.py tests/unit/test_sqlite_trace_repo.py
git commit -m "feat(trace-repo): implement get_traces_by_run and get_all_traces"
```

---

## Task 3: Add `skip_validation`, `run_id`, `ticket_id` to `run_triage()`

**Files:**
- Modify: `src/ticket_triage_llm/services/triage.py`
- Test: `tests/unit/test_triage_service.py`

- [ ] **Step 1: Update FakeTraceRepo to support get_traces_by_run and get_all_traces**

In `tests/unit/test_triage_service.py`, update `FakeTraceRepo`:

```python
class FakeTraceRepo:
    def __init__(self):
        self.traces: list[TraceRecord] = []

    def save_trace(self, trace: TraceRecord) -> None:
        self.traces.append(trace)

    def get_recent_traces(self, limit: int) -> list[TraceRecord]:
        return self.traces[:limit]

    def get_traces_by_run(self, run_id: str) -> list[TraceRecord]:
        return [t for t in self.traces if t.run_id == run_id]

    def get_traces_by_provider(self, provider: str) -> list[TraceRecord]:
        raise NotImplementedError

    def get_traces_since(self, since: datetime) -> list[TraceRecord]:
        raise NotImplementedError

    def get_all_traces(self) -> list[TraceRecord]:
        return list(self.traces)
```

- [ ] **Step 2: Write failing tests for run_id and ticket_id pass-through**

In `tests/unit/test_triage_service.py`, add:

```python
class TestRunTriageEvalParams:
    def test_run_id_passed_to_trace(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="billing question",
            ticket_subject="",
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
            run_id="e1-2b-test",
        )
        assert trace.run_id == "e1-2b-test"

    def test_ticket_id_passed_to_trace(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="billing question",
            ticket_subject="",
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
            ticket_id="n-001",
        )
        assert trace.ticket_id == "n-001"

    def test_run_id_defaults_to_none(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="billing question",
            ticket_subject="",
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert trace.run_id is None

    def test_ticket_id_defaults_to_none(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="billing question",
            ticket_subject="",
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert trace.ticket_id is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_triage_service.py::TestRunTriageEvalParams -v`
Expected: FAIL — `run_triage()` doesn't accept `run_id` or `ticket_id` parameters.

- [ ] **Step 4: Add `run_id`, `ticket_id`, `skip_validation` parameters to `run_triage()`**

In `src/ticket_triage_llm/services/triage.py`, update the signature:

```python
def run_triage(
    ticket_body: str,
    ticket_subject: str,
    provider: LlmProvider,
    prompt_version: str,
    trace_repo: TraceRepository,
    guardrail_max_length: int = 10_000,
    skip_validation: bool = False,
    run_id: str | None = None,
    ticket_id: str | None = None,
) -> tuple[TriageResult, TraceRecord]:
```

Pass `run_id` and `ticket_id` to `_build_and_save_trace()`. Update `_build_and_save_trace` signature to accept these two new keyword args and set them on the `TraceRecord`:

```python
def _build_and_save_trace(
    *,
    trace_repo: TraceRepository,
    request_id: str,
    start: float,
    provider: LlmProvider,
    prompt_version: str,
    ticket_body: str,
    guardrail_result: str,
    guardrail_matched_rules: list[str],
    model_result: ModelResult | None,
    raw_output: str | None,
    result: TriageResult,
    retry_count: int,
    validation_status_override: str | None = None,
    run_id: str | None = None,
    ticket_id: str | None = None,
) -> TraceRecord:
```

In the `TraceRecord(...)` constructor inside `_build_and_save_trace`, add:

```python
        run_id=run_id,
        ticket_id=ticket_id,
```

Update all three call sites in `run_triage()` to pass `run_id=run_id, ticket_id=ticket_id`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_triage_service.py::TestRunTriageEvalParams -v`
Expected: PASS

- [ ] **Step 6: Write failing tests for skip_validation behavior**

In `tests/unit/test_triage_service.py`, add:

```python
class TestRunTriageSkipValidation:
    def test_skip_validation_sets_status_skipped(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="billing question",
            ticket_subject="",
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
            skip_validation=True,
        )
        assert trace.validation_status == "skipped"

    def test_skip_validation_still_returns_success_on_valid_output(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="billing question",
            ticket_subject="",
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
            skip_validation=True,
        )
        assert isinstance(result, TriageSuccess)
        assert result.retry_count == 0

    def test_skip_validation_returns_parse_failure_on_bad_json(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="billing question",
            ticket_subject="",
            provider=AlwaysBadJsonProvider(),
            prompt_version="v1",
            trace_repo=repo,
            skip_validation=True,
        )
        assert isinstance(result, TriageFailure)
        assert result.category == "parse_failure"
        assert trace.retry_count == 0
        assert trace.validation_status == "skipped"

    def test_skip_validation_returns_schema_failure_on_bad_schema(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="billing question",
            ticket_subject="",
            provider=AlwaysBadSchemaProvider(),
            prompt_version="v1",
            trace_repo=repo,
            skip_validation=True,
        )
        assert isinstance(result, TriageFailure)
        assert result.category == "schema_failure"
        assert trace.retry_count == 0
        assert trace.validation_status == "skipped"

    def test_skip_validation_does_not_retry(self):
        repo = FakeTraceRepo()
        provider = RetrySuccessProvider()
        result, trace = run_triage(
            ticket_body="billing question",
            ticket_subject="",
            provider=provider,
            prompt_version="v1",
            trace_repo=repo,
            skip_validation=True,
        )
        assert isinstance(result, TriageFailure)
        assert result.category == "parse_failure"
        assert trace.retry_count == 0
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_triage_service.py::TestRunTriageSkipValidation -v`
Expected: FAIL — `skip_validation` behavior not implemented yet.

- [ ] **Step 8: Implement skip_validation logic in run_triage**

In `src/ticket_triage_llm/services/triage.py`, add the import at the top:

```python
from ticket_triage_llm.services.validation import parse_json, validate_schema
```

After the provider call and before the `validate_or_retry()` call, add the skip_validation branch:

```python
    if skip_validation:
        parsed = parse_json(model_result.raw_output)
        if parsed is None:
            result = TriageFailure(
                category="parse_failure",
                detected_by="parser",
                message="Failed to parse output as JSON (validation skipped)",
                raw_model_output=model_result.raw_output,
                retry_count=0,
            )
        else:
            output = validate_schema(parsed)
            if output is None:
                result = TriageFailure(
                    category="schema_failure",
                    detected_by="schema",
                    message="Schema validation failed (validation skipped)",
                    raw_model_output=model_result.raw_output,
                    retry_count=0,
                )
            else:
                result = TriageSuccess(output=output, retry_count=0)

        trace = _build_and_save_trace(
            trace_repo=trace_repo,
            request_id=request_id,
            start=start,
            provider=provider,
            prompt_version=prompt_version,
            ticket_body=ticket_body,
            guardrail_result=guardrail.decision,
            guardrail_matched_rules=guardrail.matched_rules,
            model_result=model_result,
            raw_output=model_result.raw_output,
            result=result,
            retry_count=0,
            validation_status_override="skipped",
            run_id=run_id,
            ticket_id=ticket_id,
        )
        return result, trace
```

This goes between the `except ProviderError` block and the existing `retry = validate_or_retry(...)` line.

- [ ] **Step 9: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_triage_service.py::TestRunTriageSkipValidation -v`
Expected: PASS

- [ ] **Step 10: Run full triage service test suite**

Run: `uv run pytest tests/unit/test_triage_service.py -v`
Expected: All pass — existing tests unaffected because defaults preserve old behavior.

- [ ] **Step 11: Commit**

```bash
git add src/ticket_triage_llm/services/triage.py tests/unit/test_triage_service.py
git commit -m "feat(triage): add skip_validation, run_id, ticket_id for eval harness"
```

---

## Task 4: Dataset loader

**Files:**
- Create: `src/ticket_triage_llm/eval/datasets.py`
- Create: `tests/unit/test_datasets.py`

- [ ] **Step 1: Write failing tests for load_dataset**

Create `tests/unit/test_datasets.py`:

```python
import json
from pathlib import Path

import pytest

from ticket_triage_llm.eval.datasets import GroundTruth, TicketRecord, load_dataset


class TestLoadDataset:
    def test_loads_valid_jsonl(self, tmp_path):
        jsonl = tmp_path / "test.jsonl"
        jsonl.write_text(
            json.dumps({
                "id": "n-001",
                "subject": "Billing issue",
                "body": "I have a billing question",
                "ground_truth": {
                    "category": "billing",
                    "severity": "medium",
                    "routing_team": "billing",
                    "escalation": False,
                },
            })
            + "\n"
        )
        tickets = load_dataset(jsonl)
        assert len(tickets) == 1
        assert tickets[0].id == "n-001"
        assert tickets[0].subject == "Billing issue"
        assert tickets[0].body == "I have a billing question"
        assert tickets[0].ground_truth.category == "billing"
        assert tickets[0].ground_truth.severity == "medium"
        assert tickets[0].ground_truth.routing_team == "billing"
        assert tickets[0].ground_truth.escalation is False

    def test_loads_multiple_lines(self, tmp_path):
        jsonl = tmp_path / "multi.jsonl"
        lines = []
        for i in range(3):
            lines.append(
                json.dumps({
                    "id": f"n-{i:03d}",
                    "subject": f"Subject {i}",
                    "body": f"Body {i}",
                    "ground_truth": {
                        "category": "billing",
                        "severity": "low",
                        "routing_team": "support",
                        "escalation": False,
                    },
                })
            )
        jsonl.write_text("\n".join(lines) + "\n")
        tickets = load_dataset(jsonl)
        assert len(tickets) == 3
        assert tickets[2].id == "n-002"

    def test_skips_blank_lines(self, tmp_path):
        jsonl = tmp_path / "blanks.jsonl"
        line = json.dumps({
            "id": "n-001",
            "subject": "S",
            "body": "B",
            "ground_truth": {
                "category": "billing",
                "severity": "low",
                "routing_team": "support",
                "escalation": False,
            },
        })
        jsonl.write_text(line + "\n\n\n")
        tickets = load_dataset(jsonl)
        assert len(tickets) == 1

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_dataset(Path("/nonexistent/file.jsonl"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_datasets.py -v`
Expected: FAIL — module `ticket_triage_llm.eval.datasets` has no `load_dataset` or dataclasses.

- [ ] **Step 3: Implement datasets module**

Create `src/ticket_triage_llm/eval/datasets.py`:

```python
"""Dataset loading for evaluation harness — Phase 3."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GroundTruth:
    category: str
    severity: str
    routing_team: str
    escalation: bool


@dataclass(frozen=True)
class TicketRecord:
    id: str
    subject: str
    body: str
    ground_truth: GroundTruth


def load_dataset(path: Path) -> list[TicketRecord]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    tickets: list[TicketRecord] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            gt = data["ground_truth"]
            tickets.append(
                TicketRecord(
                    id=data["id"],
                    subject=data["subject"],
                    body=data["body"],
                    ground_truth=GroundTruth(
                        category=gt["category"],
                        severity=gt["severity"],
                        routing_team=gt["routing_team"],
                        escalation=gt["escalation"],
                    ),
                )
            )
    return tickets
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_datasets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ticket_triage_llm/eval/datasets.py tests/unit/test_datasets.py
git commit -m "feat(eval): add dataset loader with GroundTruth and TicketRecord"
```

---

## Task 5: Results dataclasses

**Files:**
- Create: `src/ticket_triage_llm/eval/results.py`

- [ ] **Step 1: Create results module**

Create `src/ticket_triage_llm/eval/results.py`:

```python
"""Experiment result data structures — Phase 3."""

from dataclasses import asdict, dataclass


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

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExperimentSummary:
    experiment_id: str
    experiment_name: str
    date: str
    dataset_size: int
    prompt_version: str
    model_metrics: list[ModelMetrics]

    def to_dict(self) -> dict:
        return asdict(self)
```

- [ ] **Step 2: Verify import works**

Run: `uv run python -c "from ticket_triage_llm.eval.results import ModelMetrics, ExperimentSummary; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/ticket_triage_llm/eval/results.py
git commit -m "feat(eval): add ModelMetrics and ExperimentSummary dataclasses"
```

---

## Task 6: Summarizer — `summarize_run()` core logic

**Files:**
- Modify: `src/ticket_triage_llm/eval/runners/summarize_results.py`
- Create: `tests/unit/test_summarize_results.py`

- [ ] **Step 1: Write failing tests for summarize_run**

Create `tests/unit/test_summarize_results.py`:

```python
import json
from datetime import UTC, datetime

from ticket_triage_llm.eval.datasets import GroundTruth, TicketRecord
from ticket_triage_llm.eval.results import ModelMetrics
from ticket_triage_llm.eval.runners.summarize_results import summarize_run
from ticket_triage_llm.schemas.trace import TraceRecord


VALID_OUTPUT = {
    "category": "billing",
    "severity": "medium",
    "routingTeam": "billing",
    "summary": "Billing issue",
    "businessImpact": "Cannot process payments",
    "draftReply": "We are looking into it.",
    "confidence": 0.85,
    "escalation": False,
}

TICKETS = [
    TicketRecord(
        id="n-001",
        subject="Billing issue",
        body="I have a billing question",
        ground_truth=GroundTruth(
            category="billing",
            severity="medium",
            routing_team="billing",
            escalation=False,
        ),
    ),
    TicketRecord(
        id="n-002",
        subject="Account access",
        body="Cannot log in",
        ground_truth=GroundTruth(
            category="account_access",
            severity="high",
            routing_team="support",
            escalation=False,
        ),
    ),
]


def _make_trace(
    request_id: str,
    run_id: str,
    ticket_id: str,
    triage_output: dict | None = None,
    status: str = "success",
    failure_category: str | None = None,
    validation_status: str = "valid",
    retry_count: int = 0,
    latency_ms: float = 1500.0,
    tokens_input: int = 100,
    tokens_output: int = 50,
    tokens_total: int = 150,
    tokens_per_second: float | None = 33.0,
    raw_model_output: str | None = None,
) -> TraceRecord:
    triage_json = json.dumps(triage_output) if triage_output else None
    return TraceRecord(
        request_id=request_id,
        run_id=run_id,
        ticket_id=ticket_id,
        timestamp=datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC),
        model="qwen3.5:4b",
        provider="ollama:qwen3.5:4b",
        prompt_version="v1",
        ticket_body="test",
        guardrail_result="pass",
        validation_status=validation_status,
        retry_count=retry_count,
        latency_ms=latency_ms,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        tokens_total=tokens_total,
        tokens_per_second=tokens_per_second,
        status=status,
        failure_category=failure_category,
        raw_model_output=raw_model_output or json.dumps(triage_output) if triage_output else "bad",
        triage_output_json=triage_json,
    )


class FakeTraceRepo:
    def __init__(self, traces: list[TraceRecord]):
        self._traces = traces

    def save_trace(self, trace: TraceRecord) -> None:
        self._traces.append(trace)

    def get_recent_traces(self, limit: int) -> list[TraceRecord]:
        return self._traces[:limit]

    def get_traces_by_run(self, run_id: str) -> list[TraceRecord]:
        return [t for t in self._traces if t.run_id == run_id]

    def get_traces_by_provider(self, provider: str) -> list[TraceRecord]:
        raise NotImplementedError

    def get_traces_since(self, since: datetime) -> list[TraceRecord]:
        raise NotImplementedError

    def get_all_traces(self) -> list[TraceRecord]:
        return list(self._traces)


class TestSummarizeRunAccuracy:
    def test_all_correct(self):
        traces = [
            _make_trace("r1", "run-1", "n-001", triage_output=VALID_OUTPUT),
        ]
        repo = FakeTraceRepo(traces)
        metrics = summarize_run("run-1", TICKETS[:1], repo)
        assert metrics.category_accuracy == 1.0
        assert metrics.severity_accuracy == 1.0
        assert metrics.routing_accuracy == 1.0
        assert metrics.escalation_accuracy == 1.0

    def test_wrong_category_counts_as_incorrect(self):
        wrong_output = {**VALID_OUTPUT, "category": "outage"}
        traces = [
            _make_trace("r1", "run-1", "n-001", triage_output=wrong_output),
        ]
        repo = FakeTraceRepo(traces)
        metrics = summarize_run("run-1", TICKETS[:1], repo)
        assert metrics.category_accuracy == 0.0
        assert metrics.severity_accuracy == 1.0

    def test_failed_trace_counts_as_incorrect_for_all_fields(self):
        traces = [
            _make_trace(
                "r1", "run-1", "n-001",
                triage_output=None,
                status="failure",
                failure_category="parse_failure",
                validation_status="invalid",
            ),
        ]
        repo = FakeTraceRepo(traces)
        metrics = summarize_run("run-1", TICKETS[:1], repo)
        assert metrics.category_accuracy == 0.0
        assert metrics.severity_accuracy == 0.0
        assert metrics.routing_accuracy == 0.0
        assert metrics.escalation_accuracy == 0.0
        assert metrics.successful_tickets == 0
        assert metrics.total_tickets == 1

    def test_mixed_correct_and_incorrect(self):
        traces = [
            _make_trace("r1", "run-1", "n-001", triage_output=VALID_OUTPUT),
            _make_trace(
                "r2", "run-1", "n-002",
                triage_output=None,
                status="failure",
                failure_category="parse_failure",
                validation_status="invalid",
            ),
        ]
        repo = FakeTraceRepo(traces)
        metrics = summarize_run("run-1", TICKETS, repo)
        assert metrics.category_accuracy == 0.5
        assert metrics.total_tickets == 2
        assert metrics.successful_tickets == 1


class TestSummarizeRunReliability:
    def test_json_valid_rate(self):
        traces = [
            _make_trace("r1", "run-1", "n-001", triage_output=VALID_OUTPUT,
                        raw_model_output=json.dumps(VALID_OUTPUT)),
            _make_trace("r2", "run-1", "n-002", triage_output=None,
                        status="failure", failure_category="parse_failure",
                        validation_status="invalid",
                        raw_model_output="not json"),
        ]
        repo = FakeTraceRepo(traces)
        metrics = summarize_run("run-1", TICKETS, repo)
        assert metrics.json_valid_rate == 0.5

    def test_retry_rate_and_success(self):
        traces = [
            _make_trace("r1", "run-1", "n-001", triage_output=VALID_OUTPUT,
                        retry_count=0),
            _make_trace("r2", "run-1", "n-002", triage_output=VALID_OUTPUT,
                        retry_count=1, validation_status="valid_after_retry"),
        ]
        repo = FakeTraceRepo(traces)
        metrics = summarize_run("run-1", TICKETS, repo)
        assert metrics.retry_rate == 0.5
        assert metrics.retry_success_rate == 1.0

    def test_schema_pass_rate(self):
        traces = [
            _make_trace("r1", "run-1", "n-001", triage_output=VALID_OUTPUT,
                        validation_status="valid"),
            _make_trace("r2", "run-1", "n-002", triage_output=None,
                        status="failure", failure_category="schema_failure",
                        validation_status="invalid"),
        ]
        repo = FakeTraceRepo(traces)
        metrics = summarize_run("run-1", TICKETS, repo)
        assert metrics.schema_pass_rate == 0.5


class TestSummarizeRunLatency:
    def test_latency_percentiles(self):
        traces = [
            _make_trace("r1", "run-1", "n-001", triage_output=VALID_OUTPUT,
                        latency_ms=100.0),
            _make_trace("r2", "run-1", "n-002", triage_output=VALID_OUTPUT,
                        latency_ms=200.0),
        ]
        repo = FakeTraceRepo(traces)
        metrics = summarize_run("run-1", TICKETS, repo)
        assert metrics.avg_latency_ms == 150.0
        assert metrics.p50_latency_ms == 150.0

    def test_token_averages(self):
        traces = [
            _make_trace("r1", "run-1", "n-001", triage_output=VALID_OUTPUT,
                        tokens_input=100, tokens_output=50, tokens_total=150),
            _make_trace("r2", "run-1", "n-002", triage_output=VALID_OUTPUT,
                        tokens_input=200, tokens_output=100, tokens_total=300),
        ]
        repo = FakeTraceRepo(traces)
        metrics = summarize_run("run-1", TICKETS, repo)
        assert metrics.avg_tokens_input == 150.0
        assert metrics.avg_tokens_output == 75.0
        assert metrics.avg_tokens_total == 225.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_summarize_results.py -v`
Expected: FAIL — `summarize_run` not importable.

- [ ] **Step 3: Implement summarize_run**

Replace `src/ticket_triage_llm/eval/runners/summarize_results.py` with:

```python
"""Aggregate and summarize experiment results — Phase 3."""

import json
import statistics
from datetime import datetime

from ticket_triage_llm.eval.datasets import TicketRecord
from ticket_triage_llm.eval.results import ExperimentSummary, ModelMetrics
from ticket_triage_llm.services.validation import parse_json
from ticket_triage_llm.storage.trace_repo import TraceRepository


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (pct / 100)
    f = int(k)
    c = f + 1
    if c >= len(sorted_vals):
        return sorted_vals[f]
    return sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f])


def summarize_run(
    run_id: str,
    tickets: list[TicketRecord],
    trace_repo: TraceRepository,
) -> ModelMetrics:
    traces = trace_repo.get_traces_by_run(run_id)
    if not traces:
        raise ValueError(f"No traces found for run_id={run_id!r}")

    gt_by_id = {t.id: t.ground_truth for t in tickets}
    total = len(traces)

    category_correct = 0
    severity_correct = 0
    routing_correct = 0
    escalation_correct = 0
    successful = 0
    json_valid = 0
    schema_pass = 0
    retried = 0
    retry_succeeded = 0
    latencies: list[float] = []
    tps_values: list[float] = []
    tokens_in: list[int] = []
    tokens_out: list[int] = []
    tokens_tot: list[int] = []

    for trace in traces:
        latencies.append(trace.latency_ms)
        tokens_in.append(trace.tokens_input)
        tokens_out.append(trace.tokens_output)
        tokens_tot.append(trace.tokens_total)
        if trace.tokens_per_second is not None:
            tps_values.append(trace.tokens_per_second)

        if trace.raw_model_output and parse_json(trace.raw_model_output) is not None:
            json_valid += 1

        if trace.validation_status in ("valid", "valid_after_retry"):
            schema_pass += 1

        if trace.retry_count > 0:
            retried += 1
            if trace.status == "success":
                retry_succeeded += 1

        if trace.status != "success" or not trace.triage_output_json:
            continue

        successful += 1
        gt = gt_by_id.get(trace.ticket_id) if trace.ticket_id else None
        if gt is None:
            continue

        output = json.loads(trace.triage_output_json)
        if output.get("category") == gt.category:
            category_correct += 1
        if output.get("severity") == gt.severity:
            severity_correct += 1
        routing = output.get("routingTeam") or output.get("routing_team")
        if routing == gt.routing_team:
            routing_correct += 1
        if output.get("escalation") == gt.escalation:
            escalation_correct += 1

    return ModelMetrics(
        model=traces[0].model,
        run_id=run_id,
        category_accuracy=category_correct / total if total else 0.0,
        severity_accuracy=severity_correct / total if total else 0.0,
        routing_accuracy=routing_correct / total if total else 0.0,
        escalation_accuracy=escalation_correct / total if total else 0.0,
        json_valid_rate=json_valid / total if total else 0.0,
        schema_pass_rate=schema_pass / total if total else 0.0,
        retry_rate=retried / total if total else 0.0,
        retry_success_rate=retry_succeeded / retried if retried else 0.0,
        avg_latency_ms=statistics.mean(latencies) if latencies else 0.0,
        p50_latency_ms=_percentile(latencies, 50),
        p95_latency_ms=_percentile(latencies, 95),
        avg_tokens_per_second=(
            statistics.mean(tps_values) if tps_values else None
        ),
        avg_tokens_input=statistics.mean(tokens_in) if tokens_in else 0.0,
        avg_tokens_output=statistics.mean(tokens_out) if tokens_out else 0.0,
        avg_tokens_total=statistics.mean(tokens_tot) if tokens_tot else 0.0,
        total_tickets=total,
        successful_tickets=successful,
    )


def compose_e2(
    e1_summary: ExperimentSummary,
    e2_9b_noval_run_id: str,
    tickets: list[TicketRecord],
    trace_repo: TraceRepository,
) -> ExperimentSummary:
    smallest_metrics = None
    for m in e1_summary.model_metrics:
        if "2b" in m.model.lower():
            smallest_metrics = m
            break
    if smallest_metrics is None:
        smallest_metrics = e1_summary.model_metrics[0]

    largest_noval_metrics = summarize_run(e2_9b_noval_run_id, tickets, trace_repo)

    return ExperimentSummary(
        experiment_id="E2",
        experiment_name="Model size vs engineering controls",
        date=datetime.now().strftime("%Y-%m-%d"),
        dataset_size=len(tickets),
        prompt_version="v1",
        model_metrics=[smallest_metrics, largest_noval_metrics],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_summarize_results.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ticket_triage_llm/eval/runners/summarize_results.py tests/unit/test_summarize_results.py
git commit -m "feat(eval): implement summarize_run with accuracy and reliability metrics"
```

---

## Task 7: `compose_e2()` tests

**Files:**
- Modify: `tests/unit/test_summarize_results.py`

- [ ] **Step 1: Write failing tests for compose_e2**

Add to `tests/unit/test_summarize_results.py`:

```python
from ticket_triage_llm.eval.runners.summarize_results import compose_e2


class TestComposeE2:
    def test_picks_2b_from_e1_and_9b_noval(self):
        e1_2b = ModelMetrics(
            model="qwen3.5:2b", run_id="e1-2b", category_accuracy=0.8,
            severity_accuracy=0.7, routing_accuracy=0.9, escalation_accuracy=1.0,
            json_valid_rate=1.0, schema_pass_rate=1.0, retry_rate=0.1,
            retry_success_rate=1.0, avg_latency_ms=500.0, p50_latency_ms=450.0,
            p95_latency_ms=800.0, avg_tokens_per_second=60.0,
            avg_tokens_input=100.0, avg_tokens_output=50.0,
            avg_tokens_total=150.0, total_tickets=2, successful_tickets=2,
        )
        e1_9b = ModelMetrics(
            model="qwen3.5:9b", run_id="e1-9b", category_accuracy=0.95,
            severity_accuracy=0.9, routing_accuracy=0.95, escalation_accuracy=1.0,
            json_valid_rate=1.0, schema_pass_rate=1.0, retry_rate=0.0,
            retry_success_rate=0.0, avg_latency_ms=2000.0, p50_latency_ms=1800.0,
            p95_latency_ms=3000.0, avg_tokens_per_second=25.0,
            avg_tokens_input=100.0, avg_tokens_output=50.0,
            avg_tokens_total=150.0, total_tickets=2, successful_tickets=2,
        )
        e1_summary = ExperimentSummary(
            experiment_id="E1", experiment_name="Model size comparison",
            date="2026-04-17", dataset_size=2, prompt_version="v1",
            model_metrics=[e1_2b, e1_9b],
        )

        noval_traces = [
            _make_trace("r1", "e2-9b-noval", "n-001",
                        triage_output=VALID_OUTPUT, validation_status="skipped"),
            _make_trace("r2", "e2-9b-noval", "n-002",
                        triage_output={**VALID_OUTPUT, "category": "account_access",
                                       "severity": "high", "routingTeam": "support"},
                        validation_status="skipped"),
        ]
        repo = FakeTraceRepo(noval_traces)

        e2 = compose_e2(e1_summary, "e2-9b-noval", TICKETS, repo)
        assert e2.experiment_id == "E2"
        assert len(e2.model_metrics) == 2
        assert e2.model_metrics[0].model == "qwen3.5:2b"
        assert e2.model_metrics[1].run_id == "e2-9b-noval"
```

- [ ] **Step 2: Run test to verify it passes** (compose_e2 already implemented in Task 6)

Run: `uv run pytest tests/unit/test_summarize_results.py::TestComposeE2 -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_summarize_results.py
git commit -m "test(eval): add compose_e2 tests for E2 experiment composition"
```

---

## Task 8: Shared runner loop — `run_experiment_pass()`

**Files:**
- Create: `src/ticket_triage_llm/eval/runners/common.py`
- Create: `tests/unit/test_eval_common.py`

- [ ] **Step 1: Write failing tests for run_experiment_pass**

Create `tests/unit/test_eval_common.py`:

```python
from datetime import datetime

from ticket_triage_llm.eval.datasets import GroundTruth, TicketRecord
from ticket_triage_llm.eval.runners.common import run_experiment_pass
from ticket_triage_llm.schemas.model_result import ModelResult
from ticket_triage_llm.schemas.trace import TraceRecord


VALID_JSON_OUTPUT = (
    '{"category": "billing", "severity": "medium",'
    ' "routingTeam": "billing", "summary": "Billing issue",'
    ' "businessImpact": "Cannot process payments",'
    ' "draftReply": "We are looking into it.",'
    ' "confidence": 0.85, "escalation": false}'
)


class FakeProvider:
    name: str = "fake:test"

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str, ticket_subject: str = ""
    ) -> ModelResult:
        return ModelResult(
            raw_output=VALID_JSON_OUTPUT,
            model="fake-model",
            latency_ms=100.0,
            tokens_input=50,
            tokens_output=25,
            tokens_total=75,
        )


class FakeTraceRepo:
    def __init__(self):
        self.traces: list[TraceRecord] = []

    def save_trace(self, trace: TraceRecord) -> None:
        self.traces.append(trace)

    def get_recent_traces(self, limit: int) -> list[TraceRecord]:
        return self.traces[:limit]

    def get_traces_by_run(self, run_id: str) -> list[TraceRecord]:
        return [t for t in self.traces if t.run_id == run_id]

    def get_traces_by_provider(self, provider: str) -> list[TraceRecord]:
        raise NotImplementedError

    def get_traces_since(self, since: datetime) -> list[TraceRecord]:
        raise NotImplementedError

    def get_all_traces(self) -> list[TraceRecord]:
        return list(self.traces)


TICKETS = [
    TicketRecord(
        id="n-001",
        subject="Billing issue",
        body="I have a billing question",
        ground_truth=GroundTruth(
            category="billing", severity="medium",
            routing_team="billing", escalation=False,
        ),
    ),
    TicketRecord(
        id="n-002",
        subject="Account access",
        body="Cannot log in",
        ground_truth=GroundTruth(
            category="account_access", severity="high",
            routing_team="support", escalation=False,
        ),
    ),
]


class TestRunExperimentPass:
    def test_returns_one_trace_per_ticket(self):
        repo = FakeTraceRepo()
        traces = run_experiment_pass(
            tickets=TICKETS,
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
            run_id="test-run",
        )
        assert len(traces) == 2

    def test_sets_run_id_on_all_traces(self):
        repo = FakeTraceRepo()
        traces = run_experiment_pass(
            tickets=TICKETS,
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
            run_id="test-run",
        )
        assert all(t.run_id == "test-run" for t in traces)

    def test_sets_ticket_id_on_all_traces(self):
        repo = FakeTraceRepo()
        traces = run_experiment_pass(
            tickets=TICKETS,
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
            run_id="test-run",
        )
        assert traces[0].ticket_id == "n-001"
        assert traces[1].ticket_id == "n-002"

    def test_passes_skip_validation_flag(self):
        repo = FakeTraceRepo()
        traces = run_experiment_pass(
            tickets=TICKETS,
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
            run_id="test-run",
            skip_validation=True,
        )
        assert all(t.validation_status == "skipped" for t in traces)

    def test_saves_traces_to_repo(self):
        repo = FakeTraceRepo()
        run_experiment_pass(
            tickets=TICKETS,
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
            run_id="test-run",
        )
        assert len(repo.traces) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_eval_common.py -v`
Expected: FAIL — `run_experiment_pass` not importable.

- [ ] **Step 3: Implement run_experiment_pass**

Replace `src/ticket_triage_llm/eval/runners/common.py` content (currently an empty `__init__.py`-style stub or doesn't exist):

```python
"""Shared eval runner infrastructure — Phase 3."""

import logging

from ticket_triage_llm.eval.datasets import TicketRecord
from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.schemas.trace import TraceRecord
from ticket_triage_llm.services.triage import run_triage
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)


def run_experiment_pass(
    tickets: list[TicketRecord],
    provider: LlmProvider,
    prompt_version: str,
    trace_repo: TraceRepository,
    run_id: str,
    skip_validation: bool = False,
    guardrail_max_length: int = 10_000,
) -> list[TraceRecord]:
    traces: list[TraceRecord] = []
    total = len(tickets)
    for i, ticket in enumerate(tickets, 1):
        result, trace = run_triage(
            ticket_body=ticket.body,
            ticket_subject=ticket.subject,
            provider=provider,
            prompt_version=prompt_version,
            trace_repo=trace_repo,
            guardrail_max_length=guardrail_max_length,
            skip_validation=skip_validation,
            run_id=run_id,
            ticket_id=ticket.id,
        )
        traces.append(trace)
        logger.info(
            "[%d/%d] ticket %s — %s — %.0fms",
            i, total, ticket.id, trace.status, trace.latency_ms,
        )
    return traces
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_eval_common.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ticket_triage_llm/eval/runners/common.py tests/unit/test_eval_common.py
git commit -m "feat(eval): add run_experiment_pass shared runner loop"
```

---

## Task 9: E1 runner — `run_local_comparison`

**Files:**
- Modify: `src/ticket_triage_llm/eval/runners/run_local_comparison.py`

- [ ] **Step 1: Implement E1 runner**

Replace `src/ticket_triage_llm/eval/runners/run_local_comparison.py`:

```python
"""Experiment 1: local model size comparison — Phase 3."""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from ticket_triage_llm.eval.datasets import TicketRecord, load_dataset
from ticket_triage_llm.eval.results import ExperimentSummary
from ticket_triage_llm.eval.runners.common import run_experiment_pass
from ticket_triage_llm.eval.runners.summarize_results import summarize_run
from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)


def run_local_comparison(
    providers: list[LlmProvider],
    tickets: list[TicketRecord],
    trace_repo: TraceRepository,
) -> ExperimentSummary:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M")
    metrics = []

    for provider in providers:
        tag = provider.name.split(":")[-1] if ":" in provider.name else provider.name
        run_id = f"e1-{tag}-{timestamp}"
        logger.info("E1: running %s — run_id=%s", provider.name, run_id)
        run_experiment_pass(
            tickets=tickets,
            provider=provider,
            prompt_version="v1",
            trace_repo=trace_repo,
            run_id=run_id,
        )
        model_metrics = summarize_run(run_id, tickets, trace_repo)
        metrics.append(model_metrics)

    return ExperimentSummary(
        experiment_id="E1",
        experiment_name="Model size comparison",
        date=datetime.now().strftime("%Y-%m-%d"),
        dataset_size=len(tickets),
        prompt_version="v1",
        model_metrics=metrics,
    )


if __name__ == "__main__":
    import argparse

    from ticket_triage_llm.config import Settings
    from ticket_triage_llm.providers.ollama_qwen import OllamaQwenProvider
    from ticket_triage_llm.services.trace import SqliteTraceRepository
    from ticket_triage_llm.storage.db import get_connection, init_schema

    parser = argparse.ArgumentParser(description="E1: local model size comparison")
    parser.add_argument("--db-path", default="data/traces.db")
    parser.add_argument("--dataset-path", default="data/normal_set.jsonl")
    parser.add_argument("--output-dir", default="data/phase3")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    settings = Settings()
    models = [m.strip() for m in settings.ollama_models.split(",") if m.strip()]
    if not models:
        models = [settings.ollama_model]

    providers = [
        OllamaQwenProvider(model=m, base_url=settings.ollama_base_url)
        for m in models
    ]

    conn = get_connection(args.db_path)
    init_schema(conn)
    repo = SqliteTraceRepository(conn)
    tickets = load_dataset(Path(args.dataset_path))

    summary = run_local_comparison(providers, tickets, repo)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "e1-local-comparison.json"
    out_path.write_text(json.dumps(summary.to_dict(), indent=2))
    logger.info("E1 results written to %s", out_path)
```

- [ ] **Step 2: Verify import works**

Run: `uv run python -c "from ticket_triage_llm.eval.runners.run_local_comparison import run_local_comparison; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/ticket_triage_llm/eval/runners/run_local_comparison.py
git commit -m "feat(eval): implement E1 local model comparison runner"
```

---

## Task 10: E3 runner — `run_validation_impact`

**Files:**
- Modify: `src/ticket_triage_llm/eval/runners/run_validation_impact.py`

- [ ] **Step 1: Implement E3 runner**

Replace `src/ticket_triage_llm/eval/runners/run_validation_impact.py`:

```python
"""Experiment 3: validation on/off impact — Phase 3."""

import json
import logging
from datetime import datetime
from pathlib import Path

from ticket_triage_llm.eval.datasets import TicketRecord, load_dataset
from ticket_triage_llm.eval.results import ExperimentSummary
from ticket_triage_llm.eval.runners.common import run_experiment_pass
from ticket_triage_llm.eval.runners.summarize_results import summarize_run
from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)


def run_validation_impact(
    provider_4b: LlmProvider,
    provider_9b: LlmProvider,
    tickets: list[TicketRecord],
    trace_repo: TraceRepository,
) -> tuple[ExperimentSummary, str]:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M")

    run_id_validated = f"e3-4b-validated-{timestamp}"
    logger.info("E3: 4B validated — run_id=%s", run_id_validated)
    run_experiment_pass(
        tickets=tickets,
        provider=provider_4b,
        prompt_version="v1",
        trace_repo=trace_repo,
        run_id=run_id_validated,
        skip_validation=False,
    )

    run_id_skipped = f"e3-4b-skipped-{timestamp}"
    logger.info("E3: 4B no-validation — run_id=%s", run_id_skipped)
    run_experiment_pass(
        tickets=tickets,
        provider=provider_4b,
        prompt_version="v1",
        trace_repo=trace_repo,
        run_id=run_id_skipped,
        skip_validation=True,
    )

    e2_run_id = f"e2-9b-noval-{timestamp}"
    logger.info("E2 data point: 9B no-validation — run_id=%s", e2_run_id)
    run_experiment_pass(
        tickets=tickets,
        provider=provider_9b,
        prompt_version="v1",
        trace_repo=trace_repo,
        run_id=e2_run_id,
        skip_validation=True,
    )

    validated_metrics = summarize_run(run_id_validated, tickets, trace_repo)
    skipped_metrics = summarize_run(run_id_skipped, tickets, trace_repo)

    summary = ExperimentSummary(
        experiment_id="E3",
        experiment_name="Validation impact",
        date=datetime.now().strftime("%Y-%m-%d"),
        dataset_size=len(tickets),
        prompt_version="v1",
        model_metrics=[validated_metrics, skipped_metrics],
    )
    return summary, e2_run_id


if __name__ == "__main__":
    import argparse

    from ticket_triage_llm.config import Settings
    from ticket_triage_llm.providers.ollama_qwen import OllamaQwenProvider
    from ticket_triage_llm.services.trace import SqliteTraceRepository
    from ticket_triage_llm.storage.db import get_connection, init_schema

    parser = argparse.ArgumentParser(description="E3: validation impact")
    parser.add_argument("--db-path", default="data/traces.db")
    parser.add_argument("--dataset-path", default="data/normal_set.jsonl")
    parser.add_argument("--output-dir", default="data/phase3")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    settings = Settings()
    provider_4b = OllamaQwenProvider(
        model="qwen3.5:4b", base_url=settings.ollama_base_url
    )
    provider_9b = OllamaQwenProvider(
        model="qwen3.5:9b", base_url=settings.ollama_base_url
    )

    conn = get_connection(args.db_path)
    init_schema(conn)
    repo = SqliteTraceRepository(conn)
    tickets = load_dataset(Path(args.dataset_path))

    summary, e2_run_id = run_validation_impact(provider_4b, provider_9b, tickets, repo)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "e3-validation-impact.json"
    out_path.write_text(json.dumps(summary.to_dict(), indent=2))
    logger.info("E3 results written to %s", out_path)
    logger.info("E2 9B no-validation run_id: %s (use with summarize_results)", e2_run_id)
```

- [ ] **Step 2: Verify import works**

Run: `uv run python -c "from ticket_triage_llm.eval.runners.run_validation_impact import run_validation_impact; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/ticket_triage_llm/eval/runners/run_validation_impact.py
git commit -m "feat(eval): implement E3 validation impact runner with E2 data point"
```

---

## Task 11: E4 runner — `run_prompt_comparison`

**Files:**
- Modify: `src/ticket_triage_llm/eval/runners/run_prompt_comparison.py`

- [ ] **Step 1: Implement E4 runner (v1 only for Phase 3)**

Replace `src/ticket_triage_llm/eval/runners/run_prompt_comparison.py`:

```python
"""Experiment 4: prompt v1 vs v2 comparison — Phase 6.

Phase 3 runs v1 only. Re-run after Phase 6 adds triage_v2.py.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from ticket_triage_llm.eval.datasets import TicketRecord, load_dataset
from ticket_triage_llm.eval.results import ExperimentSummary
from ticket_triage_llm.eval.runners.common import run_experiment_pass
from ticket_triage_llm.eval.runners.summarize_results import summarize_run
from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)


def run_prompt_comparison(
    provider: LlmProvider,
    tickets: list[TicketRecord],
    trace_repo: TraceRepository,
    prompt_versions: list[str] | None = None,
) -> ExperimentSummary:
    if prompt_versions is None:
        prompt_versions = ["v1"]

    timestamp = datetime.now().strftime("%Y%m%dT%H%M")
    metrics = []

    for version in prompt_versions:
        run_id = f"e4-{version}-{timestamp}"
        logger.info("E4: prompt %s — run_id=%s", version, run_id)
        run_experiment_pass(
            tickets=tickets,
            provider=provider,
            prompt_version=version,
            trace_repo=trace_repo,
            run_id=run_id,
        )
        model_metrics = summarize_run(run_id, tickets, trace_repo)
        metrics.append(model_metrics)

    return ExperimentSummary(
        experiment_id="E4",
        experiment_name="Prompt comparison",
        date=datetime.now().strftime("%Y-%m-%d"),
        dataset_size=len(tickets),
        prompt_version=",".join(prompt_versions),
        model_metrics=metrics,
    )


if __name__ == "__main__":
    import argparse

    from ticket_triage_llm.config import Settings
    from ticket_triage_llm.providers.ollama_qwen import OllamaQwenProvider
    from ticket_triage_llm.services.trace import SqliteTraceRepository
    from ticket_triage_llm.storage.db import get_connection, init_schema

    parser = argparse.ArgumentParser(description="E4: prompt comparison")
    parser.add_argument("--db-path", default="data/traces.db")
    parser.add_argument("--dataset-path", default="data/normal_set.jsonl")
    parser.add_argument("--output-dir", default="data/phase3")
    parser.add_argument(
        "--prompt-versions", default="v1",
        help="Comma-separated prompt versions (e.g., 'v1,v2')",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    settings = Settings()
    provider = OllamaQwenProvider(
        model=settings.ollama_model, base_url=settings.ollama_base_url
    )

    conn = get_connection(args.db_path)
    init_schema(conn)
    repo = SqliteTraceRepository(conn)
    tickets = load_dataset(Path(args.dataset_path))
    versions = [v.strip() for v in args.prompt_versions.split(",")]

    summary = run_prompt_comparison(provider, tickets, repo, prompt_versions=versions)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "e4-prompt-comparison.json"
    out_path.write_text(json.dumps(summary.to_dict(), indent=2))
    logger.info("E4 results written to %s", out_path)
```

- [ ] **Step 2: Verify import works**

Run: `uv run python -c "from ticket_triage_llm.eval.runners.run_prompt_comparison import run_prompt_comparison; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/ticket_triage_llm/eval/runners/run_prompt_comparison.py
git commit -m "feat(eval): implement E4 prompt comparison runner (v1 only for Phase 3)"
```

---

## Task 12: Summarizer CLI entry point

**Files:**
- Modify: `src/ticket_triage_llm/eval/runners/summarize_results.py`

- [ ] **Step 1: Add CLI __main__ block to summarize_results.py**

Append to the end of `src/ticket_triage_llm/eval/runners/summarize_results.py`:

```python
def _print_metrics(m: ModelMetrics) -> None:
    print(f"  Model:              {m.model}")
    print(f"  Run ID:             {m.run_id}")
    print(f"  Category accuracy:  {m.category_accuracy:.1%}")
    print(f"  Severity accuracy:  {m.severity_accuracy:.1%}")
    print(f"  Routing accuracy:   {m.routing_accuracy:.1%}")
    print(f"  Escalation acc:     {m.escalation_accuracy:.1%}")
    print(f"  JSON valid rate:    {m.json_valid_rate:.1%}")
    print(f"  Schema pass rate:   {m.schema_pass_rate:.1%}")
    print(f"  Retry rate:         {m.retry_rate:.1%}")
    print(f"  Retry success rate: {m.retry_success_rate:.1%}")
    print(f"  Avg latency:        {m.avg_latency_ms:.0f}ms")
    print(f"  p50 latency:        {m.p50_latency_ms:.0f}ms")
    print(f"  p95 latency:        {m.p95_latency_ms:.0f}ms")
    tps = f"{m.avg_tokens_per_second:.1f}" if m.avg_tokens_per_second else "N/A"
    print(f"  Avg tokens/sec:     {tps}")
    print(f"  Avg tokens in:      {m.avg_tokens_input:.0f}")
    print(f"  Avg tokens out:     {m.avg_tokens_output:.0f}")
    print(f"  Tickets:            {m.successful_tickets}/{m.total_tickets}")
    print()


if __name__ == "__main__":
    import argparse
    import logging
    from pathlib import Path

    from ticket_triage_llm.eval.datasets import load_dataset
    from ticket_triage_llm.services.trace import SqliteTraceRepository
    from ticket_triage_llm.storage.db import get_connection, init_schema

    parser = argparse.ArgumentParser(description="Summarize experiment results")
    parser.add_argument("--db-path", default="data/traces.db")
    parser.add_argument("--dataset-path", default="data/normal_set.jsonl")
    parser.add_argument("--run-id", required=True, help="Run ID to summarize")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    conn = get_connection(args.db_path)
    init_schema(conn)
    repo = SqliteTraceRepository(conn)
    tickets = load_dataset(Path(args.dataset_path))

    metrics = summarize_run(args.run_id, tickets, repo)
    _print_metrics(metrics)
```

- [ ] **Step 2: Verify CLI help works**

Run: `uv run python -m ticket_triage_llm.eval.runners.summarize_results --help`
Expected: Shows help text with `--db-path`, `--dataset-path`, `--run-id` options.

- [ ] **Step 3: Commit**

```bash
git add src/ticket_triage_llm/eval/runners/summarize_results.py
git commit -m "feat(eval): add summarizer CLI entry point"
```

---

## Task 13: Lint, full test suite, and cleanup

**Files:**
- All modified/created files

- [ ] **Step 1: Run ruff check and fix**

Run: `uv run ruff check . --fix && uv run ruff format .`
Expected: No errors after fix.

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest --cov=ticket_triage_llm --cov-fail-under=80 -v`
Expected: All tests pass, coverage >= 80%.

- [ ] **Step 3: Fix any failures or coverage gaps**

Address any test failures or lint issues found. Common issues:
- Unused imports from auto-generated code
- Missing `strict=True` on `zip()` calls
- Line length violations

- [ ] **Step 4: Commit cleanup if needed**

```bash
git add -A
git commit -m "chore: lint and format cleanup for Phase 3"
```

---

## Task 14: Update docs — TODO.md, SUMMARY.md, README.md

**Files:**
- Modify: `TODO.md`
- Modify: `SUMMARY.md`
- Modify: `README.md`

- [ ] **Step 1: Mark Phase 3 complete in TODO.md**

In `TODO.md`, check off all Phase 3 items:

```markdown
## [2026-04-17] Phase 3 — Evaluation harness + benchmark run (COMPLETE)

- [x] `eval/runners/run_local_comparison.py` (E1) — local model size comparison
- [x] `eval/runners/run_validation_impact.py` (E3) — validation on/off impact (needs Phase 2 retry)
- [x] `eval/runners/run_prompt_comparison.py` (E4) — prompt v1 vs v2 (partial; re-run after Phase 6)
- [x] `eval/runners/summarize_results.py` — aggregate results, compute E2 as composition of E1+E3
- [x] All runs tag rows with `run_id` in traces table (ADR 0005)
- [x] Fill in `docs/evaluation-checklist.md` Phase 3 sections + "Expected Benchmark Table" in `PLAN.md`
- [x] Unit tests (TDD) for summarizer aggregation logic
- [x] SUMMARY.md + TODO.md updated
- [x] PR opened, CI green, merged to `develop`
```

Add a completed-phase summary block at the bottom:

```markdown
### [2026-04-17] Phase 3 — Evaluation harness + benchmark run (COMPLETE)

**Objective:** Build the eval harness: dataset loader, experiment runners (E1–E4), summarizer with accuracy/reliability/latency metrics, ground-truth correlation via `ticket_id`, and `skip_validation` mode for E3.

**Outcome:** [N] tests, [X]% coverage, ruff clean. Eval runners produce tagged traces and JSON result files in `data/phase3/`. Summarizer computes accuracy, reliability, and operational metrics from traces joined to ground truth. E2 composed from E1 + E3 data.

**References:** `SUMMARY.md` (Phase 3 entry), design spec at `docs/superpowers/specs/2026-04-17-phase-3-eval-harness-design.md`, implementation plan at `docs/superpowers/plans/2026-04-17-phase-3-eval-harness.md`.
```

- [ ] **Step 2: Add Phase 3 entry to SUMMARY.md**

Prepend to `SUMMARY.md` (above the Phase 2 entry):

```markdown
## [2026-04-17] Phase 3 — Evaluation harness + benchmark run

**What was done:**

- Added `ticket_id` field to `TraceRecord` and `traces` table for ground-truth correlation.
- Added `skip_validation`, `run_id`, `ticket_id` parameters to `run_triage()`. `skip_validation=True` bypasses `validate_or_retry()`, sets `validation_status="skipped"`, records parse/schema outcome without retry.
- Implemented `get_traces_by_run()` and `get_all_traces()` on `SqliteTraceRepository` (previously `NotImplementedError` stubs).
- Created `eval/datasets.py` with `GroundTruth`, `TicketRecord` dataclasses and `load_dataset()` JSONL parser.
- Created `eval/results.py` with `ModelMetrics` and `ExperimentSummary` dataclasses.
- Implemented `eval/runners/common.py::run_experiment_pass()` — shared loop calling `run_triage()` per ticket with eval params.
- Implemented `summarize_run()` — computes accuracy (category, severity, routing, escalation), reliability (JSON valid rate, schema pass rate, retry rate), and operational (latency percentiles, token averages) metrics by joining traces on `ticket_id` to ground truth.
- Implemented `compose_e2()` — picks smallest-model-with-validation from E1, computes largest-model-no-validation from dedicated run.
- Implemented E1 runner (`run_local_comparison.py`) — runs all providers through normal set with full validation.
- Implemented E3 runner (`run_validation_impact.py`) — runs 4B validated/skipped + 9B skipped for E2 data point.
- Implemented E4 runner (`run_prompt_comparison.py`) — v1 only for Phase 3, re-run after Phase 6.
- All runners write JSON summaries to `data/phase3/` and tagged traces to SQLite.
- [N] tests total, [X]% coverage, ruff clean.

**How it was done:**

- Strict RED/GREEN/REFACTOR TDD for summarizer, dataset loader, shared runner loop, skip-validation, trace repo query methods.
- Judgment-based for runner CLI entry points and results dataclasses.
- Atomic commits per task on `feature/phase-3-eval-harness`.

**Issues encountered:**

[Fill in after implementation]

**How those issues were resolved:**

[Fill in after implementation]

**Exit state:**

- [N] tests pass, [X]% coverage, ruff clean.
- Phase 4 unblocked (adversarial eval uses the same harness + guardrail `matched_rules`).
- Phase 5 unblocked (dashboard queries `run_id`-tagged traces).

---
```

- [ ] **Step 3: Update README.md eval runner commands**

In `README.md`, update the Commands section to mark eval runners as functional:

```bash
# Eval runners — Phase 3 (functional)
uv run python -m ticket_triage_llm.eval.runners.run_local_comparison
uv run python -m ticket_triage_llm.eval.runners.run_validation_impact
uv run python -m ticket_triage_llm.eval.runners.run_prompt_comparison
uv run python -m ticket_triage_llm.eval.runners.summarize_results --run-id <RUN_ID>
```

- [ ] **Step 4: Commit docs**

```bash
git add TODO.md SUMMARY.md README.md
git commit -m "docs: update TODO, SUMMARY, README for Phase 3 completion"
```

---

## Dependency Graph

```text
Task 1 (ticket_id schema) ──► Task 2 (get_traces_by_run) ──► Task 6 (summarize_run)
         │                                                            │
         └──► Task 3 (skip_validation + run_id) ──► Task 8 (common) ─┤
                                                         │            │
Task 4 (datasets) ─────────────────────────────►─────────┤            │
                                                         │            │
Task 5 (results) ──────────────────────────────►─────────┤            │
                                                         │            │
                                                         ├──► Task 9 (E1)
                                                         ├──► Task 10 (E3)
                                                         ├──► Task 11 (E4)
                                                         │
Task 7 (compose_e2 tests) ◄── Task 6                     │
                                                         │
Task 12 (CLI) ◄── Task 6                                 │
                                                         │
Task 13 (lint + full suite) ◄── all above                │
                                                         │
Task 14 (docs) ◄── Task 13                              │
```

**Parallelizable groups:**
- Tasks 4 + 5 can run in parallel (no dependencies on each other)
- Tasks 9, 10, 11 can run in parallel (all depend on Task 8 but not each other)
