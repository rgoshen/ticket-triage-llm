# Phase 5 — Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Metrics, Traces, and Experiments tabs plus the metrics service layer, so the dashboard is demo-ready with benchmark results, trace inspection, and experiment comparison.

**Architecture:** All data computed from the SQLite `traces` table on the fly (ADR 0005). A stateless metrics service sits between the trace repository and the Gradio tabs. The triage tab is refactored from a standalone `gr.Blocks` into content within a `gr.Tab` inside an outer tabbed layout. Each tab builds its content inline inside a `gr.Tab` context.

**Tech Stack:** Python 3.11+, Gradio `gr.Blocks`/`gr.Tabs`, SQLite, pydantic, pytest

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `src/ticket_triage_llm/storage/trace_repo.py` | Add `get_distinct_run_ids` to Protocol |
| Modify | `src/ticket_triage_llm/services/trace.py` | Implement stubs + new `get_distinct_run_ids` |
| Modify | `tests/unit/test_sqlite_trace_repo.py` | Tests for new/unstubbed repo methods |
| Modify | `tests/fakes.py` | Add new methods to `FakeTraceRepo` |
| Rewrite | `src/ticket_triage_llm/services/metrics.py` | `list_run_ids`, `get_live_summary`, `group_runs_by_experiment` |
| Create | `tests/unit/test_metrics_service.py` | Tests for metrics service |
| Rewrite | `src/ticket_triage_llm/ui/metrics_tab.py` | Benchmark Results + Live Metrics sections |
| Rewrite | `src/ticket_triage_llm/ui/traces_tab.py` | Filter bar + trace list + detail pane |
| Rewrite | `src/ticket_triage_llm/ui/experiments_tab.py` | Experiment selector + comparison tables |
| Modify | `src/ticket_triage_llm/ui/triage_tab.py` | Refactor from standalone Blocks to inline content |
| Modify | `src/ticket_triage_llm/app.py` | Outer tabbed layout wiring |
| Modify | `docs/future-improvements.md` | Add drift indicator + log-based alerting entries |

---

### Task 1: Trace repo — implement stubs + add `get_distinct_run_ids` (TDD)

**Files:**
- Modify: `tests/unit/test_sqlite_trace_repo.py`
- Modify: `src/ticket_triage_llm/services/trace.py`
- Modify: `src/ticket_triage_llm/storage/trace_repo.py`
- Modify: `tests/fakes.py`

- [ ] **Step 1: Write failing tests for `get_traces_by_provider`**

In `tests/unit/test_sqlite_trace_repo.py`, replace `TestUnimplementedMethods` with real tests:

```python
class TestGetTracesByProvider:
    def test_filters_by_provider(self, repo):
        repo.save_trace(
            _make_trace(request_id="req-1", provider="ollama:qwen3.5:4b")
        )
        repo.save_trace(
            _make_trace(request_id="req-2", provider="ollama:qwen3.5:9b")
        )
        repo.save_trace(
            _make_trace(request_id="req-3", provider="ollama:qwen3.5:4b")
        )
        traces = repo.get_traces_by_provider("ollama:qwen3.5:4b")
        assert len(traces) == 2
        assert all(t.provider == "ollama:qwen3.5:4b" for t in traces)

    def test_returns_empty_for_unknown_provider(self, repo):
        repo.save_trace(_make_trace(request_id="req-1"))
        traces = repo.get_traces_by_provider("unknown:provider")
        assert traces == []

    def test_returns_newest_first(self, repo):
        repo.save_trace(
            _make_trace(
                request_id="old",
                provider="ollama:qwen3.5:4b",
                timestamp=datetime(2026, 4, 17, 10, 0, 0, tzinfo=UTC),
            )
        )
        repo.save_trace(
            _make_trace(
                request_id="new",
                provider="ollama:qwen3.5:4b",
                timestamp=datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC),
            )
        )
        traces = repo.get_traces_by_provider("ollama:qwen3.5:4b")
        assert traces[0].request_id == "new"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_sqlite_trace_repo.py::TestGetTracesByProvider -v`
Expected: FAIL with `NotImplementedError`

- [ ] **Step 3: Implement `get_traces_by_provider`**

In `src/ticket_triage_llm/services/trace.py`, replace the stub:

```python
def get_traces_by_provider(self, provider: str) -> list[TraceRecord]:
    cursor = self._conn.execute(
        "SELECT * FROM traces WHERE provider = ? ORDER BY timestamp DESC",
        (provider,),
    )
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    return [self._row_to_trace(columns, row) for row in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_sqlite_trace_repo.py::TestGetTracesByProvider -v`
Expected: PASS

- [ ] **Step 5: Write failing tests for `get_traces_since`**

```python
class TestGetTracesSince:
    def test_filters_by_timestamp(self, repo):
        repo.save_trace(
            _make_trace(
                request_id="old",
                timestamp=datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC),
            )
        )
        repo.save_trace(
            _make_trace(
                request_id="new",
                timestamp=datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC),
            )
        )
        traces = repo.get_traces_since(datetime(2026, 4, 17, 0, 0, 0, tzinfo=UTC))
        assert len(traces) == 1
        assert traces[0].request_id == "new"

    def test_returns_empty_when_none_match(self, repo):
        repo.save_trace(
            _make_trace(
                request_id="old",
                timestamp=datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC),
            )
        )
        traces = repo.get_traces_since(datetime(2026, 4, 18, 0, 0, 0, tzinfo=UTC))
        assert traces == []

    def test_returns_newest_first(self, repo):
        repo.save_trace(
            _make_trace(
                request_id="early",
                timestamp=datetime(2026, 4, 17, 8, 0, 0, tzinfo=UTC),
            )
        )
        repo.save_trace(
            _make_trace(
                request_id="later",
                timestamp=datetime(2026, 4, 17, 16, 0, 0, tzinfo=UTC),
            )
        )
        traces = repo.get_traces_since(datetime(2026, 4, 17, 0, 0, 0, tzinfo=UTC))
        assert traces[0].request_id == "later"
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_sqlite_trace_repo.py::TestGetTracesSince -v`
Expected: FAIL with `NotImplementedError`

- [ ] **Step 7: Implement `get_traces_since`**

```python
def get_traces_since(self, since: datetime) -> list[TraceRecord]:
    cursor = self._conn.execute(
        "SELECT * FROM traces WHERE timestamp >= ? ORDER BY timestamp DESC",
        (since.isoformat(),),
    )
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    return [self._row_to_trace(columns, row) for row in rows]
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_sqlite_trace_repo.py::TestGetTracesSince -v`
Expected: PASS

- [ ] **Step 9: Write failing tests for `get_distinct_run_ids`**

```python
class TestGetDistinctRunIds:
    def test_returns_distinct_run_ids(self, repo):
        repo.save_trace(_make_trace(request_id="r1", run_id="e1-4b-20260417"))
        repo.save_trace(_make_trace(request_id="r2", run_id="e1-4b-20260417"))
        repo.save_trace(_make_trace(request_id="r3", run_id="e1-9b-20260417"))
        result = repo.get_distinct_run_ids()
        assert len(result) == 2
        run_ids = {r["run_id"] for r in result}
        assert run_ids == {"e1-4b-20260417", "e1-9b-20260417"}

    def test_excludes_null_run_ids(self, repo):
        repo.save_trace(_make_trace(request_id="r1", run_id=None))
        repo.save_trace(_make_trace(request_id="r2", run_id="e1-4b-20260417"))
        result = repo.get_distinct_run_ids()
        assert len(result) == 1
        assert result[0]["run_id"] == "e1-4b-20260417"

    def test_includes_model_and_count(self, repo):
        repo.save_trace(
            _make_trace(request_id="r1", run_id="e1-4b-20260417", model="qwen3.5:4b")
        )
        repo.save_trace(
            _make_trace(request_id="r2", run_id="e1-4b-20260417", model="qwen3.5:4b")
        )
        result = repo.get_distinct_run_ids()
        assert len(result) == 1
        assert result[0]["model"] == "qwen3.5:4b"
        assert result[0]["ticket_count"] == 2

    def test_returns_empty_when_no_runs(self, repo):
        repo.save_trace(_make_trace(request_id="r1", run_id=None))
        result = repo.get_distinct_run_ids()
        assert result == []

    def test_ordered_by_timestamp_desc(self, repo):
        repo.save_trace(
            _make_trace(
                request_id="r1",
                run_id="old-run",
                timestamp=datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC),
            )
        )
        repo.save_trace(
            _make_trace(
                request_id="r2",
                run_id="new-run",
                timestamp=datetime(2026, 4, 17, 10, 0, 0, tzinfo=UTC),
            )
        )
        result = repo.get_distinct_run_ids()
        assert result[0]["run_id"] == "new-run"
        assert result[1]["run_id"] == "old-run"
```

- [ ] **Step 10: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_sqlite_trace_repo.py::TestGetDistinctRunIds -v`
Expected: FAIL with `AttributeError: 'SqliteTraceRepository' object has no attribute 'get_distinct_run_ids'`

- [ ] **Step 11: Add `get_distinct_run_ids` to Protocol**

In `src/ticket_triage_llm/storage/trace_repo.py`, add to the `TraceRepository` Protocol:

```python
def get_distinct_run_ids(self) -> list[dict]: ...
```

- [ ] **Step 12: Implement `get_distinct_run_ids`**

In `src/ticket_triage_llm/services/trace.py`, add to `SqliteTraceRepository`:

```python
def get_distinct_run_ids(self) -> list[dict]:
    cursor = self._conn.execute(
        """
        SELECT run_id, model, MIN(timestamp) as first_ts, COUNT(*) as ticket_count
        FROM traces
        WHERE run_id IS NOT NULL
        GROUP BY run_id
        ORDER BY first_ts DESC
        """
    )
    return [
        {
            "run_id": row[0],
            "model": row[1],
            "timestamp": row[2],
            "ticket_count": row[3],
        }
        for row in cursor.fetchall()
    ]
```

- [ ] **Step 13: Update `FakeTraceRepo`**

In `tests/fakes.py`, replace the stubs and add the new method:

```python
def get_traces_by_provider(self, provider: str) -> list[TraceRecord]:
    return [t for t in self.traces if t.provider == provider]

def get_traces_since(self, since: datetime) -> list[TraceRecord]:
    return [t for t in self.traces if t.timestamp >= since]

def get_distinct_run_ids(self) -> list[dict]:
    from collections import defaultdict

    runs: dict[str, dict] = {}
    for t in self.traces:
        if t.run_id is None:
            continue
        if t.run_id not in runs:
            runs[t.run_id] = {
                "run_id": t.run_id,
                "model": t.model,
                "timestamp": t.timestamp.isoformat(),
                "ticket_count": 0,
            }
        runs[t.run_id]["ticket_count"] += 1
    return sorted(runs.values(), key=lambda r: r["timestamp"], reverse=True)
```

- [ ] **Step 14: Run all trace repo tests**

Run: `uv run pytest tests/unit/test_sqlite_trace_repo.py -v`
Expected: ALL PASS

- [ ] **Step 15: Run full test suite + lint**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: ALL PASS, no lint errors

- [ ] **Step 16: Commit**

```bash
git add src/ticket_triage_llm/services/trace.py src/ticket_triage_llm/storage/trace_repo.py tests/unit/test_sqlite_trace_repo.py tests/fakes.py
git commit -m "feat: implement trace repo stubs + add get_distinct_run_ids"
```

---

### Task 2: Metrics service (TDD)

**Files:**
- Create: `tests/unit/test_metrics_service.py`
- Modify: `src/ticket_triage_llm/services/metrics.py`

- [ ] **Step 1: Write failing tests for `list_run_ids`**

Create `tests/unit/test_metrics_service.py`:

```python
from datetime import UTC, datetime

from ticket_triage_llm.schemas.trace import TraceRecord
from ticket_triage_llm.services.metrics import (
    get_live_summary,
    group_runs_by_experiment,
    list_run_ids,
)
from tests.fakes import FakeTraceRepo


def _make_trace(**overrides) -> TraceRecord:
    defaults = {
        "request_id": "req-001",
        "timestamp": datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC),
        "model": "qwen3.5:4b",
        "provider": "ollama:qwen3.5:4b",
        "prompt_version": "v1",
        "ticket_body": "Test ticket",
        "guardrail_result": "pass",
        "validation_status": "valid",
        "retry_count": 0,
        "latency_ms": 1500.0,
        "tokens_input": 100,
        "tokens_output": 50,
        "tokens_total": 150,
        "status": "success",
    }
    defaults.update(overrides)
    return TraceRecord(**defaults)


class TestListRunIds:
    def test_returns_run_ids_from_repo(self):
        repo = FakeTraceRepo([
            _make_trace(request_id="r1", run_id="e1-4b-20260417"),
            _make_trace(request_id="r2", run_id="e1-4b-20260417"),
            _make_trace(request_id="r3", run_id="e1-9b-20260417"),
        ])
        result = list_run_ids(repo)
        assert len(result) == 2
        run_ids = {r["run_id"] for r in result}
        assert run_ids == {"e1-4b-20260417", "e1-9b-20260417"}

    def test_returns_empty_when_no_runs(self):
        repo = FakeTraceRepo([_make_trace(request_id="r1", run_id=None)])
        result = list_run_ids(repo)
        assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_metrics_service.py::TestListRunIds -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `list_run_ids`**

Rewrite `src/ticket_triage_llm/services/metrics.py`:

```python
"""Metrics aggregation from traces — Phase 5."""

from ticket_triage_llm.storage.trace_repo import TraceRepository


def list_run_ids(trace_repo: TraceRepository) -> list[dict]:
    return trace_repo.get_distinct_run_ids()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_metrics_service.py::TestListRunIds -v`
Expected: PASS

- [ ] **Step 5: Write failing tests for `get_live_summary`**

```python
class TestGetLiveSummary:
    def test_computes_stats_from_live_traffic(self):
        repo = FakeTraceRepo([
            _make_trace(
                request_id="r1", run_id=None, latency_ms=1000.0,
                status="success", retry_count=0,
            ),
            _make_trace(
                request_id="r2", run_id=None, latency_ms=2000.0,
                status="success", retry_count=1,
            ),
            _make_trace(
                request_id="r3", run_id=None, latency_ms=3000.0,
                status="failure", failure_category="parse_failure",
                retry_count=0,
            ),
        ])
        result = get_live_summary(repo, window_hours=None)
        assert result["total_requests"] == 3
        assert result["success_rate"] == pytest.approx(2 / 3)
        assert result["error_rate"] == pytest.approx(1 / 3)
        assert result["retry_rate"] == pytest.approx(1 / 3)
        assert result["avg_latency_ms"] == pytest.approx(2000.0)

    def test_excludes_eval_traffic(self):
        repo = FakeTraceRepo([
            _make_trace(request_id="r1", run_id=None, latency_ms=1000.0),
            _make_trace(request_id="r2", run_id="e1-4b-20260417", latency_ms=500.0),
        ])
        result = get_live_summary(repo, window_hours=None)
        assert result["total_requests"] == 1
        assert result["avg_latency_ms"] == pytest.approx(1000.0)

    def test_returns_zeros_when_no_live_traffic(self):
        repo = FakeTraceRepo([
            _make_trace(request_id="r1", run_id="e1-4b-20260417"),
        ])
        result = get_live_summary(repo, window_hours=None)
        assert result["total_requests"] == 0
        assert result["success_rate"] == 0.0
        assert result["avg_latency_ms"] == 0.0

    def test_respects_window_hours(self):
        repo = FakeTraceRepo([
            _make_trace(
                request_id="old", run_id=None,
                timestamp=datetime(2026, 4, 16, 0, 0, 0, tzinfo=UTC),
                latency_ms=5000.0,
            ),
            _make_trace(
                request_id="recent", run_id=None,
                timestamp=datetime(2026, 4, 17, 23, 0, 0, tzinfo=UTC),
                latency_ms=1000.0,
            ),
        ])
        # window_hours=24 from "now" — mock by using get_traces_since
        # FakeTraceRepo.get_traces_since filters by timestamp
        result = get_live_summary(repo, window_hours=None)
        assert result["total_requests"] == 2
```

Add `import pytest` to the top of the test file.

- [ ] **Step 6: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_metrics_service.py::TestGetLiveSummary -v`
Expected: FAIL with `ImportError` (get_live_summary not yet defined)

- [ ] **Step 7: Implement `get_live_summary`**

Add to `src/ticket_triage_llm/services/metrics.py`:

```python
import statistics
from datetime import UTC, datetime, timedelta

from ticket_triage_llm.schemas.trace import TraceRecord
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


def _get_live_traces(
    trace_repo: TraceRepository, window_hours: int | None
) -> list[TraceRecord]:
    if window_hours is not None:
        since = datetime.now(UTC) - timedelta(hours=window_hours)
        all_traces = trace_repo.get_traces_since(since)
    else:
        all_traces = trace_repo.get_all_traces()
    return [t for t in all_traces if t.run_id is None]


def get_live_summary(
    trace_repo: TraceRepository, window_hours: int | None
) -> dict:
    traces = _get_live_traces(trace_repo, window_hours)
    total = len(traces)
    if total == 0:
        return {
            "total_requests": 0,
            "success_rate": 0.0,
            "avg_latency_ms": 0.0,
            "p50_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "retry_rate": 0.0,
            "error_rate": 0.0,
        }

    successes = sum(1 for t in traces if t.status == "success")
    retried = sum(1 for t in traces if t.retry_count > 0)
    latencies = [t.latency_ms for t in traces]

    return {
        "total_requests": total,
        "success_rate": successes / total,
        "avg_latency_ms": statistics.mean(latencies),
        "p50_latency_ms": _percentile(latencies, 50),
        "p95_latency_ms": _percentile(latencies, 95),
        "retry_rate": retried / total,
        "error_rate": (total - successes) / total,
    }
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_metrics_service.py::TestGetLiveSummary -v`
Expected: PASS

- [ ] **Step 9: Write failing tests for `group_runs_by_experiment`**

```python
class TestGroupRunsByExperiment:
    def test_groups_by_prefix(self):
        run_ids = [
            {"run_id": "e1-4b-20260417", "model": "qwen3.5:4b", "timestamp": "2026-04-17", "ticket_count": 35},
            {"run_id": "e1-9b-20260417", "model": "qwen3.5:9b", "timestamp": "2026-04-17", "ticket_count": 35},
            {"run_id": "e3-4b-validated-20260417", "model": "qwen3.5:4b", "timestamp": "2026-04-17", "ticket_count": 35},
            {"run_id": "adv-4b-20260418", "model": "qwen3.5:4b", "timestamp": "2026-04-18", "ticket_count": 14},
        ]
        result = group_runs_by_experiment(run_ids)
        assert "E1: Model Size Comparison" in result
        assert len(result["E1: Model Size Comparison"]) == 2
        assert "E3: Validation Impact" in result
        assert len(result["E3: Validation Impact"]) == 1
        assert "Adversarial: Injection Defense" in result
        assert len(result["Adversarial: Injection Defense"]) == 1

    def test_unknown_prefix_grouped_as_other(self):
        run_ids = [
            {"run_id": "custom-run-123", "model": "qwen3.5:4b", "timestamp": "2026-04-17", "ticket_count": 10},
        ]
        result = group_runs_by_experiment(run_ids)
        assert "Other" in result

    def test_empty_input(self):
        result = group_runs_by_experiment([])
        assert result == {}
```

- [ ] **Step 10: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_metrics_service.py::TestGroupRunsByExperiment -v`
Expected: FAIL

- [ ] **Step 11: Implement `group_runs_by_experiment`**

Add to `src/ticket_triage_llm/services/metrics.py`:

```python
EXPERIMENT_PREFIXES = {
    "e1-": "E1: Model Size Comparison",
    "e2-": "E2: Model Size vs Engineering Controls",
    "e3-": "E3: Validation Impact",
    "e4-": "E4: Prompt Comparison",
    "adv-": "Adversarial: Injection Defense",
}


def group_runs_by_experiment(run_ids: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for run in run_ids:
        rid = run["run_id"]
        matched = False
        for prefix, name in EXPERIMENT_PREFIXES.items():
            if rid.startswith(prefix):
                groups.setdefault(name, []).append(run)
                matched = True
                break
        if not matched:
            groups.setdefault("Other", []).append(run)
    return groups
```

- [ ] **Step 12: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_metrics_service.py -v`
Expected: ALL PASS

- [ ] **Step 13: Run full test suite + lint**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: ALL PASS

- [ ] **Step 14: Commit**

```bash
git add src/ticket_triage_llm/services/metrics.py tests/unit/test_metrics_service.py
git commit -m "feat: add metrics service with list_run_ids, get_live_summary, group_runs_by_experiment"
```

---

### Task 3: Refactor triage tab from standalone Blocks to inline content

**Files:**
- Modify: `src/ticket_triage_llm/ui/triage_tab.py`

This task changes `build_triage_tab` so it no longer creates its own `gr.Blocks` context. Instead, it builds components directly into the calling context (a `gr.Tab` created by `app.py`). The function signature changes to `build_triage_tab_content` and returns `None`.

- [ ] **Step 1: Refactor `build_triage_tab` to `build_triage_tab_content`**

Rewrite `src/ticket_triage_llm/ui/triage_tab.py`:

```python
"""Triage tab — ticket input, model selection, result display — Phase 2."""

import gradio as gr

from ticket_triage_llm.schemas.trace import TriageFailure, TriageSuccess
from ticket_triage_llm.services.provider_router import ProviderRegistry
from ticket_triage_llm.services.triage import run_triage
from ticket_triage_llm.storage.trace_repo import TraceRepository


def build_triage_tab_content(
    registry: ProviderRegistry,
    trace_repo: TraceRepository,
    default_provider: str | None = None,
    guardrail_max_length: int = 10_000,
) -> None:
    provider_names = registry.list_names()
    default_value = (
        default_provider if default_provider in provider_names else provider_names[0]
    )

    def handle_triage(provider_name: str, ticket_subject: str, ticket_body: str):
        if not ticket_body.strip():
            return "Error: ticket body is required", ""

        provider = registry.get(provider_name)
        result, trace = run_triage(
            ticket_body=ticket_body,
            ticket_subject=ticket_subject,
            provider=provider,
            prompt_version="v1",
            trace_repo=trace_repo,
            guardrail_max_length=guardrail_max_length,
        )

        trace_text = (
            f"Request ID: {trace.request_id}\n"
            f"Model: {trace.model}\n"
            f"Latency: {trace.latency_ms:.0f} ms\n"
            f"Tokens: {trace.tokens_total} "
            f"(in={trace.tokens_input}, out={trace.tokens_output})\n"
            f"Validation: {trace.validation_status}\n"
            f"Retry Count: {trace.retry_count}\n"
            f"Guardrail: {trace.guardrail_result}"
        )
        if trace.guardrail_matched_rules:
            trace_text += f"\nMatched Rules: {', '.join(trace.guardrail_matched_rules)}"

        if isinstance(result, TriageSuccess):
            output = result.output
            esc = "Yes" if output.escalation else "No"
            cat = output.category.replace("_", " ").title()
            sev = output.severity.title()
            team = output.routing_team.title()
            result_text = (
                f"### Triage Result\n\n"
                f"**Category:** {cat}  \n"
                f"**Severity:** {sev}  \n"
                f"**Routing Team:** {team}  \n"
                f"**Escalation:** {esc}\n\n"
                f"---\n\n"
                f"**Summary**  \n{output.summary}\n\n"
                f"**Business Impact**  \n"
                f"{output.business_impact}\n\n"
                f"**Draft Reply**  \n{output.draft_reply}"
            )
            return result_text, trace_text

        if isinstance(result, TriageFailure):
            if result.category == "guardrail_blocked":
                result_text = (
                    "**Ticket Blocked**\n\n"
                    "This ticket was flagged by the safety guardrail "
                    "and was not sent to the model."
                )
            elif result.category == "parse_failure":
                result_text = (
                    "**Triage Unavailable**\n\n"
                    "The model could not produce a structured response "
                    "for this ticket. Try again or select a different "
                    "model from the dropdown."
                )
            else:
                result_text = (
                    "**Triage Failed**\n\n"
                    f"The model response did not pass validation "
                    f"({result.category}). Try again or select a "
                    f"different model."
                )
            return result_text, trace_text

        return "Unexpected result type", ""

    gr.Markdown("# Ticket Triage LLM")

    with gr.Row():
        with gr.Column(scale=1):
            provider_dropdown = gr.Dropdown(
                choices=provider_names,
                value=default_value,
                label="Model",
            )
            subject_input = gr.Textbox(
                label="Subject (optional)",
                placeholder="e.g., Cannot login to account",
                lines=1,
            )
            body_input = gr.Textbox(
                label="Ticket Body",
                placeholder="Paste the support ticket text here...",
                lines=10,
            )
            with gr.Row():
                submit_btn = gr.Button("Triage", variant="primary", scale=2)
                cancel_btn = gr.Button("Cancel", variant="stop", scale=1)
                clear_btn = gr.Button("New Ticket", scale=1)

        with gr.Column(scale=1):
            status_output = gr.Markdown(value="", label="Status")
            result_output = gr.Markdown(label="Triage Result")
            with gr.Accordion("Trace Details", open=False):
                trace_output = gr.Textbox(
                    label="Trace Summary",
                    lines=8,
                    interactive=False,
                )

    def run_triage_with_status(provider_name, ticket_subject, ticket_body):
        result_text, trace_text = handle_triage(
            provider_name, ticket_subject, ticket_body
        )
        return "", result_text, trace_text

    triage_event = submit_btn.click(
        fn=lambda: ("*Processing ticket...*", "", ""),
        inputs=None,
        outputs=[status_output, result_output, trace_output],
    ).then(
        fn=run_triage_with_status,
        inputs=[provider_dropdown, subject_input, body_input],
        outputs=[status_output, result_output, trace_output],
    )

    cancel_btn.click(
        fn=lambda: ("*Ticket submission cancelled.*", "", ""),
        inputs=None,
        outputs=[status_output, result_output, trace_output],
        cancels=[triage_event],
    )

    clear_btn.click(
        fn=lambda: ("", "", "", "", ""),
        inputs=None,
        outputs=[
            subject_input,
            body_input,
            status_output,
            result_output,
            trace_output,
        ],
    )
```

The key change: removed `with gr.Blocks(title="Ticket Triage LLM") as demo:` wrapper and `return demo`. The function now adds components into whatever Blocks context is active when it's called.

- [ ] **Step 2: Run full test suite to check nothing breaks**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: PASS (triage_tab is in the coverage omit list, so no test failures expected from the refactor. The integration test for the API route doesn't import triage_tab.)

- [ ] **Step 3: Commit**

```bash
git add src/ticket_triage_llm/ui/triage_tab.py
git commit -m "refactor: change triage tab from standalone Blocks to inline content builder"
```

---

### Task 4: App.py — outer tabbed layout

**Files:**
- Modify: `src/ticket_triage_llm/app.py`

- [ ] **Step 1: Rewrite app.py with tabbed layout**

```python
"""FastAPI + Gradio entry point — Phase 5."""

import os

import gradio as gr
import uvicorn
from fastapi import FastAPI

from ticket_triage_llm.api.triage_route import configure as configure_api
from ticket_triage_llm.api.triage_route import router as api_router
from ticket_triage_llm.config import Settings
from ticket_triage_llm.logging_config import configure_logging
from ticket_triage_llm.providers.ollama_qwen import OllamaQwenProvider
from ticket_triage_llm.services.provider_router import ProviderRegistry
from ticket_triage_llm.services.trace import SqliteTraceRepository
from ticket_triage_llm.storage.db import get_connection, init_schema
from ticket_triage_llm.ui.experiments_tab import build_experiments_tab_content
from ticket_triage_llm.ui.metrics_tab import build_metrics_tab_content
from ticket_triage_llm.ui.traces_tab import build_traces_tab_content
from ticket_triage_llm.ui.triage_tab import build_triage_tab_content


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings.log_level)

    os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)
    conn = get_connection(settings.db_path)
    init_schema(conn)
    trace_repo = SqliteTraceRepository(conn)

    registry = ProviderRegistry()

    model_list = [m.strip() for m in settings.ollama_models.split(",") if m.strip()]

    if not model_list:
        model_list = [settings.ollama_model]

    for model_name in model_list:
        provider = OllamaQwenProvider(
            model=model_name,
            base_url=settings.ollama_base_url,
        )
        registry.register(provider)

    configure_api(registry, trace_repo, settings.guardrail_max_length)

    with gr.Blocks(title="Ticket Triage LLM") as gradio_app:
        with gr.Tabs():
            with gr.Tab("Triage"):
                build_triage_tab_content(
                    registry,
                    trace_repo,
                    default_provider=f"ollama:{settings.ollama_model}",
                    guardrail_max_length=settings.guardrail_max_length,
                )
            with gr.Tab("Metrics"):
                build_metrics_tab_content(trace_repo)
            with gr.Tab("Traces"):
                build_traces_tab_content(trace_repo)
            with gr.Tab("Experiments"):
                build_experiments_tab_content(trace_repo)

    app = FastAPI(title="Ticket Triage LLM", version="0.3.0")
    app.include_router(api_router)
    app = gr.mount_gradio_app(app, gradio_app, path="/")

    return app


if __name__ == "__main__":
    application = create_app()
    uvicorn.run(application, host="0.0.0.0", port=7860)
```

Note: This will fail to import until we implement the tab content functions in Tasks 5-7. That's expected — we're wiring the skeleton now and implementing the tabs next.

- [ ] **Step 2: Run lint**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/ticket_triage_llm/app.py
git commit -m "feat: wire outer tabbed layout with Triage, Metrics, Traces, Experiments tabs"
```

---

### Task 5: Metrics tab UI (judgment-based)

**Files:**
- Rewrite: `src/ticket_triage_llm/ui/metrics_tab.py`

- [ ] **Step 1: Implement the Metrics tab**

```python
"""Metrics tab — benchmark results and live metrics — Phase 5."""

import logging
from pathlib import Path

import gradio as gr

from ticket_triage_llm.eval.datasets import load_dataset
from ticket_triage_llm.eval.runners.summarize_results import summarize_run
from ticket_triage_llm.services.metrics import get_live_summary, list_run_ids
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)

NORMAL_DATASET_PATH = Path("data/normal_set.jsonl")

WINDOW_OPTIONS = {"1 hour": 1, "24 hours": 24, "7 days": 168, "All time": None}


def build_metrics_tab_content(trace_repo: TraceRepository) -> None:
    tickets = []
    if NORMAL_DATASET_PATH.exists():
        try:
            tickets = load_dataset(NORMAL_DATASET_PATH)
        except Exception:
            logger.warning("Could not load normal dataset for benchmark summaries")

    def _get_run_choices():
        runs = list_run_ids(trace_repo)
        if not runs:
            return [], None
        choices = [
            f"{r['run_id']} — {r['model']} ({r['ticket_count']} tickets)"
            for r in runs
        ]
        return choices, choices[0] if choices else None

    def _extract_run_id(choice: str | None) -> str | None:
        if not choice:
            return None
        return choice.split(" — ")[0]

    def load_benchmark(choice: str | None):
        run_id = _extract_run_id(choice)
        if not run_id or not tickets:
            return "No benchmark data available.", []

        try:
            metrics = summarize_run(run_id, tickets, trace_repo)
        except ValueError:
            return "No traces found for this run.", []

        kpi_text = (
            f"**Category Accuracy:** {metrics.category_accuracy:.1%}  \n"
            f"**JSON Validity:** {metrics.json_valid_rate:.1%}  \n"
            f"**Schema Pass Rate:** {metrics.schema_pass_rate:.1%}  \n"
            f"**p95 Latency:** {metrics.p95_latency_ms:.0f} ms  \n"
            f"**Retry Rate:** {metrics.retry_rate:.1%}  \n"
            f"**Success:** {metrics.successful_tickets}/{metrics.total_tickets}"
        )

        table_data = [[
            metrics.model,
            f"{metrics.category_accuracy:.1%}",
            f"{metrics.severity_accuracy:.1%}",
            f"{metrics.routing_accuracy:.1%}",
            f"{metrics.json_valid_rate:.1%}",
            f"{metrics.schema_pass_rate:.1%}",
            f"{metrics.retry_rate:.1%}",
            f"{metrics.p50_latency_ms:.0f}",
            f"{metrics.p95_latency_ms:.0f}",
            f"{metrics.avg_tokens_per_second:.1f}" if metrics.avg_tokens_per_second else "N/A",
            f"{metrics.successful_tickets}/{metrics.total_tickets}",
        ]]

        return kpi_text, table_data

    def refresh_runs():
        choices, default = _get_run_choices()
        return gr.update(choices=choices, value=default)

    def load_live(window_label: str):
        window_hours = WINDOW_OPTIONS.get(window_label)
        summary = get_live_summary(trace_repo, window_hours)

        if summary["total_requests"] == 0:
            return "No live traffic recorded yet. Submit tickets through the Triage tab to see live metrics."

        return (
            f"**Total Requests:** {summary['total_requests']}  \n"
            f"**Success Rate:** {summary['success_rate']:.1%}  \n"
            f"**Avg Latency:** {summary['avg_latency_ms']:.0f} ms  \n"
            f"**p50 Latency:** {summary['p50_latency_ms']:.0f} ms  \n"
            f"**p95 Latency:** {summary['p95_latency_ms']:.0f} ms  \n"
            f"**Retry Rate:** {summary['retry_rate']:.1%}  \n"
            f"**Error Rate:** {summary['error_rate']:.1%}"
        )

    # --- Benchmark Results section ---
    gr.Markdown("## Benchmark Results")

    initial_choices, initial_default = _get_run_choices()

    with gr.Row():
        run_selector = gr.Dropdown(
            choices=initial_choices,
            value=initial_default,
            label="Select Run",
            scale=4,
        )
        refresh_btn = gr.Button("Refresh", scale=1)

    benchmark_kpi = gr.Markdown(
        value="Select a run to view benchmark results."
        if initial_choices
        else "No benchmark runs found. Run an experiment to see results here."
    )

    benchmark_table = gr.Dataframe(
        headers=[
            "Model", "Cat Acc", "Sev Acc", "Route Acc",
            "JSON Valid %", "Schema Pass %", "Retry %",
            "p50 ms", "p95 ms", "Tok/s", "Success",
        ],
        interactive=False,
    )

    run_selector.change(
        fn=load_benchmark,
        inputs=[run_selector],
        outputs=[benchmark_kpi, benchmark_table],
    )

    refresh_btn.click(fn=refresh_runs, outputs=[run_selector])

    # --- Live Metrics section ---
    gr.Markdown("---")
    gr.Markdown("## Live Metrics")

    with gr.Row():
        window_selector = gr.Radio(
            choices=list(WINDOW_OPTIONS.keys()),
            value="All time",
            label="Time Window",
        )
        live_refresh_btn = gr.Button("Refresh")

    live_kpi = gr.Markdown(
        value="No live traffic recorded yet. Submit tickets through the Triage tab to see live metrics."
    )

    window_selector.change(
        fn=load_live,
        inputs=[window_selector],
        outputs=[live_kpi],
    )

    live_refresh_btn.click(
        fn=load_live,
        inputs=[window_selector],
        outputs=[live_kpi],
    )
```

- [ ] **Step 2: Run lint**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/ticket_triage_llm/ui/metrics_tab.py
git commit -m "feat: implement Metrics tab with Benchmark Results and Live Metrics sections"
```

---

### Task 6: Traces tab UI (judgment-based)

**Files:**
- Rewrite: `src/ticket_triage_llm/ui/traces_tab.py`

- [ ] **Step 1: Implement the Traces tab**

```python
"""Traces tab — request inspection and filtering — Phase 5."""

import json
import logging

import gradio as gr

from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)

VALIDATION_OPTIONS = ["All", "valid", "valid_after_retry", "invalid", "skipped"]
STATUS_OPTIONS = ["All", "success", "failure"]
LIMIT_OPTIONS = [25, 50, 100]

TABLE_HEADERS = [
    "Timestamp", "Model", "Status", "Validation",
    "Latency (ms)", "Tokens", "Retry", "Guardrail",
]


def build_traces_tab_content(trace_repo: TraceRepository) -> None:
    def _load_traces(provider_filter, validation_filter, status_filter, limit):
        limit = int(limit)
        traces = trace_repo.get_recent_traces(limit=500)

        if provider_filter and provider_filter != "All":
            traces = [t for t in traces if t.provider == provider_filter]
        if validation_filter and validation_filter != "All":
            traces = [t for t in traces if t.validation_status == validation_filter]
        if status_filter and status_filter != "All":
            traces = [t for t in traces if t.status == status_filter]

        traces = traces[:limit]

        rows = []
        for t in traces:
            rows.append([
                t.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                t.model,
                t.status,
                t.validation_status,
                f"{t.latency_ms:.0f}",
                str(t.tokens_total),
                str(t.retry_count),
                t.guardrail_result,
            ])
        return rows

    def _get_providers():
        traces = trace_repo.get_recent_traces(limit=500)
        providers = sorted({t.provider for t in traces})
        return ["All"] + providers

    def _format_detail(evt: gr.SelectData, table_data):
        if evt.index is None or not table_data:
            return "Select a row to view trace details."

        row_idx = evt.index[0] if isinstance(evt.index, list) else evt.index
        if row_idx >= len(table_data):
            return "Select a row to view trace details."

        row = table_data[row_idx]
        timestamp_str = row[0]

        traces = trace_repo.get_recent_traces(limit=500)
        trace = None
        for t in traces:
            if t.timestamp.strftime("%Y-%m-%d %H:%M:%S") == timestamp_str and t.model == row[1]:
                trace = t
                break

        if not trace:
            return "Could not find trace details."

        triage_json = ""
        if trace.triage_output_json:
            try:
                parsed = json.loads(trace.triage_output_json)
                triage_json = json.dumps(parsed, indent=2)
            except json.JSONDecodeError:
                triage_json = trace.triage_output_json

        detail = (
            f"### Trace Details\n\n"
            f"**Metadata**  \n"
            f"Request ID: `{trace.request_id}`  \n"
            f"Run ID: `{trace.run_id or 'live'}`  \n"
            f"Ticket ID: `{trace.ticket_id or 'N/A'}`  \n"
            f"Model: {trace.model}  \n"
            f"Provider: {trace.provider}  \n"
            f"Prompt Version: {trace.prompt_version}\n\n"
            f"**Timing**  \n"
            f"Latency: {trace.latency_ms:.0f} ms  \n"
            f"Tokens: {trace.tokens_total} "
            f"(in={trace.tokens_input}, out={trace.tokens_output})  \n"
            f"Tokens/sec: "
            f"{trace.tokens_per_second:.1f}" if trace.tokens_per_second else "N/A"
        )
        detail += (
            f"  \nEstimated Cost: ${trace.estimated_cost:.4f}\n\n"
            f"**Pipeline**  \n"
            f"Guardrail: {trace.guardrail_result}  \n"
        )
        if trace.guardrail_matched_rules:
            detail += f"Matched Rules: {', '.join(trace.guardrail_matched_rules)}  \n"
        detail += (
            f"Validation: {trace.validation_status}  \n"
            f"Retry Count: {trace.retry_count}  \n"
            f"Failure Category: {trace.failure_category or 'N/A'}\n\n"
        )

        if trace.ticket_body:
            body_preview = trace.ticket_body[:500]
            if len(trace.ticket_body) > 500:
                body_preview += "..."
            detail += f"**Ticket Body**  \n```\n{body_preview}\n```\n\n"

        if trace.raw_model_output:
            raw_preview = trace.raw_model_output[:1000]
            if len(trace.raw_model_output) > 1000:
                raw_preview += "..."
            detail += f"**Raw Model Output**  \n```\n{raw_preview}\n```\n\n"

        if triage_json:
            detail += f"**Triage Output**  \n```json\n{triage_json}\n```"

        return detail

    gr.Markdown("## Trace Explorer")

    initial_providers = _get_providers()

    with gr.Row():
        provider_filter = gr.Dropdown(
            choices=initial_providers,
            value="All",
            label="Provider",
        )
        validation_filter = gr.Dropdown(
            choices=VALIDATION_OPTIONS,
            value="All",
            label="Validation Status",
        )
        status_filter = gr.Dropdown(
            choices=STATUS_OPTIONS,
            value="All",
            label="Status",
        )
        limit_selector = gr.Dropdown(
            choices=[str(x) for x in LIMIT_OPTIONS],
            value="50",
            label="Limit",
        )
        refresh_btn = gr.Button("Refresh")

    initial_data = _load_traces("All", "All", "All", 50)

    trace_table = gr.Dataframe(
        value=initial_data,
        headers=TABLE_HEADERS,
        interactive=False,
    )

    trace_detail = gr.Markdown(
        value="Select a row to view trace details.",
    )

    def refresh_traces(provider, validation, status, limit):
        rows = _load_traces(provider, validation, status, limit)
        providers = _get_providers()
        return rows, gr.update(choices=providers)

    refresh_btn.click(
        fn=refresh_traces,
        inputs=[provider_filter, validation_filter, status_filter, limit_selector],
        outputs=[trace_table, provider_filter],
    )

    for filt in [provider_filter, validation_filter, status_filter, limit_selector]:
        filt.change(
            fn=_load_traces,
            inputs=[provider_filter, validation_filter, status_filter, limit_selector],
            outputs=[trace_table],
        )

    trace_table.select(
        fn=_format_detail,
        inputs=[trace_table],
        outputs=[trace_detail],
    )
```

- [ ] **Step 2: Run lint**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/ticket_triage_llm/ui/traces_tab.py
git commit -m "feat: implement Traces tab with filtering and click-to-inspect detail"
```

---

### Task 7: Experiments tab UI (judgment-based, Tier 2)

**Files:**
- Rewrite: `src/ticket_triage_llm/ui/experiments_tab.py`

- [ ] **Step 1: Implement the Experiments tab**

```python
"""Experiments tab — side-by-side experiment comparison — Phase 5."""

import logging
from pathlib import Path

import gradio as gr

from ticket_triage_llm.eval.datasets import load_dataset
from ticket_triage_llm.eval.runners.summarize_results import summarize_run
from ticket_triage_llm.services.metrics import group_runs_by_experiment, list_run_ids
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)

NORMAL_DATASET_PATH = Path("data/normal_set.jsonl")

EXPERIMENT_DESCRIPTIONS = {
    "E1: Model Size Comparison": "How does quality scale with model size on consumer hardware? Compares Qwen 3.5 2B vs 4B vs 9B.",
    "E2: Model Size vs Engineering Controls": "Can a smaller model with full validation match a larger model without? Smallest-with-validation vs largest-without.",
    "E3: Validation Impact": "What do engineering controls actually buy? Full pipeline vs no validation on same model.",
    "E4: Prompt Comparison": "How much does prompt design contribute? Prompt v1 vs v2 on same model.",
    "Adversarial: Injection Defense": "Per-layer mitigation effectiveness against the adversarial ticket set.",
}

BENCHMARK_HEADERS = [
    "Model", "Cat Acc", "Sev Acc", "Route Acc",
    "JSON Valid %", "Schema Pass %", "Retry %",
    "p50 ms", "p95 ms", "Tok/s", "Success",
]

ADVERSARIAL_HEADERS = [
    "Model", "Tickets", "Success", "Failure",
    "Parse Fail", "Guardrail Blocked",
]


def build_experiments_tab_content(trace_repo: TraceRepository) -> None:
    tickets = []
    if NORMAL_DATASET_PATH.exists():
        try:
            tickets = load_dataset(NORMAL_DATASET_PATH)
        except Exception:
            logger.warning("Could not load normal dataset for experiment summaries")

    def _get_experiment_choices():
        runs = list_run_ids(trace_repo)
        groups = group_runs_by_experiment(runs)
        return list(groups.keys()) if groups else []

    def _load_experiment(experiment_name: str | None):
        if not experiment_name:
            return "Select an experiment.", []

        description = EXPERIMENT_DESCRIPTIONS.get(experiment_name, "")
        desc_text = f"**{experiment_name}**\n\n{description}\n\n"

        runs = list_run_ids(trace_repo)
        groups = group_runs_by_experiment(runs)
        experiment_runs = groups.get(experiment_name, [])

        if not experiment_runs:
            return desc_text + "No runs found for this experiment.", []

        is_adversarial = experiment_name.startswith("Adversarial")

        table_rows = []
        for run in experiment_runs:
            run_id = run["run_id"]
            if is_adversarial:
                traces = trace_repo.get_traces_by_run(run_id)
                total = len(traces)
                successes = sum(1 for t in traces if t.status == "success")
                failures = sum(1 for t in traces if t.status == "failure")
                parse_fails = sum(
                    1 for t in traces
                    if t.failure_category == "parse_failure"
                )
                blocked = sum(
                    1 for t in traces
                    if t.guardrail_result == "block"
                )
                table_rows.append([
                    run["model"],
                    str(total),
                    str(successes),
                    str(failures),
                    str(parse_fails),
                    str(blocked),
                ])
            else:
                if not tickets:
                    table_rows.append([
                        run["model"], "N/A", "N/A", "N/A",
                        "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
                    ])
                    continue
                try:
                    m = summarize_run(run_id, tickets, trace_repo)
                    tps = f"{m.avg_tokens_per_second:.1f}" if m.avg_tokens_per_second else "N/A"
                    table_rows.append([
                        m.model,
                        f"{m.category_accuracy:.1%}",
                        f"{m.severity_accuracy:.1%}",
                        f"{m.routing_accuracy:.1%}",
                        f"{m.json_valid_rate:.1%}",
                        f"{m.schema_pass_rate:.1%}",
                        f"{m.retry_rate:.1%}",
                        f"{m.p50_latency_ms:.0f}",
                        f"{m.p95_latency_ms:.0f}",
                        tps,
                        f"{m.successful_tickets}/{m.total_tickets}",
                    ])
                except ValueError:
                    logger.warning("Could not summarize run %s", run_id)

        headers = ADVERSARIAL_HEADERS if is_adversarial else BENCHMARK_HEADERS
        return desc_text, table_rows

    gr.Markdown("## Experiment Comparison")

    initial_choices = _get_experiment_choices()

    experiment_selector = gr.Dropdown(
        choices=initial_choices,
        value=initial_choices[0] if initial_choices else None,
        label="Select Experiment",
    )

    refresh_btn = gr.Button("Refresh")

    experiment_desc = gr.Markdown(
        value="Select an experiment to view comparison."
        if initial_choices
        else "No experiment runs found. Run experiments to see results here."
    )

    experiment_table = gr.Dataframe(
        headers=BENCHMARK_HEADERS,
        interactive=False,
    )

    def on_select(experiment_name):
        desc, rows = _load_experiment(experiment_name)
        is_adversarial = experiment_name and experiment_name.startswith("Adversarial")
        headers = ADVERSARIAL_HEADERS if is_adversarial else BENCHMARK_HEADERS
        return desc, gr.update(value=rows, headers=headers)

    experiment_selector.change(
        fn=on_select,
        inputs=[experiment_selector],
        outputs=[experiment_desc, experiment_table],
    )

    def on_refresh():
        choices = _get_experiment_choices()
        return gr.update(choices=choices, value=choices[0] if choices else None)

    refresh_btn.click(fn=on_refresh, outputs=[experiment_selector])
```

- [ ] **Step 2: Run lint**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/ticket_triage_llm/ui/experiments_tab.py
git commit -m "feat: implement Experiments tab with side-by-side comparison"
```

---

### Task 8: Update future-improvements.md

**Files:**
- Modify: `docs/future-improvements.md`

- [ ] **Step 1: Add two new entries**

Add these two sections at the end of `docs/future-improvements.md`, before the closing `---` if any, matching the existing entry structure exactly:

```markdown
---

## Category-distribution drift indicator

**What it would add:** A chart in the Live Metrics section showing the distribution of assigned categories over time, flagging when a single category dominates recent traffic (>70%) as a signal that input distribution or model behavior has shifted.

**Why it's deferred:** Requires enough live traffic to produce a meaningful distribution. During a 5-minute demo, the volume of live requests is too low to show drift. The chart would render as single bars or be empty, undermining rather than supporting the demo narrative.

**What was done instead:** The Metrics tab shows rolling aggregate metrics (success rate, latency, retry rate) that are meaningful even at low traffic volumes. Category distribution can be inferred from the Traces tab's filterable list.

**Estimated effort to add:** A few hours. The trace data already includes category in `triage_output_json`. Implementation is a time-bucketed aggregation query and a Gradio bar chart.

---

## Log-based alerting

**What it would add:** Structured log warnings (`WARN [monitoring] threshold_breached: p95_latency=6200ms > limit=5000ms`) emitted when configured thresholds are crossed (p95 latency > 5s, retry rate > 20%, single category > 70% of recent traffic). See [ADR 0009](../../adr/0009-monitoring-distinct-from-benchmarking.md) for the threshold values and log format.

**Why it's deferred:** Log-based alerts are invisible to the audience during a demo unless specifically surfaced in the UI. The monitoring value is real but the demo impact is low compared to the visible dashboard components.

**What was done instead:** The Live Metrics section shows the same threshold-relevant numbers (p95 latency, retry rate) as KPI cards, making threshold violations visually apparent without log parsing.

**Estimated effort to add:** A few hours. The metrics service already computes the relevant values; adding threshold checks and structured log output is straightforward.
```

- [ ] **Step 2: Commit**

```bash
git add docs/future-improvements.md
git commit -m "docs: defer drift indicator and log-based alerting to future improvements"
```

---

### Task 9: Full verification + lint

**Files:** All modified files

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 2: Run lint and format check**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: Clean

- [ ] **Step 3: Run coverage check**

Run: `uv run pytest --cov=ticket_triage_llm --cov-fail-under=80`
Expected: ≥80% coverage. The new UI modules (`metrics_tab.py`, `traces_tab.py`, `experiments_tab.py`) should be added to the coverage `omit` list in `pyproject.toml` if they're judgment-based (same pattern as existing `triage_tab.py` omit).

If needed, update `pyproject.toml`:

```toml
[tool.coverage.report]
omit = [
    "src/ticket_triage_llm/app.py",
    "src/ticket_triage_llm/ui/*",
    "src/ticket_triage_llm/logging_config.py",
    "src/ticket_triage_llm/eval/runners/run_*.py",
]
```

- [ ] **Step 4: Fix any ruff violations**

Run: `uv run ruff check --fix . && uv run ruff format .`

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "chore: fix lint and coverage for Phase 5"
```

---

### Task 10: User testing — run the app and verify in browser

**Files:** None (manual verification)

- [ ] **Step 1: Start Ollama (if not running)**

Run: `ollama list` to verify models are available.

- [ ] **Step 2: Start the app**

Run: `OLLAMA_MODEL=qwen3.5:4b OLLAMA_MODELS=qwen3.5:2b,qwen3.5:4b,qwen3.5:9b uv run python -m ticket_triage_llm.app`

Open `http://localhost:7860` in browser.

- [ ] **Step 3: Verify Triage tab**

- Tab is visible and labeled "Triage"
- All existing functionality works (model dropdown, submit, cancel, new ticket)

- [ ] **Step 4: Verify Metrics tab**

- Tab is visible and labeled "Metrics"
- Benchmark Results section shows run selector with eval runs from Phase 3/4
- Selecting a run populates KPI cards and comparison table
- Live Metrics section shows "No live traffic" message or live stats
- Window selector radio buttons work

- [ ] **Step 5: Verify Traces tab**

- Tab is visible and labeled "Traces"
- Trace list populates with recent traces
- Filters work (provider, validation, status, limit)
- Clicking a row shows trace detail

- [ ] **Step 6: Verify Experiments tab**

- Tab is visible and labeled "Experiments"
- Experiment dropdown shows available experiments (E1, E3, etc.)
- Selecting an experiment shows description and comparison table
- Adversarial experiment shows different column headers

- [ ] **Step 7: Submit a live ticket and verify it appears**

- Submit a ticket in the Triage tab
- Switch to Traces tab, click Refresh — new trace appears
- Switch to Metrics tab, check Live Metrics section — stats update

---

Plan complete and saved to `docs/superpowers/plans/2026-04-18-phase-5-dashboard.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?