# Phase 1: Single Happy-Path Slice — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the first end-to-end triage slice — one model, one prompt, one Gradio tab, one API endpoint, trace storage, and a Dockerfile. Demo-able both natively and via Docker.

**Architecture:** Flat procedural pipeline in `run_triage()`. Each step (prompt, provider, parse, validate) is a standalone function. All dependencies passed as parameters. Every exit path saves a trace. No retry, no real guardrail, no provider switching.

**Tech Stack:** Python 3.11+, FastAPI, Gradio 5, OpenAI client (against Ollama), pydantic 2, SQLite, pytest, ruff, Docker, uv

**Branch:** `feature/phase-1-happy-path` (off `develop`)

**Spec:** `docs/superpowers/specs/2026-04-17-phase-1-happy-path-design.md`

---

## File map

### New files

| File | Responsibility |
|---|---|
| `src/ticket_triage_llm/providers/errors.py` | `ProviderError` exception class |
| `src/ticket_triage_llm/services/prompt.py` | Prompt version dispatch |
| `src/ticket_triage_llm/services/validation.py` | JSON parse + pydantic schema validation |
| `src/ticket_triage_llm/services/triage.py` | Pipeline orchestrator (`run_triage()`) |
| `src/ticket_triage_llm/services/trace.py` | `SqliteTraceRepository` concrete implementation |
| `src/ticket_triage_llm/app.py` | FastAPI + Gradio entry point (overwrite stub) |
| `src/ticket_triage_llm/api/triage_route.py` | `POST /api/v1/triage` (overwrite stub) |
| `src/ticket_triage_llm/ui/triage_tab.py` | Triage tab Gradio components (overwrite stub) |
| `Dockerfile` | Multi-stage Docker build |
| `tests/unit/test_prompt_service.py` | Prompt dispatch tests |
| `tests/unit/test_validation.py` | JSON parse + schema validation tests |
| `tests/unit/test_triage_service.py` | Pipeline orchestration tests |
| `tests/unit/test_sqlite_trace_repo.py` | Concrete SQLite repository tests |
| `tests/integration/test_api_route.py` | FastAPI TestClient smoke test |

### Modified files

| File | Change |
|---|---|
| `src/ticket_triage_llm/providers/ollama_qwen.py` | Replace stub with real implementation |
| `src/ticket_triage_llm/providers/__init__.py` | Add `ProviderError` export |
| `tests/unit/test_providers.py` | Update stub test (constructor now takes `base_url`) |

---

## Task 1: ProviderError exception

**Files:**
- Create: `src/ticket_triage_llm/providers/errors.py`
- Modify: `src/ticket_triage_llm/providers/__init__.py`

- [ ] **Step 1: Create the ProviderError exception**

```python
# src/ticket_triage_llm/providers/errors.py


class ProviderError(Exception):
    """Raised when a provider cannot complete a request.

    Covers connection failures, timeouts, and unexpected API errors.
    The triage service maps this to TriageFailure(category='model_unreachable').
    """
```

- [ ] **Step 2: Export from providers package**

In `src/ticket_triage_llm/providers/__init__.py`, add the import and export:

```python
from .base import LlmProvider
from .cloud_qwen import CloudQwenProvider
from .errors import ProviderError
from .ollama_qwen import OllamaQwenProvider

__all__ = ["CloudQwenProvider", "LlmProvider", "OllamaQwenProvider", "ProviderError"]
```

- [ ] **Step 3: Verify import works**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run python -c "from ticket_triage_llm.providers import ProviderError; print(ProviderError)"`

Expected: `<class 'ticket_triage_llm.providers.errors.ProviderError'>`

- [ ] **Step 4: Commit**

```bash
git add src/ticket_triage_llm/providers/errors.py src/ticket_triage_llm/providers/__init__.py
git commit -m "feat(providers): add ProviderError exception for connection failures"
```

---

## Task 2: OllamaQwenProvider concrete implementation (TDD)

**Files:**
- Modify: `src/ticket_triage_llm/providers/ollama_qwen.py`
- Modify: `tests/unit/test_providers.py`

This task uses TDD. The provider calls the OpenAI client against Ollama's endpoint. Tests mock the OpenAI client — no live Ollama needed.

- [ ] **Step 1: Write failing tests for the concrete provider**

Add to `tests/unit/test_providers.py`:

```python
from unittest.mock import MagicMock, patch
from openai import APIConnectionError

from ticket_triage_llm.providers.errors import ProviderError


class TestOllamaQwenProviderConcrete:
    def test_constructor_accepts_model_and_base_url(self):
        provider = OllamaQwenProvider(
            model="qwen3.5:4b", base_url="http://localhost:11434/v1"
        )
        assert provider.name == "ollama:qwen3.5:4b"

    @patch("ticket_triage_llm.providers.ollama_qwen.OpenAI")
    def test_generate_returns_model_result(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = '{"category": "billing"}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 150
        mock_client.chat.completions.create.return_value = mock_response

        provider = OllamaQwenProvider(
            model="qwen3.5:4b", base_url="http://localhost:11434/v1"
        )
        result = provider.generate_structured_ticket("test ticket", "v1")

        assert isinstance(result, ModelResult)
        assert result.raw_output == '{"category": "billing"}'
        assert result.model == "qwen3.5:4b"
        assert result.tokens_input == 100
        assert result.tokens_output == 50
        assert result.tokens_total == 150
        assert result.latency_ms > 0

    @patch("ticket_triage_llm.providers.ollama_qwen.OpenAI")
    def test_generate_passes_sampling_params(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = '{"category": "billing"}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_client.chat.completions.create.return_value = mock_response

        provider = OllamaQwenProvider(
            model="qwen3.5:4b", base_url="http://localhost:11434/v1"
        )
        provider.generate_structured_ticket("test ticket", "v1")

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["temperature"] == 0.2
        assert call_kwargs.kwargs["max_tokens"] == 2048
        extra = call_kwargs.kwargs["extra_body"]
        assert extra["top_p"] == 0.9
        assert extra["top_k"] == 40
        assert extra["repetition_penalty"] == 1.0

    @patch("ticket_triage_llm.providers.ollama_qwen.OpenAI")
    def test_generate_raises_provider_error_on_connection_failure(
        self, mock_openai_cls
    ):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = APIConnectionError(
            request=MagicMock()
        )

        provider = OllamaQwenProvider(
            model="qwen3.5:4b", base_url="http://localhost:11434/v1"
        )
        with pytest.raises(ProviderError):
            provider.generate_structured_ticket("test ticket", "v1")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run pytest tests/unit/test_providers.py::TestOllamaQwenProviderConcrete -v`

Expected: FAIL — constructor doesn't accept `base_url` yet, `generate_structured_ticket` raises `NotImplementedError`.

- [ ] **Step 3: Update the existing stub test**

The existing `TestOllamaQwenProviderStub` tests check the stub behavior (raises `NotImplementedError`). Update the constructor calls to include `base_url` and remove the `test_generate_raises_not_implemented` test (it's no longer a stub):

Replace `TestOllamaQwenProviderStub` in `tests/unit/test_providers.py`:

```python
class TestOllamaQwenProviderName:
    def test_has_name(self):
        provider = OllamaQwenProvider(
            model="qwen3.5:4b", base_url="http://localhost:11434/v1"
        )
        assert provider.name == "ollama:qwen3.5:4b"

    def test_model_parameterization(self):
        p2b = OllamaQwenProvider(
            model="qwen3.5:2b", base_url="http://localhost:11434/v1"
        )
        p9b = OllamaQwenProvider(
            model="qwen3.5:9b", base_url="http://localhost:11434/v1"
        )
        assert p2b.name == "ollama:qwen3.5:2b"
        assert p9b.name == "ollama:qwen3.5:9b"
```

- [ ] **Step 4: Implement the concrete provider**

Replace the contents of `src/ticket_triage_llm/providers/ollama_qwen.py`:

```python
import time

from openai import APIConnectionError, APITimeoutError, OpenAI

from ticket_triage_llm.config import (
    REPETITION_PENALTY,
    TEMPERATURE,
    TOP_K,
    TOP_P,
)
from ticket_triage_llm.providers.errors import ProviderError
from ticket_triage_llm.schemas.model_result import ModelResult
from ticket_triage_llm.services.prompt import get_prompt

MAX_TOKENS = 2048


class OllamaQwenProvider:
    def __init__(self, model: str, base_url: str) -> None:
        self._model = model
        self._client = OpenAI(base_url=base_url, api_key="ollama")

    @property
    def name(self) -> str:
        return f"ollama:{self._model}"

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str
    ) -> ModelResult:
        system_prompt, user_prompt = get_prompt(
            prompt_version, "", ticket_body
        )

        start = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                extra_body={
                    "top_p": TOP_P,
                    "top_k": TOP_K,
                    "repetition_penalty": REPETITION_PENALTY,
                },
            )
        except (APIConnectionError, APITimeoutError) as exc:
            raise ProviderError(str(exc)) from exc
        elapsed_ms = (time.perf_counter() - start) * 1000

        raw_output = response.choices[0].message.content or ""
        usage = response.usage

        return ModelResult(
            raw_output=raw_output,
            model=self._model,
            latency_ms=elapsed_ms,
            tokens_input=usage.prompt_tokens if usage else 0,
            tokens_output=usage.completion_tokens if usage else 0,
            tokens_total=usage.total_tokens if usage else 0,
            tokens_per_second=(
                (usage.completion_tokens / (elapsed_ms / 1000))
                if usage and elapsed_ms > 0
                else None
            ),
        )
```

- [ ] **Step 5: Run all provider tests to verify they pass**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run pytest tests/unit/test_providers.py -v`

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ticket_triage_llm/providers/ollama_qwen.py tests/unit/test_providers.py
git commit -m "feat(providers): implement OllamaQwenProvider with OpenAI client against Ollama"
```

---

## Task 3: Prompt service (TDD)

**Files:**
- Create: `tests/unit/test_prompt_service.py`
- Modify: `src/ticket_triage_llm/services/prompt.py` (overwrite stub)

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_prompt_service.py`:

```python
import pytest

from ticket_triage_llm.services.prompt import get_prompt


class TestGetPrompt:
    def test_v1_returns_tuple_of_two_strings(self):
        system, user = get_prompt("v1", "Test Subject", "My printer is broken")
        assert isinstance(system, str)
        assert isinstance(user, str)

    def test_v1_system_prompt_contains_json_schema(self):
        system, _ = get_prompt("v1", "", "test")
        assert '"category"' in system
        assert '"severity"' in system
        assert '"routingTeam"' in system

    def test_v1_user_prompt_contains_ticket_body(self):
        _, user = get_prompt("v1", "Subject", "My printer broke yesterday")
        assert "My printer broke yesterday" in user

    def test_v1_user_prompt_contains_subject(self):
        _, user = get_prompt("v1", "Printer Issue", "body text")
        assert "Printer Issue" in user

    def test_v1_user_prompt_has_ticket_delimiters(self):
        _, user = get_prompt("v1", "Subject", "body text")
        assert "<ticket>" in user
        assert "</ticket>" in user

    def test_unknown_version_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown prompt version"):
            get_prompt("v99", "Subject", "body")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run pytest tests/unit/test_prompt_service.py -v`

Expected: FAIL — `get_prompt` not defined.

- [ ] **Step 3: Implement the prompt service**

Replace the contents of `src/ticket_triage_llm/services/prompt.py`:

```python
from ticket_triage_llm.prompts.triage_v1 import (
    SYSTEM_PROMPT as V1_SYSTEM_PROMPT,
)
from ticket_triage_llm.prompts.triage_v1 import (
    build_user_prompt as v1_build_user_prompt,
)


def get_prompt(
    version: str, ticket_subject: str, ticket_body: str
) -> tuple[str, str]:
    if version == "v1":
        return (
            V1_SYSTEM_PROMPT,
            v1_build_user_prompt(ticket_subject, ticket_body),
        )
    raise ValueError(f"Unknown prompt version: {version!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run pytest tests/unit/test_prompt_service.py -v`

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_prompt_service.py src/ticket_triage_llm/services/prompt.py
git commit -m "feat(services): add prompt dispatch service with v1 routing"
```

---

## Task 4: Validation service (TDD)

**Files:**
- Create: `tests/unit/test_validation.py`
- Modify: `src/ticket_triage_llm/services/validation.py` (overwrite stub)

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_validation.py`:

```python
from ticket_triage_llm.schemas.triage_output import TriageOutput
from ticket_triage_llm.services.validation import parse_json, validate_schema

VALID_TRIAGE_JSON = (
    '{"category": "billing", "severity": "medium",'
    ' "routingTeam": "billing", "summary": "Billing issue",'
    ' "businessImpact": "Cannot process payments",'
    ' "draftReply": "We are looking into it.",'
    ' "confidence": 0.85, "escalation": false}'
)


class TestParseJson:
    def test_valid_json_returns_dict(self):
        result = parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_invalid_json_returns_none(self):
        result = parse_json("not json at all")
        assert result is None

    def test_empty_string_returns_none(self):
        result = parse_json("")
        assert result is None

    def test_strips_markdown_json_fence(self):
        raw = '```json\n{"key": "value"}\n```'
        result = parse_json(raw)
        assert result == {"key": "value"}

    def test_strips_markdown_fence_without_language(self):
        raw = '```\n{"key": "value"}\n```'
        result = parse_json(raw)
        assert result == {"key": "value"}

    def test_strips_leading_whitespace_before_fence(self):
        raw = '  \n```json\n{"key": "value"}\n```\n  '
        result = parse_json(raw)
        assert result == {"key": "value"}

    def test_valid_json_without_fences(self):
        result = parse_json(VALID_TRIAGE_JSON)
        assert result is not None
        assert result["category"] == "billing"


class TestValidateSchema:
    def test_valid_data_returns_triage_output(self):
        data = {
            "category": "billing",
            "severity": "medium",
            "routingTeam": "billing",
            "summary": "Billing issue",
            "businessImpact": "Cannot process payments",
            "draftReply": "We are looking into it.",
            "confidence": 0.85,
            "escalation": False,
        }
        result = validate_schema(data)
        assert isinstance(result, TriageOutput)
        assert result.category == "billing"

    def test_missing_field_returns_none(self):
        data = {"category": "billing"}
        result = validate_schema(data)
        assert result is None

    def test_invalid_category_returns_none(self):
        data = {
            "category": "unknown_category",
            "severity": "medium",
            "routingTeam": "billing",
            "summary": "Test",
            "businessImpact": "Test",
            "draftReply": "Test",
            "confidence": 0.5,
            "escalation": False,
        }
        result = validate_schema(data)
        assert result is None

    def test_confidence_out_of_range_returns_none(self):
        data = {
            "category": "billing",
            "severity": "medium",
            "routingTeam": "billing",
            "summary": "Test",
            "businessImpact": "Test",
            "draftReply": "Test",
            "confidence": 1.5,
            "escalation": False,
        }
        result = validate_schema(data)
        assert result is None

    def test_accepts_alias_field_names(self):
        data = {
            "category": "bug",
            "severity": "high",
            "routingTeam": "infra",
            "summary": "Bug found",
            "businessImpact": "Service down",
            "draftReply": "Investigating.",
            "confidence": 0.9,
            "escalation": True,
        }
        result = validate_schema(data)
        assert result is not None
        assert result.routing_team == "infra"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run pytest tests/unit/test_validation.py -v`

Expected: FAIL — `parse_json` and `validate_schema` not defined.

- [ ] **Step 3: Implement the validation service**

Replace the contents of `src/ticket_triage_llm/services/validation.py`:

```python
import json
import re

from pydantic import ValidationError

from ticket_triage_llm.schemas.triage_output import TriageOutput

_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\n(.*?)\n\s*```\s*$", re.DOTALL
)


def parse_json(raw_output: str) -> dict | None:
    text = raw_output.strip()
    if not text:
        return None

    fence_match = _FENCE_RE.match(text)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(data, dict):
        return None
    return data


def validate_schema(data: dict) -> TriageOutput | None:
    try:
        return TriageOutput.model_validate(data)
    except ValidationError:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run pytest tests/unit/test_validation.py -v`

Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_validation.py src/ticket_triage_llm/services/validation.py
git commit -m "feat(services): add JSON parse and schema validation service"
```

---

## Task 5: SqliteTraceRepository (TDD)

**Files:**
- Create: `tests/unit/test_sqlite_trace_repo.py`
- Modify: `src/ticket_triage_llm/services/trace.py` (overwrite stub)

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_sqlite_trace_repo.py`:

```python
import json
from datetime import UTC, datetime

import pytest

from ticket_triage_llm.schemas.trace import TraceRecord
from ticket_triage_llm.storage.db import get_connection, init_schema
from ticket_triage_llm.services.trace import SqliteTraceRepository


def _make_trace(**overrides) -> TraceRecord:
    defaults = {
        "request_id": "req-001",
        "timestamp": datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC),
        "model": "qwen3.5:4b",
        "provider": "ollama:qwen3.5:4b",
        "prompt_version": "v1",
        "ticket_body": "My printer is broken",
        "guardrail_result": "pass",
        "guardrail_matched_rules": [],
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


@pytest.fixture()
def repo(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path)
    init_schema(conn)
    return SqliteTraceRepository(conn)


class TestSaveTrace:
    def test_save_and_count(self, repo):
        trace = _make_trace()
        repo.save_trace(trace)
        rows = repo._conn.execute(
            "SELECT count(*) FROM traces"
        ).fetchone()
        assert rows[0] == 1

    def test_save_stores_correct_fields(self, repo):
        trace = _make_trace(
            request_id="req-fields",
            model="qwen3.5:9b",
            latency_ms=2000.0,
        )
        repo.save_trace(trace)
        row = repo._conn.execute(
            "SELECT model, latency_ms FROM traces WHERE request_id = ?",
            ("req-fields",),
        ).fetchone()
        assert row[0] == "qwen3.5:9b"
        assert row[1] == 2000.0

    def test_save_serializes_matched_rules_as_json(self, repo):
        trace = _make_trace(
            request_id="req-rules",
            guardrail_matched_rules=["rule_a", "rule_b"],
        )
        repo.save_trace(trace)
        row = repo._conn.execute(
            "SELECT guardrail_matched_rules FROM traces WHERE request_id = ?",
            ("req-rules",),
        ).fetchone()
        assert json.loads(row[0]) == ["rule_a", "rule_b"]

    def test_save_failure_trace(self, repo):
        trace = _make_trace(
            request_id="req-fail",
            status="failure",
            failure_category="parse_failure",
            validation_status="invalid",
        )
        repo.save_trace(trace)
        row = repo._conn.execute(
            "SELECT status, failure_category FROM traces WHERE request_id = ?",
            ("req-fail",),
        ).fetchone()
        assert row[0] == "failure"
        assert row[1] == "parse_failure"


class TestGetRecentTraces:
    def test_returns_traces_newest_first(self, repo):
        repo.save_trace(_make_trace(
            request_id="old",
            timestamp=datetime(2026, 4, 17, 10, 0, 0, tzinfo=UTC),
        ))
        repo.save_trace(_make_trace(
            request_id="new",
            timestamp=datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC),
        ))
        traces = repo.get_recent_traces(10)
        assert len(traces) == 2
        assert traces[0].request_id == "new"
        assert traces[1].request_id == "old"

    def test_respects_limit(self, repo):
        for i in range(5):
            repo.save_trace(_make_trace(
                request_id=f"req-{i}",
                timestamp=datetime(2026, 4, 17, i, 0, 0, tzinfo=UTC),
            ))
        traces = repo.get_recent_traces(2)
        assert len(traces) == 2

    def test_returns_empty_list_when_no_traces(self, repo):
        traces = repo.get_recent_traces(10)
        assert traces == []

    def test_round_trip_preserves_data(self, repo):
        original = _make_trace(
            request_id="rt-1",
            tokens_per_second=33.5,
            triage_output_json='{"category": "billing"}',
        )
        repo.save_trace(original)
        retrieved = repo.get_recent_traces(1)[0]
        assert retrieved.request_id == "rt-1"
        assert retrieved.model == "qwen3.5:4b"
        assert retrieved.tokens_per_second == 33.5
        assert retrieved.triage_output_json == '{"category": "billing"}'


class TestUnimplementedMethods:
    def test_get_traces_by_run_raises(self, repo):
        with pytest.raises(NotImplementedError):
            repo.get_traces_by_run("run-1")

    def test_get_traces_by_provider_raises(self, repo):
        with pytest.raises(NotImplementedError):
            repo.get_traces_by_provider("ollama")

    def test_get_traces_since_raises(self, repo):
        with pytest.raises(NotImplementedError):
            repo.get_traces_since(datetime.now(UTC))

    def test_get_all_traces_raises(self, repo):
        with pytest.raises(NotImplementedError):
            repo.get_all_traces()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run pytest tests/unit/test_sqlite_trace_repo.py -v`

Expected: FAIL — `SqliteTraceRepository` not defined.

- [ ] **Step 3: Implement SqliteTraceRepository**

Replace the contents of `src/ticket_triage_llm/services/trace.py`:

```python
import json
import sqlite3
from datetime import UTC, datetime

from ticket_triage_llm.schemas.trace import TraceRecord


class SqliteTraceRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_trace(self, trace: TraceRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO traces (
                request_id, run_id, timestamp, model, provider,
                prompt_version, ticket_body, guardrail_result,
                guardrail_matched_rules, validation_status, retry_count,
                latency_ms, tokens_input, tokens_output, tokens_total,
                tokens_per_second, estimated_cost, status,
                failure_category, raw_model_output, triage_output_json
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                trace.request_id,
                trace.run_id,
                trace.timestamp.isoformat(),
                trace.model,
                trace.provider,
                trace.prompt_version,
                trace.ticket_body,
                trace.guardrail_result,
                json.dumps(trace.guardrail_matched_rules),
                trace.validation_status,
                trace.retry_count,
                trace.latency_ms,
                trace.tokens_input,
                trace.tokens_output,
                trace.tokens_total,
                trace.tokens_per_second,
                trace.estimated_cost,
                trace.status,
                trace.failure_category,
                trace.raw_model_output,
                trace.triage_output_json,
            ),
        )
        self._conn.commit()

    def get_recent_traces(self, limit: int) -> list[TraceRecord]:
        cursor = self._conn.execute(
            "SELECT * FROM traces ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [self._row_to_trace(columns, row) for row in rows]

    def get_traces_by_run(self, run_id: str) -> list[TraceRecord]:
        raise NotImplementedError("get_traces_by_run: Phase 3")

    def get_traces_by_provider(self, provider: str) -> list[TraceRecord]:
        raise NotImplementedError("get_traces_by_provider: Phase 5")

    def get_traces_since(self, since: datetime) -> list[TraceRecord]:
        raise NotImplementedError("get_traces_since: Phase 5")

    def get_all_traces(self) -> list[TraceRecord]:
        raise NotImplementedError("get_all_traces: Phase 3")

    @staticmethod
    def _row_to_trace(columns: list[str], row: tuple) -> TraceRecord:
        data = dict(zip(columns, row))
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["guardrail_matched_rules"] = json.loads(
            data["guardrail_matched_rules"]
        )
        return TraceRecord.model_validate(data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run pytest tests/unit/test_sqlite_trace_repo.py -v`

Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_sqlite_trace_repo.py src/ticket_triage_llm/services/trace.py
git commit -m "feat(storage): implement SqliteTraceRepository with save and recent query"
```

---

## Task 6: Triage service — pipeline orchestrator (TDD)

**Files:**
- Create: `tests/unit/test_triage_service.py`
- Modify: `src/ticket_triage_llm/services/triage.py` (overwrite stub)

This is the core pipeline. Tests use a `FakeProvider` (from test_providers.py pattern) and `FakeTraceRepository` (from test_storage.py pattern) — no mocking library needed for the orchestrator itself.

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_triage_service.py`:

```python
from datetime import UTC, datetime

import pytest

from ticket_triage_llm.providers.errors import ProviderError
from ticket_triage_llm.schemas.model_result import ModelResult
from ticket_triage_llm.schemas.trace import (
    TraceRecord,
    TriageFailure,
    TriageSuccess,
)
from ticket_triage_llm.services.triage import run_triage

VALID_JSON_OUTPUT = (
    '{"category": "billing", "severity": "medium",'
    ' "routingTeam": "billing", "summary": "Billing issue",'
    ' "businessImpact": "Cannot process payments",'
    ' "draftReply": "We are looking into it.",'
    ' "confidence": 0.85, "escalation": false}'
)


class FakeProvider:
    name: str = "fake:test"

    def __init__(self, raw_output: str = VALID_JSON_OUTPUT):
        self._raw_output = raw_output

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str
    ) -> ModelResult:
        return ModelResult(
            raw_output=self._raw_output,
            model="fake-model",
            latency_ms=100.0,
            tokens_input=50,
            tokens_output=25,
            tokens_total=75,
        )


class ErrorProvider:
    name: str = "error:test"

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str
    ) -> ModelResult:
        raise ProviderError("Connection refused")


class FakeTraceRepo:
    def __init__(self):
        self.traces: list[TraceRecord] = []

    def save_trace(self, trace: TraceRecord) -> None:
        self.traces.append(trace)

    def get_recent_traces(self, limit: int) -> list[TraceRecord]:
        return self.traces[:limit]

    def get_traces_by_run(self, run_id: str) -> list[TraceRecord]:
        raise NotImplementedError

    def get_traces_by_provider(self, provider: str) -> list[TraceRecord]:
        raise NotImplementedError

    def get_traces_since(self, since: datetime) -> list[TraceRecord]:
        raise NotImplementedError

    def get_all_traces(self) -> list[TraceRecord]:
        raise NotImplementedError


class TestRunTriageHappyPath:
    def test_returns_triage_success(self):
        repo = FakeTraceRepo()
        result = run_triage(
            ticket_body="I have a billing question",
            ticket_subject="Billing",
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert isinstance(result, TriageSuccess)
        assert result.output.category == "billing"
        assert result.retry_count == 0

    def test_saves_trace_on_success(self):
        repo = FakeTraceRepo()
        run_triage(
            ticket_body="I have a billing question",
            ticket_subject="Billing",
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert len(repo.traces) == 1
        trace = repo.traces[0]
        assert trace.status == "success"
        assert trace.failure_category is None
        assert trace.validation_status == "valid"

    def test_trace_has_request_id(self):
        repo = FakeTraceRepo()
        run_triage(
            ticket_body="test",
            ticket_subject="",
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert repo.traces[0].request_id is not None
        assert len(repo.traces[0].request_id) > 0


class TestRunTriageParseFailure:
    def test_returns_triage_failure_on_bad_json(self):
        repo = FakeTraceRepo()
        result = run_triage(
            ticket_body="test",
            ticket_subject="",
            provider=FakeProvider(raw_output="not json"),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert isinstance(result, TriageFailure)
        assert result.category == "parse_failure"
        assert result.detected_by == "parser"
        assert result.raw_model_output == "not json"

    def test_saves_trace_on_parse_failure(self):
        repo = FakeTraceRepo()
        run_triage(
            ticket_body="test",
            ticket_subject="",
            provider=FakeProvider(raw_output="not json"),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert len(repo.traces) == 1
        assert repo.traces[0].status == "failure"
        assert repo.traces[0].failure_category == "parse_failure"


class TestRunTriageSchemaFailure:
    def test_returns_triage_failure_on_invalid_schema(self):
        repo = FakeTraceRepo()
        result = run_triage(
            ticket_body="test",
            ticket_subject="",
            provider=FakeProvider(raw_output='{"category": "billing"}'),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert isinstance(result, TriageFailure)
        assert result.category == "schema_failure"
        assert result.detected_by == "schema"

    def test_saves_trace_on_schema_failure(self):
        repo = FakeTraceRepo()
        run_triage(
            ticket_body="test",
            ticket_subject="",
            provider=FakeProvider(raw_output='{"category": "billing"}'),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert repo.traces[0].status == "failure"
        assert repo.traces[0].failure_category == "schema_failure"


class TestRunTriageProviderError:
    def test_returns_triage_failure_on_provider_error(self):
        repo = FakeTraceRepo()
        result = run_triage(
            ticket_body="test",
            ticket_subject="",
            provider=ErrorProvider(),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert isinstance(result, TriageFailure)
        assert result.category == "model_unreachable"
        assert result.detected_by == "provider"

    def test_saves_trace_on_provider_error(self):
        repo = FakeTraceRepo()
        run_triage(
            ticket_body="test",
            ticket_subject="",
            provider=ErrorProvider(),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert len(repo.traces) == 1
        assert repo.traces[0].status == "failure"
        assert repo.traces[0].failure_category == "model_unreachable"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run pytest tests/unit/test_triage_service.py -v`

Expected: FAIL — `run_triage` not defined.

- [ ] **Step 3: Implement the triage service**

Replace the contents of `src/ticket_triage_llm/services/triage.py`:

```python
import logging
import time
import uuid
from datetime import UTC, datetime

from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.providers.errors import ProviderError
from ticket_triage_llm.schemas.trace import (
    TraceRecord,
    TriageFailure,
    TriageResult,
    TriageSuccess,
)
from ticket_triage_llm.services.validation import parse_json, validate_schema
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)


def run_triage(
    ticket_body: str,
    ticket_subject: str,
    provider: LlmProvider,
    prompt_version: str,
    trace_repo: TraceRepository,
) -> TriageResult:
    request_id = str(uuid.uuid4())
    start = time.perf_counter()

    # Phase 1: guardrail is a pass-through stub. Phase 2 adds real guardrail.
    guardrail_result = "pass"
    guardrail_matched_rules: list[str] = []

    model_result = None
    raw_output: str | None = None
    result: TriageResult

    # The provider handles prompt construction internally via get_prompt().
    # The LlmProvider Protocol takes (ticket_body, prompt_version).
    try:
        model_result = provider.generate_structured_ticket(
            ticket_body, prompt_version
        )
        raw_output = model_result.raw_output
    except ProviderError as exc:
        logger.warning("Provider error: %s", exc)
        result = TriageFailure(
            category="model_unreachable",
            detected_by="provider",
            message=str(exc),
            retry_count=0,
        )
        _save_trace(
            trace_repo=trace_repo,
            request_id=request_id,
            start=start,
            provider=provider,
            prompt_version=prompt_version,
            ticket_body=ticket_body,
            guardrail_result=guardrail_result,
            guardrail_matched_rules=guardrail_matched_rules,
            model_result=model_result,
            raw_output=None,
            result=result,
        )
        return result

    parsed = parse_json(raw_output)
    if parsed is None:
        result = TriageFailure(
            category="parse_failure",
            detected_by="parser",
            message="Failed to parse model output as JSON",
            raw_model_output=raw_output,
            retry_count=0,
        )
        _save_trace(
            trace_repo=trace_repo,
            request_id=request_id,
            start=start,
            provider=provider,
            prompt_version=prompt_version,
            ticket_body=ticket_body,
            guardrail_result=guardrail_result,
            guardrail_matched_rules=guardrail_matched_rules,
            model_result=model_result,
            raw_output=raw_output,
            result=result,
        )
        return result

    triage_output = validate_schema(parsed)
    if triage_output is None:
        result = TriageFailure(
            category="schema_failure",
            detected_by="schema",
            message="Model output does not conform to TriageOutput schema",
            raw_model_output=raw_output,
            retry_count=0,
        )
        _save_trace(
            trace_repo=trace_repo,
            request_id=request_id,
            start=start,
            provider=provider,
            prompt_version=prompt_version,
            ticket_body=ticket_body,
            guardrail_result=guardrail_result,
            guardrail_matched_rules=guardrail_matched_rules,
            model_result=model_result,
            raw_output=raw_output,
            result=result,
        )
        return result

    result = TriageSuccess(
        output=triage_output,
        retry_count=0,
    )

    _save_trace(
        trace_repo=trace_repo,
        request_id=request_id,
        start=start,
        provider=provider,
        prompt_version=prompt_version,
        ticket_body=ticket_body,
        guardrail_result=guardrail_result,
        guardrail_matched_rules=guardrail_matched_rules,
        model_result=model_result,
        raw_output=raw_output,
        result=result,
    )
    return result


def _save_trace(
    *,
    trace_repo: TraceRepository,
    request_id: str,
    start: float,
    provider: LlmProvider,
    prompt_version: str,
    ticket_body: str,
    guardrail_result: str,
    guardrail_matched_rules: list[str],
    model_result: object | None,
    raw_output: str | None,
    result: TriageResult,
) -> None:
    elapsed_ms = (time.perf_counter() - start) * 1000

    is_success = isinstance(result, TriageSuccess)
    triage_output_json = (
        result.output.model_dump_json(by_alias=True) if is_success else None
    )

    mr = model_result
    trace = TraceRecord(
        request_id=request_id,
        timestamp=datetime.now(UTC),
        model=mr.model if mr else "unknown",
        provider=provider.name,
        prompt_version=prompt_version,
        ticket_body=ticket_body,
        guardrail_result=guardrail_result,
        guardrail_matched_rules=guardrail_matched_rules,
        validation_status="valid" if is_success else "invalid",
        retry_count=0,
        latency_ms=elapsed_ms,
        tokens_input=mr.tokens_input if mr else 0,
        tokens_output=mr.tokens_output if mr else 0,
        tokens_total=mr.tokens_total if mr else 0,
        tokens_per_second=mr.tokens_per_second if mr else None,
        status="success" if is_success else "failure",
        failure_category=(
            result.category if isinstance(result, TriageFailure) else None
        ),
        raw_model_output=raw_output,
        triage_output_json=triage_output_json,
    )
    trace_repo.save_trace(trace)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run pytest tests/unit/test_triage_service.py -v`

Expected: All 9 tests PASS.

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run pytest -v`

Expected: All tests PASS (existing Phase F tests + new Phase 1 tests).

- [ ] **Step 6: Commit**

```bash
git add tests/unit/test_triage_service.py src/ticket_triage_llm/services/triage.py
git commit -m "feat(services): implement run_triage pipeline orchestrator"
```

---

## Task 7: FastAPI app + API route (judgment-based)

**Files:**
- Modify: `src/ticket_triage_llm/app.py` (overwrite stub)
- Modify: `src/ticket_triage_llm/api/triage_route.py` (overwrite stub)
- Create: `tests/integration/test_api_route.py`

The app wiring and API route are judgment-based (not strict TDD per CLAUDE.md). We write the implementation first, then the smoke test.

- [ ] **Step 1: Implement the API route**

Replace the contents of `src/ticket_triage_llm/api/triage_route.py`:

```python
from fastapi import APIRouter, Depends

from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.schemas.triage_input import TriageInput
from ticket_triage_llm.schemas.trace import TriageResult
from ticket_triage_llm.services.triage import run_triage
from ticket_triage_llm.storage.trace_repo import TraceRepository

router = APIRouter(prefix="/api/v1", tags=["triage"])

_provider: LlmProvider | None = None
_trace_repo: TraceRepository | None = None


def configure(provider: LlmProvider, trace_repo: TraceRepository) -> None:
    global _provider, _trace_repo  # noqa: PLW0603
    _provider = provider
    _trace_repo = trace_repo


@router.post("/triage")
def triage_ticket(payload: TriageInput) -> TriageResult:
    assert _provider is not None, "Provider not configured"
    assert _trace_repo is not None, "TraceRepository not configured"

    return run_triage(
        ticket_body=payload.ticket_body,
        ticket_subject=payload.ticket_subject,
        provider=_provider,
        prompt_version=payload.prompt_version,
        trace_repo=_trace_repo,
    )
```

- [ ] **Step 2: Implement app.py entry point**

Replace the contents of `src/ticket_triage_llm/app.py`:

```python
import os

import gradio as gr
import uvicorn
from fastapi import FastAPI

from ticket_triage_llm.api.triage_route import configure as configure_api
from ticket_triage_llm.api.triage_route import router as api_router
from ticket_triage_llm.config import Settings
from ticket_triage_llm.logging_config import configure_logging
from ticket_triage_llm.providers.ollama_qwen import OllamaQwenProvider
from ticket_triage_llm.services.trace import SqliteTraceRepository
from ticket_triage_llm.storage.db import get_connection, init_schema
from ticket_triage_llm.ui.triage_tab import build_triage_tab

app = FastAPI(title="Ticket Triage LLM", version="0.1.0")
app.include_router(api_router)


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings.log_level)

    os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)
    conn = get_connection(settings.db_path)
    init_schema(conn)
    trace_repo = SqliteTraceRepository(conn)

    provider = OllamaQwenProvider(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
    )

    configure_api(provider, trace_repo)

    gradio_app = build_triage_tab(provider, trace_repo)
    app = FastAPI(title="Ticket Triage LLM", version="0.1.0")
    app.include_router(api_router)
    app = gr.mount_gradio_app(app, gradio_app, path="/")

    return app


if __name__ == "__main__":
    application = create_app()
    uvicorn.run(application, host="0.0.0.0", port=7860)
```

- [ ] **Step 3: Write the API smoke test**

Create `tests/integration/test_api_route.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ticket_triage_llm.api.triage_route import configure, router
from ticket_triage_llm.schemas.model_result import ModelResult
from ticket_triage_llm.schemas.trace import TraceRecord

VALID_JSON = (
    '{"category": "billing", "severity": "medium",'
    ' "routingTeam": "billing", "summary": "Billing issue",'
    ' "businessImpact": "Cannot process payments",'
    ' "draftReply": "We are looking into it.",'
    ' "confidence": 0.85, "escalation": false}'
)


class FakeProvider:
    name: str = "fake:test"

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str
    ) -> ModelResult:
        return ModelResult(
            raw_output=VALID_JSON,
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
        raise NotImplementedError

    def get_traces_by_provider(self, provider: str) -> list[TraceRecord]:
        raise NotImplementedError

    def get_traces_since(self, since) -> list[TraceRecord]:
        raise NotImplementedError

    def get_all_traces(self) -> list[TraceRecord]:
        raise NotImplementedError


def _build_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router)
    configure(FakeProvider(), FakeTraceRepo())
    return test_app


class TestTriageEndpoint:
    def test_happy_path_returns_200(self):
        client = TestClient(_build_test_app())
        response = client.post(
            "/api/v1/triage",
            json={
                "ticket_body": "I have a billing question",
                "ticket_subject": "Billing",
            },
        )
        assert response.status_code == 200

    def test_happy_path_returns_success_status(self):
        client = TestClient(_build_test_app())
        response = client.post(
            "/api/v1/triage",
            json={"ticket_body": "I have a billing question"},
        )
        data = response.json()
        assert data["status"] == "success"
        assert data["output"]["category"] == "billing"

    def test_empty_body_returns_422(self):
        client = TestClient(_build_test_app())
        response = client.post(
            "/api/v1/triage",
            json={"ticket_body": "   "},
        )
        assert response.status_code == 422
```

- [ ] **Step 4: Run the API tests**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run pytest tests/integration/test_api_route.py -v`

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ticket_triage_llm/app.py src/ticket_triage_llm/api/triage_route.py tests/integration/test_api_route.py
git commit -m "feat(api): add FastAPI app entry point and POST /api/v1/triage route"
```

---

## Task 8: Gradio Triage tab (judgment-based)

**Files:**
- Modify: `src/ticket_triage_llm/ui/triage_tab.py` (overwrite stub)

The Gradio tab is UI code — judgment-based testing (manual verification), not strict TDD.

- [ ] **Step 1: Implement the Triage tab**

Replace the contents of `src/ticket_triage_llm/ui/triage_tab.py`:

```python
import gradio as gr

from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.schemas.trace import TriageFailure, TriageSuccess
from ticket_triage_llm.services.triage import run_triage
from ticket_triage_llm.storage.trace_repo import TraceRepository


def build_triage_tab(
    provider: LlmProvider, trace_repo: TraceRepository
) -> gr.Blocks:
    def handle_triage(ticket_subject: str, ticket_body: str):
        if not ticket_body.strip():
            return "Error: ticket body is required", ""

        result = run_triage(
            ticket_body=ticket_body,
            ticket_subject=ticket_subject,
            provider=provider,
            prompt_version="v1",
            trace_repo=trace_repo,
        )

        if isinstance(result, TriageSuccess):
            output = result.output
            result_text = (
                f"**Category:** {output.category}\n"
                f"**Severity:** {output.severity}\n"
                f"**Routing Team:** {output.routing_team}\n"
                f"**Escalation:** {output.escalation}\n"
                f"**Confidence:** {output.confidence:.0%}\n\n"
                f"**Summary:** {output.summary}\n\n"
                f"**Business Impact:** {output.business_impact}\n\n"
                f"**Draft Reply:** {output.draft_reply}"
            )
            trace = trace_repo.get_recent_traces(1)[0]
            trace_text = (
                f"Request ID: {trace.request_id}\n"
                f"Model: {trace.model}\n"
                f"Latency: {trace.latency_ms:.0f} ms\n"
                f"Tokens: {trace.tokens_total} "
                f"(in={trace.tokens_input}, out={trace.tokens_output})\n"
                f"Validation: {trace.validation_status}\n"
                f"Retry Count: {trace.retry_count}"
            )
            return result_text, trace_text

        if isinstance(result, TriageFailure):
            result_text = (
                f"**Triage Failed**\n\n"
                f"**Failure:** {result.category}\n"
                f"**Detected By:** {result.detected_by}\n"
                f"**Message:** {result.message}"
            )
            if result.raw_model_output:
                result_text += (
                    f"\n\n**Raw Output:**\n```\n"
                    f"{result.raw_model_output[:500]}\n```"
                )
            trace = trace_repo.get_recent_traces(1)[0]
            trace_text = (
                f"Request ID: {trace.request_id}\n"
                f"Model: {trace.model}\n"
                f"Latency: {trace.latency_ms:.0f} ms\n"
                f"Status: {trace.status}\n"
                f"Failure: {trace.failure_category}"
            )
            return result_text, trace_text

        return "Unexpected result type", ""

    with gr.Blocks(title="Ticket Triage LLM") as demo:
        gr.Markdown("# Ticket Triage LLM")
        gr.Markdown(
            f"Using model: **{provider.name}** | Prompt: **v1**"
        )

        with gr.Row():
            with gr.Column(scale=1):
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
                submit_btn = gr.Button("Triage", variant="primary")

            with gr.Column(scale=1):
                result_output = gr.Markdown(label="Triage Result")
                trace_output = gr.Textbox(
                    label="Trace Summary",
                    lines=6,
                    interactive=False,
                )

        submit_btn.click(
            fn=handle_triage,
            inputs=[subject_input, body_input],
            outputs=[result_output, trace_output],
        )

    return demo
```

- [ ] **Step 2: Verify the module imports cleanly**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run python -c "from ticket_triage_llm.ui.triage_tab import build_triage_tab; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/ticket_triage_llm/ui/triage_tab.py
git commit -m "feat(ui): implement Triage tab with ticket input and result display"
```

---

## Task 9: Dockerfile

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Create the Dockerfile**

Create `Dockerfile` at the repo root:

```dockerfile
# --- Builder stage ---
FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

COPY src/ src/

# --- Runtime stage ---
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH"
ENV OLLAMA_BASE_URL="http://host.docker.internal:11434/v1"
ENV OLLAMA_MODEL="qwen3.5:4b"
ENV DB_PATH="/app/data/traces.db"

EXPOSE 7860

CMD ["python", "-m", "ticket_triage_llm.app"]
```

- [ ] **Step 2: Verify Docker build succeeds**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && docker build -t ticket-triage-llm .`

Expected: Build completes successfully.

- [ ] **Step 3: Commit**

```bash
git add Dockerfile
git commit -m "feat(deploy): add multi-stage Dockerfile for app container"
```

---

## Task 10: Full test suite + lint + commit design/plan docs

**Files:**
- No new files — verification and final cleanup

- [ ] **Step 1: Run the full test suite with coverage**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run pytest --cov=ticket_triage_llm --cov-fail-under=80 -v`

Expected: All tests PASS, coverage >= 80%.

- [ ] **Step 2: Run ruff lint and format check**

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run ruff check . && uv run ruff format --check .`

Expected: No errors.

- [ ] **Step 3: Fix any lint or format issues**

If ruff reports issues:

Run: `cd /Users/richardgoshen/workspaces/flexion/ticket-triage-llm && uv run ruff check --fix . && uv run ruff format .`

Then re-run the checks to confirm clean.

- [ ] **Step 4: Commit the design spec and implementation plan**

```bash
git add docs/superpowers/specs/2026-04-17-phase-1-happy-path-design.md docs/superpowers/plans/2026-04-17-phase-1-happy-path.md
git commit -m "docs: add Phase 1 design spec and implementation plan"
```

---

## Task 11: Update TODO.md and SUMMARY.md

**Files:**
- Modify: `TODO.md`
- Modify: `SUMMARY.md`

- [ ] **Step 1: Update TODO.md**

Mark Phase 1 checkboxes as complete. Add checkmarks to all items that have been implemented.

- [ ] **Step 2: Update SUMMARY.md**

Add a new entry at the top of `SUMMARY.md` (below the header) with the Phase 1 summary following the established format:

```markdown
## [2026-04-17] Phase 1 — Single happy-path slice

**What was done:**

- Implemented the first end-to-end triage pipeline: OllamaQwenProvider → prompt builder → JSON parse → schema validation → trace storage.
- FastAPI app with Gradio Triage tab mounted as sub-application, `POST /api/v1/triage` endpoint with Swagger docs.
- SqliteTraceRepository with save and recent-query support.
- Multi-stage Dockerfile for the app container (Ollama on host per ADR 0007).
- Full TDD test suite for services (prompt, validation, triage orchestrator, trace repo) plus integration test for API route.

**How it was done:**

- Strict RED/GREEN/REFACTOR TDD for all service and business logic (Tasks 2-6).
- Judgment-based approach for app wiring, Gradio UI, and Dockerfile (Tasks 7-9).
- Flat procedural pipeline in `run_triage()` — each step is a standalone function, all dependencies passed as parameters.
- Atomic commits per task, Conventional Commits format.
- Branch: `feature/phase-1-happy-path` off `develop`.

**Issues encountered:**

[Fill in actual issues encountered during implementation]

**How those issues were resolved:**

[Fill in actual resolutions]

**Exit state:**

- All tests pass, coverage >= 80%, ruff clean.
- System demo-able natively via `uv run python -m ticket_triage_llm.app` and via Docker.
- Phase 2 unblocked (provider router, retry, guardrail).
```

- [ ] **Step 3: Commit**

```bash
git add TODO.md SUMMARY.md
git commit -m "docs: update TODO.md and SUMMARY.md for Phase 1 completion"
```
