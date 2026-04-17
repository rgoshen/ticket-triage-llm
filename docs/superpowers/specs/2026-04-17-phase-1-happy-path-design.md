# Phase 1 Design: Single Happy-Path Slice

**Date:** 2026-04-17
**Status:** Approved
**Branch:** `feature/phase-1-happy-path` (off `develop`)
**PLAN.md mapping:** Phase 1
**Approach:** Flat procedural pipeline (Approach 1)

---

## Overview

Phase 1 delivers the first end-to-end triage slice: a single model, a single prompt version, one Gradio tab, one API endpoint, trace storage, and a Dockerfile. The system is demo-able after this phase completes.

The pipeline is a linear function — no retry, no real guardrail, no provider switching. Each step is a standalone function in its own module. Failures at any step produce a typed `TriageFailure`; success produces a `TriageSuccess`. Every exit path saves a trace.

---

## 1. OllamaQwenProvider implementation

**File:** `src/ticket_triage_llm/providers/ollama_qwen.py`

Fills in the existing stub. Uses the `openai` Python client pointed at the Ollama OpenAI-compatible endpoint.

- **Constructor:** `__init__(self, model: str, base_url: str)`
- **`name` property:** returns `f"ollama:{self._model}"`
- **`generate_structured_ticket(ticket_body, prompt_version)`:**
  - Creates `OpenAI(base_url=base_url, api_key="ollama")` (Ollama ignores the key but the client requires one)
  - Calls `client.chat.completions.create()` with system + user messages
  - Passes locked sampling params (`TEMPERATURE`, `TOP_P`, `TOP_K`, `REPETITION_PENALTY`) via `extra_body`
  - Sets `max_tokens=2048` to cap reasoning runaway (Phase 0 finding: 2B hit 652s on ticket n-007)
  - Times the call with `time.perf_counter()` for `latency_ms`
  - Extracts token counts from `response.usage`
  - Returns `ModelResult(raw_output, model, latency_ms, tokens_*)`
  - On connection error: raises a `ProviderError` (new exception in `providers/` package)

**Model independence:** The model name is a constructor parameter, not hardcoded. Swapping models is a config change. The pipeline imports `LlmProvider`, never `OllamaQwenProvider` directly.

---

## 2. Prompt service

**File:** `src/ticket_triage_llm/services/prompt.py`

Dispatch layer mapping version strings to prompt implementations.

- **`get_prompt(version, ticket_subject, ticket_body) -> tuple[str, str]`** — returns `(system_prompt, user_prompt)`
- For `"v1"`: imports from `prompts/triage_v1.py`, returns `(SYSTEM_PROMPT, build_user_prompt(subject, body))`
- For unknown versions: raises `ValueError`
- Phase 6 adds `"v2"` as another branch

The `triage_v1.py` module is already fully written in Phase F.

---

## 3. Validation service

**File:** `src/ticket_triage_llm/services/validation.py`

Two-step validation, no retry.

- **`parse_json(raw_output: str) -> dict | None`** — strips markdown fences (` ```json ... ``` `), attempts `json.loads()`, returns dict or `None`
- **`validate_schema(data: dict) -> TriageOutput | None`** — passes to `TriageOutput.model_validate(data)`, returns validated model or `None` on `ValidationError`
- No semantic checks in Phase 1 (Phase 2 territory)

---

## 4. Triage service (pipeline orchestrator)

**File:** `src/ticket_triage_llm/services/triage.py`

Single function, flat pipeline. All dependencies passed as parameters.

```
run_triage(
    ticket_body: str,
    ticket_subject: str,
    provider: LlmProvider,
    prompt_version: str,
    trace_repo: TraceRepository,
) -> TriageResult
```

**Flow:**

1. Generate `request_id` (UUID4)
2. Start timer
3. Guardrail stub: `guardrail_result="pass"`, `matched_rules=[]`
4. Build prompt via `prompt.get_prompt(version, subject, body)`
5. Call `provider.generate_structured_ticket()` — try/except `ProviderError` -> `TriageFailure(category="model_unreachable")`
6. Parse JSON — `None` -> `TriageFailure(category="parse_failure")`
7. Validate schema — `None` -> `TriageFailure(category="schema_failure")`
8. Success: `TriageSuccess(output=triage_output, retry_count=0)`
9. Build `TraceRecord` from all collected data
10. Save trace via `trace_repo.save_trace(trace)`
11. Return `TriageResult`

Every exit path (success or failure) builds and saves a trace.

---

## 5. Trace service + SQLite repository

**Files:** `src/ticket_triage_llm/services/trace.py`, leveraging `storage/db.py`

**`SqliteTraceRepository`** — concrete class implementing `TraceRepository` Protocol:

- Constructor takes `sqlite3.Connection`
- **`save_trace(trace)`** — INSERT with JSON serialization for `guardrail_matched_rules` and `triage_output_json`
- **`get_recent_traces(limit)`** — SELECT ordered by timestamp DESC, LIMIT
- Remaining 4 query methods: `NotImplementedError` until Phase 3/5

Located in `services/trace.py` for now. No additional service-layer abstraction needed in Phase 1.

---

## 6. FastAPI + Gradio app

### `app.py` (entry point)

- Creates `FastAPI` as the outer app
- Loads `Settings` from env
- Initializes SQLite: `get_connection()` + `init_schema()` + `SqliteTraceRepository`
- Creates `OllamaQwenProvider(settings.ollama_model, settings.ollama_base_url)`
- Builds Gradio `gr.Blocks` with Triage tab
- Mounts Gradio at `/` via `gr.mount_gradio_app()`
- Includes API router at `/api/v1`
- Runs uvicorn on port 7860

### `api/triage_route.py`

- `POST /api/v1/triage` — accepts `TriageInput`, calls `run_triage()`, returns `TriageResult`
- Swagger at `/api/v1/docs`

### `ui/triage_tab.py`

- `build_triage_tab(provider, trace_repo) -> gr.Blocks`
- Ticket input textarea + subject field
- "Triage" submit button
- Structured result panel (TriageOutput fields or failure info)
- Trace summary: latency, tokens, validation status
- No model dropdown (Phase 2)

### Dependency wiring

App startup creates provider and repo once. Both API route and Gradio tab receive them as closures/parameters. No global singletons, no import-time side effects.

---

## 7. Dockerfile

**File:** `Dockerfile`

- Multi-stage build: builder installs deps with `uv`, runtime copies installed environment
- Base image: `python:3.11-slim`
- Exposes port 7860
- `CMD`: `python -m ticket_triage_llm.app`
- No Ollama inside container (ADR 0007)
- Default `OLLAMA_BASE_URL=http://host.docker.internal:11434/v1` (Mac/Windows), overridable for Linux

---

## 8. Testing strategy

**TDD (service/business logic):**

| Test file | Coverage |
|---|---|
| `test_prompt_service.py` | `get_prompt("v1")` returns correct prompts; unknown version raises `ValueError` |
| `test_validation.py` | `parse_json()`: valid JSON, markdown-fenced, invalid; `validate_schema()`: valid, missing fields, bad enums |
| `test_triage_service.py` | Happy path (mocked provider, valid JSON); parse failure; schema failure; provider error. Asserts correct `TriageResult` variant + trace saved |
| `test_sqlite_trace_repo.py` | `save_trace()` round-trips through `get_recent_traces()`; in-memory SQLite |

**Judgment-based:**

| Test file | Coverage |
|---|---|
| `test_api_route.py` | FastAPI `TestClient`, `POST /api/v1/triage` with mocked provider, 200 + correct schema |
| Dockerfile build | Verify `docker build` succeeds (skip if Docker unavailable in CI) |

No tests require a live Ollama instance.

---

## Out of scope for Phase 1

- Retry/repair logic (Phase 2)
- Real guardrail (Phase 2)
- Provider router / model dropdown (Phase 2)
- Semantic validation checks (Phase 2)
- Metrics/Traces/Experiments tabs (Phase 5)
- Prompt v2 (Phase 6)

---

## Key design decisions

| Decision | Rationale |
|---|---|
| Flat procedural pipeline | Simplest orchestration; easy to TDD; Phase 2 wraps parse+validate in retry loop without restructuring |
| Fail on first validation error | No retry in Phase 1 (Option A); retry_count always 0 |
| max_tokens=2048 | Caps reasoning runaway (Phase 0 finding) |
| ProviderError exception | Clean domain exception for connection failures; mapped to TriageFailure in run_triage |
| Strip markdown fences in parser | Defense-in-depth; smaller models wrap JSON despite instructions |
| SqliteTraceRepository with 2 of 6 methods | YAGNI; Protocol defines full contract, Phase 1 implements what it needs |
| Dependencies as function parameters | No globals, no singletons; testable with mocks via duck typing |
