# Phase 2 Design Spec: Provider Abstraction, Retry, and Guardrail

**Date:** 2026-04-17
**Branch:** `feature/phase-2-providers-retry-guardrail`
**Dependencies:** Phase F (Foundation), Phase 1 (happy-path slice)
**PLAN.md mapping:** Phase 2

---

## Overview

Phase 2 adds three composable services to the existing triage pipeline:

1. **Provider router** — registry-based model switching with config-driven registration
2. **Bounded retry** — exactly one repair attempt on validation failure (ADR 0002)
3. **Heuristic guardrail** — pre-LLM input screening for prompt injection (ADR 0008)

Each service is independently testable with clear inputs/outputs. The existing `run_triage()` orchestrator is refactored to compose them: guardrail -> provider -> validate_or_retry -> trace.

---

## 1. Provider Router (`services/provider_router.py`)

### Purpose

Registry mapping provider names to `LlmProvider` instances. The Triage tab dropdown and API route resolve providers through this registry. No `if provider == ...` branching anywhere (ADR 0004).

### Interface

```python
class ProviderRegistry:
    def register(self, provider: LlmProvider) -> None:
        """Add a provider keyed by provider.name."""

    def get(self, name: str) -> LlmProvider:
        """Return provider or raise KeyError."""

    def list_names(self) -> list[str]:
        """Return registered provider names (drives dropdown)."""

    def default(self) -> LlmProvider:
        """Return the first registered provider. Raises RuntimeError if empty."""
```

### Configuration

New env var `OLLAMA_MODELS` (comma-separated): `qwen3.5:2b,qwen3.5:4b,qwen3.5:9b`

`app.py` iterates the list, creates one `OllamaQwenProvider` per model, registers each. The existing `OLLAMA_MODEL` (singular) selects the default model for the dropdown. If `OLLAMA_MODEL` is not set, the first model in `OLLAMA_MODELS` is the default.

### Config changes

`config.py`:
- Add `ollama_models: str` field (comma-separated string)
- Keep `ollama_model: str` as default model selection

`.env.example`:
- Add `OLLAMA_MODELS=qwen3.5:2b,qwen3.5:4b,qwen3.5:9b`

---

## 2. Bounded Retry (`services/retry.py`)

### Purpose

Encapsulates the ADR 0002 retry contract: exactly one retry on validation failure using a repair prompt that includes the failed output and the specific error. Not a blind re-send.

### Interface

```python
@dataclass
class RetryResult:
    result: TriageResult
    retry_count: int
    final_raw_output: str | None

def validate_or_retry(
    raw_output: str,
    provider: LlmProvider,
    prompt_version: str,
    ticket_subject: str,
    ticket_body: str,
) -> RetryResult:
    """Parse and validate raw LLM output; retry once with repair prompt on failure."""
```

### Flow

1. `parse_json(raw_output)` — if fails, build repair prompt with raw output + "failed to parse as JSON" error, send to provider, parse again. Second failure -> `TriageFailure(category="parse_failure", retry_count=1)`.
2. `validate_schema(parsed)` — if fails, same repair flow with validation error message. Second failure -> `TriageFailure(category="schema_failure", retry_count=1)`.
3. First attempt succeeds at both stages -> `TriageSuccess(retry_count=0)`.
4. Retry succeeds -> `TriageSuccess(retry_count=1)`, trace records `validation_status="valid_after_retry"`.

### Repair Prompt (`prompts/repair_json_v1.py`)

System prompt: instructs the model that its previous output was invalid, includes the expected schema shape, and demands only corrected JSON.

User prompt: includes the original raw output and the specific error message (parse error or pydantic validation error string).

Uses the same provider instance (same model, same sampling params). The repair prompt is a separate prompt version string (not "v1"/"v2") — it does not go through `get_prompt()`.

### Provider error during retry

If the provider raises `ProviderError` during the repair call, the retry service catches it and returns `TriageFailure(category="model_unreachable", retry_count=1)`.

---

## 3. Guardrail (`services/guardrail.py`)

### Purpose

Pre-LLM heuristic input screening per ADR 0008. Deliberately pattern-matching only — the baseline numbers from this heuristic guardrail are a Phase 4 deliverable. No LLM-based classification.

### Interface

```python
@dataclass
class GuardrailResult:
    decision: Literal["pass", "warn", "block"]
    matched_rules: list[str]

def check_guardrail(ticket_body: str, max_length: int = 10_000) -> GuardrailResult:
    """Screen ticket body for injection patterns, structural markers, length, PII."""
```

### Rule categories

Each rule has a namespaced string identifier stored in `matched_rules` for per-rule analysis in Phase 4.

1. **Injection phrase patterns** (`injection:*`) — regex matching for known prompt injection phrases:
   - "ignore previous instructions", "ignore all instructions", "ignore above"
   - "you are now", "act as", "pretend you are"
   - "system prompt:", "new instructions:"
   - "disregard above", "disregard previous"
   - Case-insensitive matching.

2. **Structural markers** (`structural:*`) — detects delimiters mimicking system prompt structure:
   - `<system>`, `</system>`, `<s>`, `[INST]`, `[/INST]`, `<<<SYS>>>`, `<<SYS>>`
   - Triple-backtick blocks containing instruction-like keywords

3. **Length checks** (`length:*`) — ticket body exceeding `max_length` chars flagged as suspicious.

4. **Basic PII regex** (`pii:*`) — patterns suggesting sensitive data:
   - SSN: `\d{3}-\d{2}-\d{4}`
   - Credit card: 13-19 digit sequences (with optional separators)
   - These trigger `warn`, not `block`.

### Decision logic

- Any injection phrase or structural marker match -> `block`
- Any PII match or length warning (with no block-level matches) -> `warn`
- No matches -> `pass`
- Multiple rules can match; all are recorded in `matched_rules`.

---

## 4. Pipeline Integration (`services/triage.py`)

### Refactored flow

```
check_guardrail(ticket_body)
    -> block? -> TriageFailure(category="guardrail_blocked") + trace -> return
    -> warn/pass? -> continue

provider.generate_structured_ticket(...)
    -> ProviderError? -> TriageFailure(category="model_unreachable") + trace -> return

validate_or_retry(raw_output, provider, ...)
    -> RetryResult with final TriageResult, retry_count, final_raw_output

save trace with guardrail_result, guardrail_matched_rules, retry_count, validation_status
return result, trace
```

Three exit points. The `_save_trace` duplication is reduced because `retry_count` and `validation_status` come from `RetryResult` and `GuardrailResult` rather than being hardcoded per branch.

### `run_triage` signature

Unchanged: `run_triage(ticket_body, ticket_subject, provider, prompt_version, trace_repo) -> tuple[TriageResult, TraceRecord]`

The function now calls `check_guardrail()` and `validate_or_retry()` internally. The external contract is identical.

---

## 5. UI Changes

### Triage tab

- `build_triage_tab` receives `ProviderRegistry` instead of a single `LlmProvider`.
- `gr.Dropdown` populated from `registry.list_names()` replaces the hardcoded model display.
- Handler resolves the selected name via `registry.get()`.
- Guardrail status shown in the trace summary output.

### API route

- `POST /api/v1/triage` gains an optional `provider` field in the request body.
- If omitted, uses `registry.default()`.

---

## 6. App Startup (`app.py`)

- Parse `OLLAMA_MODELS` env var (comma-separated).
- Create one `OllamaQwenProvider` per model using `settings.ollama_base_url`.
- Build `ProviderRegistry`, register all providers.
- Pass registry to `build_triage_tab` and `configure_api`.

---

## 7. Documentation Updates

- `docs/architecture.md` — update pipeline diagram to show guardrail and retry as real components
- `docs/threat-model.md` — update to reflect implemented guardrail rule categories and their string names
- `CLAUDE.md` — update project status line from "Phase 1 next" to reflect Phase 2 completion
- `README.md` — update to reflect multi-model support and guardrail capabilities
- `SUMMARY.md` — append Phase 2 entry
- `TODO.md` — mark Phase 2 checkboxes complete
- `.env.example` — add `OLLAMA_MODELS`

---

## 8. Test Plan (all TDD)

### `tests/unit/test_provider_router.py`
- Register a provider, retrieve by name
- `list_names()` returns all registered names
- `get()` raises `KeyError` for unknown name
- `default()` returns the first registered provider
- `default()` raises `RuntimeError` if registry is empty
- Duplicate registration (same name) overwrites

### `tests/unit/test_retry.py`
- First-attempt success: parse + schema valid -> `TriageSuccess(retry_count=0)`
- Parse failure, repair succeeds -> `TriageSuccess(retry_count=1)`
- Parse failure, repair also fails -> `TriageFailure(category="parse_failure", retry_count=1)`
- Schema failure, repair succeeds -> `TriageSuccess(retry_count=1)`
- Schema failure, repair also fails -> `TriageFailure(category="schema_failure", retry_count=1)`
- Provider error during retry -> `TriageFailure(category="model_unreachable", retry_count=1)`

### `tests/unit/test_guardrail.py`
- Each injection phrase triggers `block` with correct rule name
- Each structural marker triggers `block` with correct rule name
- Overlength input triggers `warn` with `length:exceeded` rule
- PII patterns (SSN, credit card) trigger `warn` with correct rule names
- Clean input returns `pass` with empty `matched_rules`
- Empty string returns `pass`
- Mixed block + warn rules: decision is `block`, all rules listed
- Case insensitivity for injection phrases

### `tests/unit/test_triage_service.py` (updates)
- Guardrail `block` -> `TriageFailure(category="guardrail_blocked")`, no LLM call
- Guardrail `warn` -> proceeds to LLM, matched rules recorded in trace
- Retry integration: parse failure triggers retry, success after retry recorded as `valid_after_retry`

---

## 9. Files Created or Modified

### New files
- `src/ticket_triage_llm/services/provider_router.py`
- `src/ticket_triage_llm/services/guardrail.py` (replace stub)
- `src/ticket_triage_llm/services/retry.py` (replace stub)
- `src/ticket_triage_llm/prompts/repair_json_v1.py` (replace stub)
- `tests/unit/test_provider_router.py`
- `tests/unit/test_retry.py`
- `tests/unit/test_guardrail.py` (replace Foundation stub if exists)

### Modified files
- `src/ticket_triage_llm/services/triage.py` — integrate guardrail + retry
- `src/ticket_triage_llm/ui/triage_tab.py` — dropdown from registry
- `src/ticket_triage_llm/api/triage_route.py` — optional provider field
- `src/ticket_triage_llm/app.py` — multi-model startup, registry wiring
- `src/ticket_triage_llm/config.py` — add `ollama_models`, `guardrail_max_length`
- `tests/unit/test_triage_service.py` — add guardrail/retry test cases
- `.env.example`
- `docs/architecture.md`
- `docs/threat-model.md`
- `CLAUDE.md`
- `README.md`
- `SUMMARY.md`
- `TODO.md`
