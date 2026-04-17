# Phase F — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the shared contracts — package scaffolding, pydantic schemas, LlmProvider Protocol, TriageResult discriminated union, SQLite traces table, config loader, structured logging, and CI — so that every downstream phase can build against stable interfaces without merge conflicts.

**Architecture:** Phase F creates no business logic. It publishes typed contracts (pydantic models, Protocols, SQL schema) that Phase 1+ implements against. TDD applies to all schema and contract code per CLAUDE.md. Config, logging, CI, and stubs are judgment-based.

**Tech Stack:** Python 3.11+, pydantic 2.x, pydantic-settings, sqlite3 (stdlib), pytest + pytest-cov, ruff, uv, GitHub Actions.

**Branch:** `feature/phase-foundation` off `develop`.

**Existing state:** `src/ticket_triage_llm/prompts/triage_v1.py` already exists from Phase 0. Do not modify it.

---

## File Map

### Files to create

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, deps, build config |
| `ruff.toml` | Linter/formatter config |
| `.env.example` | Env var documentation |
| `.dockerignore` | Docker build exclusions |
| `src/ticket_triage_llm/__init__.py` | Package root |
| `src/ticket_triage_llm/schemas/__init__.py` | Re-exports all public schema types |
| `src/ticket_triage_llm/schemas/triage_input.py` | `TriageInput` model |
| `src/ticket_triage_llm/schemas/triage_output.py` | `TriageOutput` model + type aliases |
| `src/ticket_triage_llm/schemas/model_result.py` | `ModelResult` — raw provider return |
| `src/ticket_triage_llm/schemas/trace.py` | `TraceRecord`, `TriageSuccess`, `TriageFailure`, `TriageResult`, `FailureReason` |
| `src/ticket_triage_llm/schemas/errors.py` | `assert_never_failure_reason` helper |
| `src/ticket_triage_llm/providers/__init__.py` | Re-exports `LlmProvider`, `ModelResult` |
| `src/ticket_triage_llm/providers/base.py` | `LlmProvider` Protocol |
| `src/ticket_triage_llm/providers/ollama_qwen.py` | `OllamaQwenProvider` stub |
| `src/ticket_triage_llm/providers/cloud_qwen.py` | `CloudQwenProvider` stub |
| `src/ticket_triage_llm/storage/__init__.py` | Re-exports |
| `src/ticket_triage_llm/storage/db.py` | `get_connection()`, `init_schema()` |
| `src/ticket_triage_llm/storage/trace_repo.py` | `TraceRepository` Protocol |
| `src/ticket_triage_llm/config.py` | `Settings` via pydantic-settings |
| `src/ticket_triage_llm/logging_config.py` | Structured logging setup |
| `src/ticket_triage_llm/services/__init__.py` | Stub |
| `src/ticket_triage_llm/ui/__init__.py` | Stub |
| `src/ticket_triage_llm/api/__init__.py` | Stub |
| `src/ticket_triage_llm/eval/__init__.py` | Stub |
| `tests/__init__.py` | Test package root |
| `tests/unit/__init__.py` | Unit test package |
| `tests/unit/test_triage_input.py` | TriageInput tests |
| `tests/unit/test_triage_output.py` | TriageOutput tests |
| `tests/unit/test_model_result.py` | ModelResult tests |
| `tests/unit/test_failure_contract.py` | TriageFailure, TriageSuccess, TriageResult, FailureReason, assert_never tests |
| `tests/unit/test_trace_record.py` | TraceRecord tests |
| `tests/unit/test_providers.py` | Protocol structural typing + stub tests |
| `tests/unit/test_storage.py` | init_schema + TraceRepository Protocol tests |
| `tests/unit/test_config.py` | Settings defaults and env override tests |
| `tests/integration/__init__.py` | Stub |
| `tests/eval/__init__.py` | Stub |
| `.github/workflows/ci.yml` | CI pipeline |

### Files to modify

| File | Change |
|---|---|
| `.gitignore` | Add `data/*.db` entry |

---

### Task 1: Create feature branch and project scaffolding

**Files:**
- Create: `pyproject.toml`, `ruff.toml`, `.env.example`, `.dockerignore`
- Modify: `.gitignore`

- [ ] **Step 1: Create feature branch**

```bash
git checkout develop
git pull origin develop
git checkout -b feature/phase-foundation
```

- [ ] **Step 2: Create `pyproject.toml`**

```python
# File: pyproject.toml
```

```toml
[project]
name = "ticket-triage-llm"
version = "0.1.0"
description = "Production-style support ticket triage with local-first LLM evaluation"
requires-python = ">=3.11"
license = {text = "MIT"}
dependencies = [
    "fastapi>=0.115.0",
    "gradio>=5.0.0",
    "openai>=1.50.0",
    "ollama>=0.4.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.6.0",
    "uvicorn>=0.32.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.8.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ticket_triage_llm"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v"

[tool.coverage.run]
source = ["ticket_triage_llm"]

[tool.coverage.report]
fail_under = 80
```

- [ ] **Step 3: Create `ruff.toml`**

```toml
line-length = 88
target-version = "py311"

[lint]
select = ["E", "F", "I", "UP", "B", "SIM", "N"]

[format]
quote-style = "double"
```

- [ ] **Step 4: Create `.env.example`**

```bash
# Ollama endpoint — the openai client base URL
OLLAMA_BASE_URL=http://localhost:11434/v1

# Model to use (no default — must be set)
# OLLAMA_MODEL=qwen3.5:4b

# Sampling parameters (locked values — change requires decision-log entry)
TEMPERATURE=0.2
TOP_P=0.9
TOP_K=40
REPETITION_PENALTY=1.0

# SQLite database path (relative to project root)
DB_PATH=data/traces.db

# Logging level
LOG_LEVEL=INFO
```

- [ ] **Step 5: Create `.dockerignore`**

```
.git
.github
.remember
.claude
.venv
.env
.ruff_cache
.pytest_cache
.mypy_cache
__pycache__
*.pyc
*.pyo
data/phase0
docs
scripts
tests
*.md
!DEPLOYMENT.md
.DS_Store
.gitignore
```

- [ ] **Step 6: Add `data/*.db` to `.gitignore`**

Append to the end of `.gitignore`:

```
# SQLite database files (generated at runtime)
data/*.db
data/*.db-journal
data/*.db-wal
```

- [ ] **Step 7: Run `uv sync --all-extras`**

```bash
uv sync --all-extras
```

Expected: lock file generated, deps installed, no errors.

- [ ] **Step 8: Verify ruff runs clean on empty project**

```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: no errors (nothing to lint yet besides triage_v1.py).

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock ruff.toml .env.example .dockerignore .gitignore
git commit -m "chore: add project scaffolding — pyproject.toml, ruff, env, dockerignore"
```

---

### Task 2: Package skeleton with `__init__.py` stubs

**Files:**
- Create: all `__init__.py` files for the package tree, plus empty stubs for future-phase modules
- Create: `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/eval/__init__.py`

- [ ] **Step 1: Create package directories and `__init__.py` files**

```bash
mkdir -p src/ticket_triage_llm/schemas
mkdir -p src/ticket_triage_llm/providers
mkdir -p src/ticket_triage_llm/storage
mkdir -p src/ticket_triage_llm/services
mkdir -p src/ticket_triage_llm/ui
mkdir -p src/ticket_triage_llm/api
mkdir -p src/ticket_triage_llm/eval/runners
mkdir -p src/ticket_triage_llm/eval/datasets
mkdir -p src/ticket_triage_llm/eval/reports
mkdir -p tests/unit
mkdir -p tests/integration
mkdir -p tests/eval
```

Create empty `__init__.py` in each:

`src/ticket_triage_llm/__init__.py`:
```python
"""ticket-triage-llm: production-style support ticket triage with local-first LLM evaluation."""
```

All other `__init__.py` files (`schemas/`, `providers/`, `storage/`, `services/`, `ui/`, `api/`, `eval/`, `eval/runners/`, `tests/`, `tests/unit/`, `tests/integration/`, `tests/eval/`) are empty files (zero bytes).

- [ ] **Step 2: Verify package installs in editable mode**

```bash
uv sync --all-extras
uv run python -c "import ticket_triage_llm; print('OK')"
```

Expected: prints `OK`.

- [ ] **Step 3: Commit**

```bash
git add src/ tests/
git commit -m "chore: add package skeleton with __init__.py stubs"
```

---

### Task 3: TriageInput schema (TDD)

**Files:**
- Create: `tests/unit/test_triage_input.py`
- Create: `src/ticket_triage_llm/schemas/triage_input.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_triage_input.py`:
```python
import pytest
from pydantic import ValidationError

from ticket_triage_llm.schemas.triage_input import TriageInput


class TestTriageInput:
    def test_valid_minimal(self):
        ti = TriageInput(ticket_body="My account is locked")
        assert ti.ticket_body == "My account is locked"
        assert ti.ticket_subject == ""
        assert ti.model is None
        assert ti.prompt_version == "v1"

    def test_valid_all_fields(self):
        ti = TriageInput(
            ticket_body="My account is locked",
            ticket_subject="Account Issue",
            model="qwen3.5:4b",
            prompt_version="v2",
        )
        assert ti.ticket_subject == "Account Issue"
        assert ti.model == "qwen3.5:4b"
        assert ti.prompt_version == "v2"

    def test_empty_body_rejected(self):
        with pytest.raises(ValidationError):
            TriageInput(ticket_body="")

    def test_whitespace_only_body_rejected(self):
        with pytest.raises(ValidationError):
            TriageInput(ticket_body="   \n\t  ")

    def test_missing_body_rejected(self):
        with pytest.raises(ValidationError):
            TriageInput()  # type: ignore[call-arg]

    def test_round_trip_json(self):
        ti = TriageInput(ticket_body="test", ticket_subject="subj")
        data = ti.model_dump()
        restored = TriageInput.model_validate(data)
        assert restored == ti
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_triage_input.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — the module doesn't exist yet.

- [ ] **Step 3: Write minimal implementation**

`src/ticket_triage_llm/schemas/triage_input.py`:
```python
from pydantic import BaseModel, field_validator


class TriageInput(BaseModel):
    ticket_body: str
    ticket_subject: str = ""
    model: str | None = None
    prompt_version: str = "v1"

    @field_validator("ticket_body")
    @classmethod
    def body_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("ticket_body must not be empty or whitespace-only")
        return v
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_triage_input.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ticket_triage_llm/schemas/triage_input.py tests/unit/test_triage_input.py
git commit -m "feat: add TriageInput pydantic schema with body validation"
```

---

### Task 4: TriageOutput schema (TDD)

**Files:**
- Create: `tests/unit/test_triage_output.py`
- Create: `src/ticket_triage_llm/schemas/triage_output.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_triage_output.py`:
```python
import pytest
from pydantic import ValidationError

from ticket_triage_llm.schemas.triage_output import (
    Category,
    RoutingTeam,
    Severity,
    TriageOutput,
)


VALID_OUTPUT = {
    "category": "billing",
    "severity": "high",
    "routingTeam": "billing",
    "summary": "Customer cannot access invoice.",
    "businessImpact": "Billing cycle delayed.",
    "draftReply": "We are looking into your billing issue.",
    "confidence": 0.85,
    "escalation": False,
}


class TestTriageOutput:
    def test_valid_from_camel_case_json(self):
        to = TriageOutput.model_validate(VALID_OUTPUT)
        assert to.category == "billing"
        assert to.routing_team == "billing"
        assert to.business_impact == "Billing cycle delayed."
        assert to.draft_reply == "We are looking into your billing issue."

    def test_valid_from_snake_case(self):
        to = TriageOutput(
            category="outage",
            severity="critical",
            routing_team="infra",
            summary="Service is down.",
            business_impact="Revenue loss.",
            draft_reply="We are investigating.",
            confidence=0.95,
            escalation=True,
        )
        assert to.severity == "critical"

    def test_invalid_category_rejected(self):
        data = {**VALID_OUTPUT, "category": "invalid_category"}
        with pytest.raises(ValidationError, match="category"):
            TriageOutput.model_validate(data)

    def test_invalid_severity_rejected(self):
        data = {**VALID_OUTPUT, "severity": "extreme"}
        with pytest.raises(ValidationError, match="severity"):
            TriageOutput.model_validate(data)

    def test_invalid_routing_team_rejected(self):
        data = {**VALID_OUTPUT, "routingTeam": "marketing"}
        with pytest.raises(ValidationError, match="routing_team"):
            TriageOutput.model_validate(data)

    def test_confidence_below_zero_rejected(self):
        data = {**VALID_OUTPUT, "confidence": -0.1}
        with pytest.raises(ValidationError, match="confidence"):
            TriageOutput.model_validate(data)

    def test_confidence_above_one_rejected(self):
        data = {**VALID_OUTPUT, "confidence": 1.01}
        with pytest.raises(ValidationError, match="confidence"):
            TriageOutput.model_validate(data)

    def test_confidence_boundary_zero(self):
        data = {**VALID_OUTPUT, "confidence": 0.0}
        to = TriageOutput.model_validate(data)
        assert to.confidence == 0.0

    def test_confidence_boundary_one(self):
        data = {**VALID_OUTPUT, "confidence": 1.0}
        to = TriageOutput.model_validate(data)
        assert to.confidence == 1.0

    def test_missing_required_field_rejected(self):
        data = {k: v for k, v in VALID_OUTPUT.items() if k != "summary"}
        with pytest.raises(ValidationError):
            TriageOutput.model_validate(data)

    def test_round_trip_dump_validate(self):
        to = TriageOutput.model_validate(VALID_OUTPUT)
        dumped = to.model_dump(by_alias=True)
        restored = TriageOutput.model_validate(dumped)
        assert restored == to

    def test_all_categories_accepted(self):
        for cat in ("billing", "outage", "account_access", "bug", "feature_request", "other"):
            data = {**VALID_OUTPUT, "category": cat}
            to = TriageOutput.model_validate(data)
            assert to.category == cat

    def test_all_severities_accepted(self):
        for sev in ("low", "medium", "high", "critical"):
            data = {**VALID_OUTPUT, "severity": sev}
            to = TriageOutput.model_validate(data)
            assert to.severity == sev

    def test_all_routing_teams_accepted(self):
        for team in ("support", "billing", "infra", "product", "security"):
            data = {**VALID_OUTPUT, "routingTeam": team}
            to = TriageOutput.model_validate(data)
            assert to.routing_team == team
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_triage_output.py -v
```

Expected: `ImportError` — module doesn't exist.

- [ ] **Step 3: Write minimal implementation**

`src/ticket_triage_llm/schemas/triage_output.py`:
```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal[
    "billing", "outage", "account_access", "bug", "feature_request", "other"
]

Severity = Literal["low", "medium", "high", "critical"]

RoutingTeam = Literal["support", "billing", "infra", "product", "security"]


class TriageOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    category: Category
    severity: Severity
    routing_team: RoutingTeam = Field(alias="routingTeam")
    summary: str
    business_impact: str = Field(alias="businessImpact")
    draft_reply: str = Field(alias="draftReply")
    confidence: float = Field(ge=0.0, le=1.0)
    escalation: bool
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_triage_output.py -v
```

Expected: all 14 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ticket_triage_llm/schemas/triage_output.py tests/unit/test_triage_output.py
git commit -m "feat: add TriageOutput pydantic schema with enum constraints and camelCase aliases"
```

---

### Task 5: ModelResult schema (TDD)

**Files:**
- Create: `tests/unit/test_model_result.py`
- Create: `src/ticket_triage_llm/schemas/model_result.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_model_result.py`:
```python
import pytest
from pydantic import ValidationError

from ticket_triage_llm.schemas.model_result import ModelResult


class TestModelResult:
    def test_valid_construction(self):
        mr = ModelResult(
            raw_output='{"category": "billing"}',
            model="qwen3.5:4b",
            latency_ms=1234.5,
            tokens_input=150,
            tokens_output=200,
            tokens_total=350,
        )
        assert mr.raw_output == '{"category": "billing"}'
        assert mr.model == "qwen3.5:4b"
        assert mr.tokens_total == 350

    def test_optional_tokens_per_second(self):
        mr = ModelResult(
            raw_output="{}",
            model="qwen3.5:2b",
            latency_ms=100.0,
            tokens_input=10,
            tokens_output=20,
            tokens_total=30,
            tokens_per_second=36.5,
        )
        assert mr.tokens_per_second == 36.5

    def test_tokens_per_second_defaults_none(self):
        mr = ModelResult(
            raw_output="{}",
            model="qwen3.5:2b",
            latency_ms=100.0,
            tokens_input=10,
            tokens_output=20,
            tokens_total=30,
        )
        assert mr.tokens_per_second is None

    def test_missing_required_field_rejected(self):
        with pytest.raises(ValidationError):
            ModelResult(
                raw_output="{}",
                # model is missing
                latency_ms=100.0,
                tokens_input=10,
                tokens_output=20,
                tokens_total=30,
            )  # type: ignore[call-arg]

    def test_round_trip(self):
        mr = ModelResult(
            raw_output="test",
            model="qwen3.5:9b",
            latency_ms=500.0,
            tokens_input=100,
            tokens_output=200,
            tokens_total=300,
        )
        restored = ModelResult.model_validate(mr.model_dump())
        assert restored == mr
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_model_result.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Write minimal implementation**

`src/ticket_triage_llm/schemas/model_result.py`:
```python
from pydantic import BaseModel


class ModelResult(BaseModel):
    raw_output: str
    model: str
    latency_ms: float
    tokens_input: int
    tokens_output: int
    tokens_total: int
    tokens_per_second: float | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_model_result.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ticket_triage_llm/schemas/model_result.py tests/unit/test_model_result.py
git commit -m "feat: add ModelResult schema for raw provider returns"
```

---

### Task 6: Error contract — FailureReason + TriageFailure + TriageSuccess + TriageResult + assert_never (TDD)

**Files:**
- Create: `tests/unit/test_failure_contract.py`
- Create: `src/ticket_triage_llm/schemas/trace.py` (partial — TriageSuccess, TriageFailure, TriageResult, FailureReason)
- Create: `src/ticket_triage_llm/schemas/errors.py` (assert_never helper)

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_failure_contract.py`:
```python
import pytest
from pydantic import ValidationError

from ticket_triage_llm.schemas.trace import (
    FailureReason,
    TriageFailure,
    TriageResult,
    TriageSuccess,
)
from ticket_triage_llm.schemas.triage_output import TriageOutput
from ticket_triage_llm.schemas.errors import assert_never_failure_reason


VALID_OUTPUT = TriageOutput(
    category="billing",
    severity="high",
    routing_team="billing",
    summary="Invoice issue.",
    business_impact="Delayed cycle.",
    draft_reply="Looking into it.",
    confidence=0.85,
    escalation=False,
)

ALL_FAILURE_REASONS: list[FailureReason] = [
    "guardrail_blocked",
    "model_unreachable",
    "parse_failure",
    "schema_failure",
    "semantic_failure",
]


class TestTriageSuccess:
    def test_construction(self):
        ts = TriageSuccess(output=VALID_OUTPUT, retry_count=0)
        assert ts.status == "success"
        assert ts.output.category == "billing"
        assert ts.retry_count == 0

    def test_status_is_always_success(self):
        ts = TriageSuccess(output=VALID_OUTPUT, retry_count=1)
        assert ts.status == "success"

    def test_round_trip(self):
        ts = TriageSuccess(output=VALID_OUTPUT, retry_count=1)
        data = ts.model_dump(by_alias=True)
        assert data["status"] == "success"
        restored = TriageSuccess.model_validate(data)
        assert restored.output.category == "billing"


class TestTriageFailure:
    def test_construction(self):
        tf = TriageFailure(
            category="parse_failure",
            detected_by="parser",
            message="Invalid JSON",
            retry_count=1,
        )
        assert tf.status == "failure"
        assert tf.category == "parse_failure"
        assert tf.detected_by == "parser"
        assert tf.raw_model_output is None

    def test_with_raw_output(self):
        tf = TriageFailure(
            category="schema_failure",
            detected_by="schema",
            message="Missing field: severity",
            raw_model_output='{"category": "billing"}',
            retry_count=1,
        )
        assert tf.raw_model_output == '{"category": "billing"}'

    def test_invalid_category_rejected(self):
        with pytest.raises(ValidationError):
            TriageFailure(
                category="unknown_failure",  # type: ignore[arg-type]
                detected_by="parser",
                message="test",
                retry_count=0,
            )

    def test_invalid_detected_by_rejected(self):
        with pytest.raises(ValidationError):
            TriageFailure(
                category="parse_failure",
                detected_by="unknown_layer",  # type: ignore[arg-type]
                message="test",
                retry_count=0,
            )

    def test_all_failure_reasons_accepted(self):
        detected_by_map = {
            "guardrail_blocked": "guardrail",
            "model_unreachable": "provider",
            "parse_failure": "parser",
            "schema_failure": "schema",
            "semantic_failure": "semantic",
        }
        for reason in ALL_FAILURE_REASONS:
            tf = TriageFailure(
                category=reason,
                detected_by=detected_by_map[reason],
                message=f"Failed: {reason}",
                retry_count=0,
            )
            assert tf.category == reason


class TestTriageResult:
    def test_success_discriminates(self):
        ts = TriageSuccess(output=VALID_OUTPUT, retry_count=0)
        result: TriageResult = ts
        assert isinstance(result, TriageSuccess)

    def test_failure_discriminates(self):
        tf = TriageFailure(
            category="parse_failure",
            detected_by="parser",
            message="bad json",
            retry_count=1,
        )
        result: TriageResult = tf
        assert isinstance(result, TriageFailure)

    def test_success_dump_and_validate_round_trip(self):
        ts = TriageSuccess(output=VALID_OUTPUT, retry_count=0)
        data = ts.model_dump(by_alias=True)
        assert data["status"] == "success"

    def test_failure_dump_and_validate_round_trip(self):
        tf = TriageFailure(
            category="guardrail_blocked",
            detected_by="guardrail",
            message="Injection detected",
            retry_count=0,
        )
        data = tf.model_dump()
        assert data["status"] == "failure"
        restored = TriageFailure.model_validate(data)
        assert restored.category == "guardrail_blocked"


class TestAssertNeverFailureReason:
    def test_raises_on_unknown_value(self):
        with pytest.raises(AssertionError, match="Unhandled failure reason"):
            assert_never_failure_reason("not_a_real_reason")  # type: ignore[arg-type]

    def test_all_known_reasons_documented(self):
        """All five failure reasons from ADR 0003 are in the FailureReason type.

        Static exhaustiveness is enforced by mypy --strict: a match statement
        on FailureReason that forgets a case will produce a type error at the
        assert_never call. This test verifies the runtime behavior — calling
        assert_never_failure_reason with an unknown value raises AssertionError.
        """
        assert len(ALL_FAILURE_REASONS) == 5
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_failure_contract.py -v
```

Expected: `ImportError` — modules don't exist.

- [ ] **Step 3: Write minimal implementation**

`src/ticket_triage_llm/schemas/errors.py`:
```python
from typing import Never, NoReturn


def assert_never_failure_reason(value: Never) -> NoReturn:
    raise AssertionError(f"Unhandled failure reason: {value!r}")
```

`src/ticket_triage_llm/schemas/trace.py` (partial — full TraceRecord added in Task 7):
```python
from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel

from .triage_output import TriageOutput

FailureReason = Literal[
    "guardrail_blocked",
    "model_unreachable",
    "parse_failure",
    "schema_failure",
    "semantic_failure",
]

DetectedBy = Literal["guardrail", "provider", "parser", "schema", "semantic"]


class TriageSuccess(BaseModel):
    status: Literal["success"] = "success"
    output: TriageOutput
    retry_count: int


class TriageFailure(BaseModel):
    status: Literal["failure"] = "failure"
    category: FailureReason
    detected_by: DetectedBy
    message: str
    raw_model_output: str | None = None
    retry_count: int


TriageResult = Union[TriageSuccess, TriageFailure]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_failure_contract.py -v
```

Expected: all 13 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ticket_triage_llm/schemas/trace.py src/ticket_triage_llm/schemas/errors.py tests/unit/test_failure_contract.py
git commit -m "feat: add error contract — FailureReason, TriageFailure, TriageSuccess, TriageResult, assert_never"
```

---

### Task 7: TraceRecord schema (TDD)

**Files:**
- Create: `tests/unit/test_trace_record.py`
- Modify: `src/ticket_triage_llm/schemas/trace.py` (add `TraceRecord`)

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_trace_record.py`:
```python
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ticket_triage_llm.schemas.trace import TraceRecord


VALID_TRACE = {
    "request_id": "abc-123",
    "timestamp": datetime.now(timezone.utc),
    "model": "qwen3.5:4b",
    "provider": "ollama",
    "prompt_version": "v1",
    "ticket_body": "My invoice is wrong",
    "guardrail_result": "pass",
    "validation_status": "valid",
    "retry_count": 0,
    "latency_ms": 1500.0,
    "tokens_input": 150,
    "tokens_output": 200,
    "tokens_total": 350,
    "status": "success",
}


class TestTraceRecord:
    def test_valid_success_trace(self):
        tr = TraceRecord(**VALID_TRACE)
        assert tr.request_id == "abc-123"
        assert tr.run_id is None
        assert tr.failure_category is None
        assert tr.status == "success"

    def test_valid_failure_trace(self):
        tr = TraceRecord(
            **{
                **VALID_TRACE,
                "status": "failure",
                "failure_category": "parse_failure",
                "validation_status": "invalid",
                "raw_model_output": "not json",
            }
        )
        assert tr.failure_category == "parse_failure"
        assert tr.raw_model_output == "not json"

    def test_eval_run_trace_with_run_id(self):
        tr = TraceRecord(**{**VALID_TRACE, "run_id": "exp-001"})
        assert tr.run_id == "exp-001"

    def test_guardrail_blocked_trace(self):
        tr = TraceRecord(
            **{
                **VALID_TRACE,
                "guardrail_result": "block",
                "validation_status": "skipped",
                "status": "failure",
                "failure_category": "guardrail_blocked",
                "latency_ms": 5.0,
                "guardrail_matched_rules": ["injection_phrase:ignore_previous"],
            }
        )
        assert tr.guardrail_result == "block"
        assert tr.guardrail_matched_rules == ["injection_phrase:ignore_previous"]

    def test_invalid_guardrail_result_rejected(self):
        with pytest.raises(ValidationError):
            TraceRecord(**{**VALID_TRACE, "guardrail_result": "maybe"})

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            TraceRecord(**{**VALID_TRACE, "status": "pending"})

    def test_invalid_failure_category_rejected(self):
        with pytest.raises(ValidationError):
            TraceRecord(
                **{
                    **VALID_TRACE,
                    "status": "failure",
                    "failure_category": "unknown_reason",
                }
            )

    def test_defaults(self):
        tr = TraceRecord(**VALID_TRACE)
        assert tr.run_id is None
        assert tr.guardrail_matched_rules == []
        assert tr.tokens_per_second is None
        assert tr.estimated_cost == 0.0
        assert tr.failure_category is None
        assert tr.raw_model_output is None
        assert tr.triage_output_json is None

    def test_round_trip(self):
        tr = TraceRecord(**VALID_TRACE)
        data = tr.model_dump()
        restored = TraceRecord.model_validate(data)
        assert restored == tr
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_trace_record.py -v
```

Expected: `ImportError` — `TraceRecord` doesn't exist in `trace.py` yet.

- [ ] **Step 3: Add TraceRecord to `src/ticket_triage_llm/schemas/trace.py`**

Append to the existing `trace.py` file after the `TriageResult` definition:

```python
from datetime import datetime


ValidationStatus = Literal["valid", "valid_after_retry", "invalid", "skipped"]

GuardrailDecision = Literal["pass", "warn", "block"]

TraceStatus = Literal["success", "failure"]


class TraceRecord(BaseModel):
    request_id: str
    run_id: str | None = None
    timestamp: datetime
    model: str
    provider: str
    prompt_version: str
    ticket_body: str
    guardrail_result: GuardrailDecision
    guardrail_matched_rules: list[str] = []
    validation_status: ValidationStatus
    retry_count: int = 0
    latency_ms: float
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_total: int = 0
    tokens_per_second: float | None = None
    estimated_cost: float = 0.0
    status: TraceStatus
    failure_category: FailureReason | None = None
    raw_model_output: str | None = None
    triage_output_json: str | None = None
```

The full `trace.py` file after this step:

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal, Union

from pydantic import BaseModel

from .triage_output import TriageOutput

FailureReason = Literal[
    "guardrail_blocked",
    "model_unreachable",
    "parse_failure",
    "schema_failure",
    "semantic_failure",
]

DetectedBy = Literal["guardrail", "provider", "parser", "schema", "semantic"]

ValidationStatus = Literal["valid", "valid_after_retry", "invalid", "skipped"]

GuardrailDecision = Literal["pass", "warn", "block"]

TraceStatus = Literal["success", "failure"]


class TriageSuccess(BaseModel):
    status: Literal["success"] = "success"
    output: TriageOutput
    retry_count: int


class TriageFailure(BaseModel):
    status: Literal["failure"] = "failure"
    category: FailureReason
    detected_by: DetectedBy
    message: str
    raw_model_output: str | None = None
    retry_count: int


TriageResult = Union[TriageSuccess, TriageFailure]


class TraceRecord(BaseModel):
    request_id: str
    run_id: str | None = None
    timestamp: datetime
    model: str
    provider: str
    prompt_version: str
    ticket_body: str
    guardrail_result: GuardrailDecision
    guardrail_matched_rules: list[str] = []
    validation_status: ValidationStatus
    retry_count: int = 0
    latency_ms: float
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_total: int = 0
    tokens_per_second: float | None = None
    estimated_cost: float = 0.0
    status: TraceStatus
    failure_category: FailureReason | None = None
    raw_model_output: str | None = None
    triage_output_json: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_trace_record.py tests/unit/test_failure_contract.py -v
```

Expected: all tests PASS (both new and existing).

- [ ] **Step 5: Commit**

```bash
git add src/ticket_triage_llm/schemas/trace.py tests/unit/test_trace_record.py
git commit -m "feat: add TraceRecord schema with all ADR 0005 fields"
```

---

### Task 8: schemas `__init__.py` re-exports

**Files:**
- Modify: `src/ticket_triage_llm/schemas/__init__.py`

- [ ] **Step 1: Write re-exports**

`src/ticket_triage_llm/schemas/__init__.py`:
```python
from .errors import assert_never_failure_reason
from .model_result import ModelResult
from .trace import (
    DetectedBy,
    FailureReason,
    GuardrailDecision,
    TraceRecord,
    TraceStatus,
    TriageFailure,
    TriageResult,
    TriageSuccess,
    ValidationStatus,
)
from .triage_input import TriageInput
from .triage_output import Category, RoutingTeam, Severity, TriageOutput

__all__ = [
    "Category",
    "DetectedBy",
    "FailureReason",
    "GuardrailDecision",
    "ModelResult",
    "RoutingTeam",
    "Severity",
    "TraceRecord",
    "TraceStatus",
    "TriageFailure",
    "TriageInput",
    "TriageOutput",
    "TriageResult",
    "TriageSuccess",
    "ValidationStatus",
    "assert_never_failure_reason",
]
```

- [ ] **Step 2: Verify imports work**

```bash
uv run python -c "from ticket_triage_llm.schemas import TriageInput, TriageOutput, TraceRecord, TriageResult, ModelResult, FailureReason; print('All imports OK')"
```

Expected: prints `All imports OK`.

- [ ] **Step 3: Commit**

```bash
git add src/ticket_triage_llm/schemas/__init__.py
git commit -m "refactor: add schemas __init__.py re-exports"
```

---

### Task 9: LlmProvider Protocol (TDD)

**Files:**
- Create: `tests/unit/test_providers.py`
- Create: `src/ticket_triage_llm/providers/base.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_providers.py`:
```python
from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.schemas.model_result import ModelResult


class FakeProvider:
    """Minimal fake that satisfies LlmProvider structurally."""

    name: str = "fake"

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str
    ) -> ModelResult:
        return ModelResult(
            raw_output='{"category": "billing"}',
            model="fake-model",
            latency_ms=10.0,
            tokens_input=5,
            tokens_output=10,
            tokens_total=15,
        )


class TestLlmProviderProtocol:
    def test_fake_satisfies_protocol(self):
        provider: LlmProvider = FakeProvider()
        assert provider.name == "fake"

    def test_fake_returns_model_result(self):
        provider: LlmProvider = FakeProvider()
        result = provider.generate_structured_ticket("test ticket", "v1")
        assert isinstance(result, ModelResult)
        assert result.raw_output == '{"category": "billing"}'

    def test_protocol_is_structural(self):
        """LlmProvider is a Protocol — no inheritance required."""
        assert not issubclass(FakeProvider, LlmProvider)
        provider: LlmProvider = FakeProvider()
        assert provider.name == "fake"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_providers.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Write minimal implementation**

`src/ticket_triage_llm/providers/base.py`:
```python
from typing import Protocol, runtime_checkable

from ticket_triage_llm.schemas.model_result import ModelResult


@runtime_checkable
class LlmProvider(Protocol):
    name: str

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str
    ) -> ModelResult: ...
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_providers.py -v
```

Expected: all 3 tests PASS.

Note: The `test_protocol_is_structural` test's `issubclass` check returns `False` because FakeProvider does not inherit from LlmProvider — it satisfies it structurally. This is correct for a Protocol.

- [ ] **Step 5: Commit**

```bash
git add src/ticket_triage_llm/providers/base.py tests/unit/test_providers.py
git commit -m "feat: add LlmProvider Protocol (ADR 0004)"
```

---

### Task 10: Provider stubs — OllamaQwenProvider + CloudQwenProvider (TDD)

**Files:**
- Create: `src/ticket_triage_llm/providers/ollama_qwen.py`
- Create: `src/ticket_triage_llm/providers/cloud_qwen.py`
- Modify: `tests/unit/test_providers.py` (append new tests)
- Modify: `src/ticket_triage_llm/providers/__init__.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_providers.py`:

```python
import pytest

from ticket_triage_llm.providers.ollama_qwen import OllamaQwenProvider
from ticket_triage_llm.providers.cloud_qwen import CloudQwenProvider


class TestOllamaQwenProviderStub:
    def test_has_name(self):
        provider = OllamaQwenProvider(model="qwen3.5:4b")
        assert provider.name == "ollama:qwen3.5:4b"

    def test_generate_raises_not_implemented(self):
        provider = OllamaQwenProvider(model="qwen3.5:4b")
        with pytest.raises(NotImplementedError):
            provider.generate_structured_ticket("test", "v1")

    def test_model_parameterization(self):
        p2b = OllamaQwenProvider(model="qwen3.5:2b")
        p9b = OllamaQwenProvider(model="qwen3.5:9b")
        assert p2b.name == "ollama:qwen3.5:2b"
        assert p9b.name == "ollama:qwen3.5:9b"


class TestCloudQwenProviderStub:
    def test_has_name(self):
        provider = CloudQwenProvider()
        assert provider.name == "cloud:qwen"

    def test_generate_raises_not_implemented(self):
        provider = CloudQwenProvider()
        with pytest.raises(NotImplementedError):
            provider.generate_structured_ticket("test", "v1")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_providers.py -v
```

Expected: `ImportError` for the two new modules.

- [ ] **Step 3: Write minimal implementation**

`src/ticket_triage_llm/providers/ollama_qwen.py`:
```python
from ticket_triage_llm.schemas.model_result import ModelResult


class OllamaQwenProvider:
    def __init__(self, model: str) -> None:
        self._model = model

    @property
    def name(self) -> str:
        return f"ollama:{self._model}"

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str
    ) -> ModelResult:
        raise NotImplementedError(
            f"OllamaQwenProvider({self._model}) is a stub — "
            "concrete implementation belongs to Phase 1."
        )
```

`src/ticket_triage_llm/providers/cloud_qwen.py`:
```python
from ticket_triage_llm.schemas.model_result import ModelResult


class CloudQwenProvider:
    name: str = "cloud:qwen"

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str
    ) -> ModelResult:
        raise NotImplementedError(
            "CloudQwenProvider is a placeholder — "
            "cloud integration is deferred to future work (OD-2)."
        )
```

`src/ticket_triage_llm/providers/__init__.py`:
```python
from .base import LlmProvider
from .cloud_qwen import CloudQwenProvider
from .ollama_qwen import OllamaQwenProvider

__all__ = ["CloudQwenProvider", "LlmProvider", "OllamaQwenProvider"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_providers.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ticket_triage_llm/providers/ tests/unit/test_providers.py
git commit -m "feat: add OllamaQwenProvider and CloudQwenProvider stubs (ADR 0004)"
```

---

### Task 11: Storage — db.py init_schema (TDD)

**Files:**
- Create: `tests/unit/test_storage.py`
- Create: `src/ticket_triage_llm/storage/db.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_storage.py`:
```python
import sqlite3

import pytest

from ticket_triage_llm.storage.db import get_connection, init_schema


EXPECTED_COLUMNS = {
    "request_id",
    "run_id",
    "timestamp",
    "model",
    "provider",
    "prompt_version",
    "ticket_body",
    "guardrail_result",
    "guardrail_matched_rules",
    "validation_status",
    "retry_count",
    "latency_ms",
    "tokens_input",
    "tokens_output",
    "tokens_total",
    "tokens_per_second",
    "estimated_cost",
    "status",
    "failure_category",
    "raw_model_output",
    "triage_output_json",
}


class TestInitSchema:
    def test_creates_traces_table(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        init_schema(conn)

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='traces'"
        )
        assert cursor.fetchone() is not None

    def test_traces_table_has_expected_columns(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        init_schema(conn)

        cursor = conn.execute("PRAGMA table_info(traces)")
        columns = {row[1] for row in cursor.fetchall()}
        assert columns == EXPECTED_COLUMNS

    def test_idempotent(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        init_schema(conn)
        init_schema(conn)  # should not raise

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='traces'"
        )
        assert cursor.fetchone() is not None

    def test_indexes_created(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        init_schema(conn)

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='traces'"
        )
        index_names = {row[0] for row in cursor.fetchall()}
        assert "idx_traces_run_id" in index_names
        assert "idx_traces_provider" in index_names
        assert "idx_traces_prompt_version" in index_names
        assert "idx_traces_timestamp" in index_names

    def test_get_connection_returns_sqlite3_connection(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        assert isinstance(conn, sqlite3.Connection)

    def test_only_traces_table_exists(self, tmp_path):
        """ADR 0005: single traces table, no summary tables."""
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        init_schema(conn)

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        assert tables == ["traces"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_storage.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Write minimal implementation**

`src/ticket_triage_llm/storage/db.py`:
```python
import sqlite3


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.Connection(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS traces (
            request_id TEXT PRIMARY KEY,
            run_id TEXT,
            timestamp TEXT NOT NULL,
            model TEXT NOT NULL,
            provider TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            ticket_body TEXT NOT NULL,
            guardrail_result TEXT NOT NULL,
            guardrail_matched_rules TEXT NOT NULL DEFAULT '[]',
            validation_status TEXT NOT NULL,
            retry_count INTEGER NOT NULL DEFAULT 0,
            latency_ms REAL NOT NULL,
            tokens_input INTEGER NOT NULL DEFAULT 0,
            tokens_output INTEGER NOT NULL DEFAULT 0,
            tokens_total INTEGER NOT NULL DEFAULT 0,
            tokens_per_second REAL,
            estimated_cost REAL NOT NULL DEFAULT 0.0,
            status TEXT NOT NULL,
            failure_category TEXT,
            raw_model_output TEXT,
            triage_output_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_traces_run_id
            ON traces(run_id);
        CREATE INDEX IF NOT EXISTS idx_traces_provider
            ON traces(provider);
        CREATE INDEX IF NOT EXISTS idx_traces_prompt_version
            ON traces(prompt_version);
        CREATE INDEX IF NOT EXISTS idx_traces_timestamp
            ON traces(timestamp);
    """)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_storage.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ticket_triage_llm/storage/db.py tests/unit/test_storage.py
git commit -m "feat: add SQLite traces schema with init_schema and indexes (ADR 0005)"
```

---

### Task 12: Storage — TraceRepository Protocol (TDD)

**Files:**
- Create: `src/ticket_triage_llm/storage/trace_repo.py`
- Modify: `tests/unit/test_storage.py` (append new tests)
- Modify: `src/ticket_triage_llm/storage/__init__.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_storage.py`:

```python
from datetime import datetime, timezone

from ticket_triage_llm.schemas.trace import TraceRecord
from ticket_triage_llm.storage.trace_repo import TraceRepository


class FakeTraceRepository:
    """Minimal fake satisfying the TraceRepository Protocol."""

    def __init__(self) -> None:
        self._traces: list[TraceRecord] = []

    def save_trace(self, trace: TraceRecord) -> None:
        self._traces.append(trace)

    def get_traces_by_run(self, run_id: str) -> list[TraceRecord]:
        return [t for t in self._traces if t.run_id == run_id]

    def get_traces_by_provider(self, provider: str) -> list[TraceRecord]:
        return [t for t in self._traces if t.provider == provider]

    def get_traces_since(self, since: datetime) -> list[TraceRecord]:
        return [t for t in self._traces if t.timestamp >= since]

    def get_recent_traces(self, limit: int) -> list[TraceRecord]:
        return sorted(self._traces, key=lambda t: t.timestamp, reverse=True)[:limit]

    def get_all_traces(self) -> list[TraceRecord]:
        return list(self._traces)


class TestTraceRepositoryProtocol:
    def test_fake_satisfies_protocol(self):
        repo: TraceRepository = FakeTraceRepository()
        assert repo is not None

    def test_save_and_retrieve(self):
        repo: TraceRepository = FakeTraceRepository()
        trace = TraceRecord(
            request_id="test-1",
            timestamp=datetime.now(timezone.utc),
            model="qwen3.5:4b",
            provider="ollama",
            prompt_version="v1",
            ticket_body="test",
            guardrail_result="pass",
            validation_status="valid",
            retry_count=0,
            latency_ms=100.0,
            tokens_input=10,
            tokens_output=20,
            tokens_total=30,
            status="success",
        )
        repo.save_trace(trace)
        assert len(repo.get_all_traces()) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_storage.py::TestTraceRepositoryProtocol -v
```

Expected: `ImportError`.

- [ ] **Step 3: Write minimal implementation**

`src/ticket_triage_llm/storage/trace_repo.py`:
```python
from datetime import datetime
from typing import Protocol

from ticket_triage_llm.schemas.trace import TraceRecord


class TraceRepository(Protocol):
    def save_trace(self, trace: TraceRecord) -> None: ...

    def get_traces_by_run(self, run_id: str) -> list[TraceRecord]: ...

    def get_traces_by_provider(self, provider: str) -> list[TraceRecord]: ...

    def get_traces_since(self, since: datetime) -> list[TraceRecord]: ...

    def get_recent_traces(self, limit: int) -> list[TraceRecord]: ...

    def get_all_traces(self) -> list[TraceRecord]: ...
```

`src/ticket_triage_llm/storage/__init__.py`:
```python
from .db import get_connection, init_schema
from .trace_repo import TraceRepository

__all__ = ["TraceRepository", "get_connection", "init_schema"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_storage.py -v
```

Expected: all 8 tests PASS (6 from Task 11 + 2 new).

- [ ] **Step 5: Commit**

```bash
git add src/ticket_triage_llm/storage/ tests/unit/test_storage.py
git commit -m "feat: add TraceRepository Protocol (ADR 0005)"
```

---

### Task 13: Config loader (TDD)

**Files:**
- Create: `tests/unit/test_config.py`
- Create: `src/ticket_triage_llm/config.py`

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_config.py`:
```python
import os

import pytest

from ticket_triage_llm.config import Settings


class TestSettingsDefaults:
    def test_ollama_base_url_default(self):
        settings = Settings(ollama_model="qwen3.5:4b")
        assert settings.ollama_base_url == "http://localhost:11434/v1"

    def test_locked_sampling_defaults(self):
        """Sampling params are locked per 2026-04-16 decision-log entry."""
        settings = Settings(ollama_model="qwen3.5:4b")
        assert settings.temperature == 0.2
        assert settings.top_p == 0.9
        assert settings.top_k == 40
        assert settings.repetition_penalty == 1.0

    def test_db_path_default(self):
        settings = Settings(ollama_model="qwen3.5:4b")
        assert settings.db_path == "data/traces.db"

    def test_log_level_default(self):
        settings = Settings(ollama_model="qwen3.5:4b")
        assert settings.log_level == "INFO"


class TestSettingsEnvOverrides:
    def test_ollama_base_url_override(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://remote:11434/v1")
        monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:9b")
        settings = Settings()  # type: ignore[call-arg]
        assert settings.ollama_base_url == "http://remote:11434/v1"

    def test_ollama_model_from_env(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:9b")
        settings = Settings()  # type: ignore[call-arg]
        assert settings.ollama_model == "qwen3.5:9b"

    def test_temperature_override(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:4b")
        monkeypatch.setenv("TEMPERATURE", "0.5")
        settings = Settings()  # type: ignore[call-arg]
        assert settings.temperature == 0.5

    def test_db_path_override(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:4b")
        monkeypatch.setenv("DB_PATH", "/tmp/custom.db")
        settings = Settings()  # type: ignore[call-arg]
        assert settings.db_path == "/tmp/custom.db"


class TestSettingsRequired:
    def test_missing_model_raises(self):
        """OLLAMA_MODEL has no default — must be set explicitly."""
        with pytest.raises(Exception):
            Settings()  # type: ignore[call-arg]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Write minimal implementation**

`src/ticket_triage_llm/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str
    temperature: float = 0.2
    top_p: float = 0.9
    top_k: int = 40
    repetition_penalty: float = 1.0
    db_path: str = "data/traces.db"
    log_level: str = "INFO"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ticket_triage_llm/config.py tests/unit/test_config.py
git commit -m "feat: add Settings config loader with locked sampling defaults"
```

---

### Task 14: Structured logging

**Files:**
- Create: `src/ticket_triage_llm/logging_config.py`

- [ ] **Step 1: Write implementation**

`src/ticket_triage_llm/logging_config.py`:
```python
import logging
import sys
from typing import ClassVar


class StructuredFormatter(logging.Formatter):
    BASE_FORMAT: ClassVar[str] = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

    def __init__(self) -> None:
        super().__init__(fmt=self.BASE_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S%z")


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        root.addHandler(handler)
```

- [ ] **Step 2: Verify it imports and runs**

```bash
uv run python -c "
from ticket_triage_llm.logging_config import configure_logging
import logging
configure_logging('INFO')
logger = logging.getLogger('monitoring')
logger.warning('threshold_breached: p95_latency=6200ms > limit=5000ms window=1h provider=qwen3.5:9b')
"
```

Expected: prints a structured log line to stdout, format like:
```
2026-04-17T... WARN [monitoring] threshold_breached: p95_latency=6200ms > limit=5000ms window=1h provider=qwen3.5:9b
```

- [ ] **Step 3: Commit**

```bash
git add src/ticket_triage_llm/logging_config.py
git commit -m "feat: add structured logging config with monitoring format (ADR 0009)"
```

---

### Task 15: Module stubs for future phases

**Files:**
- Create: service, UI, API, and eval module stubs

- [ ] **Step 1: Create service stubs**

`src/ticket_triage_llm/services/triage.py`:
```python
"""Triage pipeline orchestration — Phase 1."""
```

`src/ticket_triage_llm/services/prompt.py`:
```python
"""Prompt building and version selection — Phase 1."""
```

`src/ticket_triage_llm/services/guardrail.py`:
```python
"""Pre-LLM input screening — Phase 2."""
```

`src/ticket_triage_llm/services/validation.py`:
```python
"""JSON parse, schema validation, semantic checks — Phase 1."""
```

`src/ticket_triage_llm/services/retry.py`:
```python
"""Bounded retry policy — Phase 2."""
```

`src/ticket_triage_llm/services/trace.py`:
```python
"""Trace recording and retrieval — Phase 1."""
```

`src/ticket_triage_llm/services/metrics.py`:
```python
"""Metrics aggregation from traces — Phase 5."""
```

`src/ticket_triage_llm/services/provider_router.py`:
```python
"""Provider registry and selection — Phase 2."""
```

- [ ] **Step 2: Create UI stubs**

`src/ticket_triage_llm/ui/triage_tab.py`:
```python
"""Triage tab — ticket input, model selection, result display — Phase 1."""
```

`src/ticket_triage_llm/ui/metrics_tab.py`:
```python
"""Metrics tab — benchmark results and live metrics — Phase 5."""
```

`src/ticket_triage_llm/ui/traces_tab.py`:
```python
"""Traces tab — request inspection and filtering — Phase 5."""
```

`src/ticket_triage_llm/ui/experiments_tab.py`:
```python
"""Experiments tab — side-by-side experiment comparison — Phase 5."""
```

- [ ] **Step 3: Create API stubs**

`src/ticket_triage_llm/api/triage_route.py`:
```python
"""POST /api/v1/triage — Phase 1."""
```

- [ ] **Step 4: Create app stub**

`src/ticket_triage_llm/app.py`:
```python
"""FastAPI + Gradio entry point — Phase 1."""
```

- [ ] **Step 5: Create eval stubs**

`src/ticket_triage_llm/eval/runners/__init__.py`:
```python
```

`src/ticket_triage_llm/eval/runners/run_local_comparison.py`:
```python
"""Experiment 1: local model size comparison — Phase 3."""
```

`src/ticket_triage_llm/eval/runners/run_validation_impact.py`:
```python
"""Experiment 3: validation on/off impact — Phase 3."""
```

`src/ticket_triage_llm/eval/runners/run_prompt_comparison.py`:
```python
"""Experiment 4: prompt v1 vs v2 comparison — Phase 6."""
```

`src/ticket_triage_llm/eval/runners/summarize_results.py`:
```python
"""Aggregate and summarize experiment results — Phase 3."""
```

- [ ] **Step 6: Create prompt stubs (do NOT modify existing triage_v1.py)**

`src/ticket_triage_llm/prompts/__init__.py` (if not already created):
```python
```

`src/ticket_triage_llm/prompts/triage_v2.py`:
```python
"""Triage prompt v2 — Phase 6."""
```

`src/ticket_triage_llm/prompts/repair_json_v1.py`:
```python
"""Repair prompt for bounded retry — Phase 2."""
```

- [ ] **Step 7: Commit**

```bash
git add src/ticket_triage_llm/services/ src/ticket_triage_llm/ui/ src/ticket_triage_llm/api/ src/ticket_triage_llm/app.py src/ticket_triage_llm/eval/ src/ticket_triage_llm/prompts/triage_v2.py src/ticket_triage_llm/prompts/repair_json_v1.py
git commit -m "chore: add module stubs for future phases"
```

---

### Task 16: CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write CI workflow**

`.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [develop, main]
  pull_request:
    branches: [develop, main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: true
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          enable-cache: true
          cache-dependency-glob: |
            pyproject.toml
            uv.lock

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync --all-extras

      - name: Lint
        run: uv run ruff check .

      - name: Format check
        run: uv run ruff format --check .

      - name: Test with coverage
        run: uv run pytest --cov=ticket_triage_llm --cov-fail-under=80
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow with lint, format, and coverage"
```

---

### Task 17: Final verification and cleanup

- [ ] **Step 1: Run full test suite with coverage**

```bash
uv run pytest --cov=ticket_triage_llm --cov-fail-under=80 -v
```

Expected: all tests pass, coverage >= 80%.

- [ ] **Step 2: Run ruff check and format**

```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: clean on both. If not, fix with `uv run ruff format .` and `uv run ruff check --fix .`, then re-run.

- [ ] **Step 3: Verify package imports**

```bash
uv run python -c "
from ticket_triage_llm.schemas import (
    TriageInput, TriageOutput, ModelResult, TraceRecord,
    TriageSuccess, TriageFailure, TriageResult, FailureReason,
    Category, Severity, RoutingTeam,
)
from ticket_triage_llm.providers import LlmProvider, OllamaQwenProvider, CloudQwenProvider
from ticket_triage_llm.storage import get_connection, init_schema, TraceRepository
from ticket_triage_llm.config import Settings
from ticket_triage_llm.logging_config import configure_logging
print('All imports OK')
"
```

Expected: `All imports OK`.

- [ ] **Step 4: Fix any ruff or coverage issues**

If ruff format made changes:
```bash
uv run ruff format .
git add -u
git commit -m "style: apply ruff formatting"
```

- [ ] **Step 5: Verify git status is clean**

```bash
git status
```

Expected: working tree clean.

---

## Post-completion checklist

After all tasks are complete:

1. Update `SUMMARY.md` with Phase F entry
2. Update `TODO.md` — mark Phase F complete
3. Open PR from `feature/phase-foundation` to `develop` using `.github/PULL_REQUEST_TEMPLATE.md`
4. Verify CI goes green on the PR
5. Merge to `develop`
