# Architecture

This document describes the system architecture of `ticket-triage-llm`: the pipeline flow, the component responsibilities, and how the pieces connect. For the *reasoning* behind each architectural choice, see the [ADRs](adr/README.md). This document describes *what* the architecture is; the ADRs describe *why*.

---

## System overview

The system is a single-process Python application that accepts a support ticket as text input and produces a structured triage result. It is built around three principles:

1. **Validator-first:** all model output is untrusted until validated ([ADR 0002](adr/0002-validator-first-pipeline-with-bounded-retry.md))
2. **Provider-abstracted:** the pipeline does not know or care which model or hosting environment is serving inference ([ADR 0004](adr/0004-provider-abstraction-via-python-protocol.md))
3. **Observable:** every request produces a trace, and the system distinguishes benchmarking from live monitoring ([ADR 0009](adr/0009-monitoring-distinct-from-benchmarking.md))

---

## Pipeline flow

```text
[User / Eval Runner]
        │
        ▼
[Input Validation]        ── is the input non-empty and within length bounds?
        │
        ▼
[Guardrail Check]         ── screen for injection patterns, PII, structural anomalies
  │         │                  (ADR 0008)
  │      [BLOCK]  ───────► [TriageFailure: guardrail_blocked]
  │
  ▼ (pass or warn)
[Prompt Builder]          ── select prompt version, construct system + user prompt
        │                    with structural separation (delimiters around ticket body)
        ▼
[Provider Router]         ── select active LlmProvider instance
        │                    (ADR 0004)
        ▼
[LLM Inference]           ── call Ollama via openai client
        │
        ▼
[JSON Parse]              ── does the raw output parse as JSON?
  │         │
  │      [FAIL] ──► [Retry with repair prompt (max 1)]
  │                        │
  │                     [FAIL] ──► [TriageFailure: parse_failure]
  │
  ▼ (parsed)
[Schema Validation]       ── does it conform to TriageOutput pydantic model?
  │         │
  │      [FAIL] ──► [Retry with repair prompt (max 1)]
  │                        │
  │                     [FAIL] ──► [TriageFailure: schema_failure]
  │
  ▼ (schema valid)
[Semantic Checks]         ── are cross-field constraints satisfied?
  │         │
  │      [FAIL] ──► [Retry with repair prompt (max 1)]
  │                        │
  │                     [FAIL] ──► [TriageFailure: semantic_failure]
  │
  ▼ (all checks pass)
[TriageSuccess]           ── validated output ready for consumer
        │
        ▼
[Trace Store]             ── record trace to SQLite (ADR 0005)
        │
        ▼
[Consumer]                ── Triage tab displays result
                             Metrics tab queries traces
                             Traces tab shows individual requests
```

**Key properties of the flow:**

- The pipeline has exactly one retry point. If any validation layer fails, the *entire* validation sequence restarts with a repair prompt. The retry count is recorded in the trace.
- On any unrecoverable failure, the pipeline returns a typed `TriageFailure` with a specific category ([ADR 0003](adr/0003-pipeline-failure-handling-and-error-contract.md)). It never returns malformed data and never raises uncaught exceptions.
- The guardrail and validation layers are independent. The guardrail screens *input* before the model sees it. Validation screens *output* after the model produces it. They catch different failure modes and are measured separately.

---

## Component responsibilities

### Entry points

| Component | Responsibility |
|---|---|
| `app.py` | FastAPI + Gradio entry point. FastAPI is the outer app; Gradio is mounted as a sub-application. Wires API routes and UI tabs to the shared service layer. ([ADR 0006](adr/0006-single-app-gradio-architecture.md) + addendum) |
| `eval/runners/*.py` | Eval runner entry points. Import service layer directly, no Gradio or FastAPI dependency. |

### API layer

The system exposes a REST API via FastAPI alongside the Gradio UI, in the same process:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/triage` | POST | Submit a ticket for triage. Accepts ticket body, optional model and prompt version. Returns `TriageResult`. |
| `/api/v1/docs` | GET | Swagger UI — interactive API documentation auto-generated from pydantic models |
| `/` | GET | Gradio UI (mounted as sub-application) |

The API and the UI call the same service layer. There is no logic duplication. The API exists to satisfy the rubric's "accessible via an API endpoint" requirement and to provide Swagger documentation for programmatic consumers.

### Sampling configuration

The pipeline uses conservative sampling parameters optimized for structured JSON output:

| Parameter | Value | Rationale |
|---|---|---|
| Temperature | 0.1–0.3 | Low temperature maximizes JSON validity. Near-zero avoids greedy decoding's complete lack of variation. |
| Top-p | 0.85–0.9 | Excludes low-probability tokens that could break JSON structure |
| Top-k | 40 | Standard default; limits vocabulary to the 40 most probable tokens |
| Repetition penalty | 1.0 (disabled) | JSON output legitimately repeats field names and structural tokens |

These parameters are passed to the Ollama provider as request-level settings and are configurable via app configuration. The rationale: structured JSON output requires the model to be predictable. Every "creative" token choice is a potential validation failure.

If time permits, sampling parameters can be added as an experimental variable in the eval harness to test whether different settings measurably affect JSON validity or task accuracy.

### UI layer (`ui/`)

| Component | Responsibility |
|---|---|
| `triage_tab.py` | Ticket input form, model selector, result display, validation status, trace summary |
| `metrics_tab.py` | Benchmark Results section + Live Metrics section with time-series views and alerting ([ADR 0009](adr/0009-monitoring-distinct-from-benchmarking.md)) |
| `traces_tab.py` | Recent trace list with filtering by provider, prompt version, validation status |
| `experiments_tab.py` | Side-by-side experiment comparison views |

UI modules have no business logic. They call service methods and render results.

### Service layer (`services/`)

| Component | Responsibility |
|---|---|
| `triage.py` | Orchestrates the full pipeline: guardrail → prompt → provider → validate → retry → trace |
| `prompt.py` | Prompt building and version selection. Manages system prompt, user content wrapping, and repair prompt. |
| `guardrail.py` | Pre-LLM input screening. Returns `pass`, `warn`, or `block` with matched rules. ([ADR 0008](adr/0008-heuristic-only-guardrail-baseline.md)) |
| `validation.py` | JSON parsing, pydantic schema validation, semantic cross-field checks |
| `retry.py` | Bounded retry policy (max 1). Constructs repair prompt from failed output and error. ([ADR 0002](adr/0002-validator-first-pipeline-with-bounded-retry.md)) |
| `trace.py` | Trace recording and retrieval via the trace repository |
| `metrics.py` | Computes aggregate metrics from traces — benchmark summaries and live rolling metrics |
| `provider_router.py` | Maintains registry of available `LlmProvider` instances, selects active provider |

Services are pure Python with no Gradio dependencies. They can be called from the UI layer, the eval runners, or tests.

### Provider layer (`providers/`)

| Component | Responsibility |
|---|---|
| `base.py` | `LlmProvider` Protocol definition ([ADR 0004](adr/0004-provider-abstraction-via-python-protocol.md)) |
| `ollama_qwen.py` | Concrete provider for local Ollama. Parameterized by model name at construction. Uses `openai` client pointed at `http://localhost:11434/v1`. |
| `cloud_qwen.py` | Placeholder for future cloud provider. Raises `NotImplementedError`. |

### Schema layer (`schemas/`)

| Component | Responsibility |
|---|---|
| `triage_input.py` | `TriageInput` pydantic model — what goes into the pipeline |
| `triage_output.py` | `TriageOutput` pydantic model — the structured triage result with all fields |
| `trace.py` | `TraceRecord`, `TriageSuccess`, `TriageFailure`, `TriageResult` pydantic models ([ADR 0003](adr/0003-pipeline-failure-handling-and-error-contract.md)) |

### Storage layer (`storage/`)

| Component | Responsibility |
|---|---|
| `db.py` | SQLite connection management and schema creation ([ADR 0005](adr/0005-sqlite-trace-storage-with-repository-pattern.md)) |
| `trace_repo.py` | Single repository. All SQL is encapsulated here. Exposes typed methods to the service layer. |

### Prompt layer (`prompts/`)

| Component | Responsibility |
|---|---|
| `triage_v1.py` | Triage system prompt, version 1 |
| `repair_json_v1.py` | Repair prompt used on retry — includes the failed output and the validation error |

*Note: `triage_v2.py` was originally planned for Phase 6 but Phase 6 was scoped out — see decision log 2026-04-19. `services/prompt.py` dispatches on `"v1"` and `"__repair__"` only.*

### Eval layer (`eval/`)

| Component | Responsibility |
|---|---|
| `datasets/gold_tickets.json` | Normal labeled ticket set |
| `datasets/adversarial_tickets.json` | Adversarial ticket set with attack categories and expected behaviors |
| `runners/run_local_comparison.py` | Experiment 1: size comparison |
| `runners/run_validation_impact.py` | Experiments 2 and 3: controls interaction and validation on/off |
| `runners/run_prompt_comparison.py` | Experiment 4: prompt v1 vs v2 |
| `runners/summarize_results.py` | Compute and display aggregate metrics from stored traces |

---

## Data model

### TriageOutput (the structured triage result)

| Field | Type | Description |
|---|---|---|
| `category` | Literal enum | billing, outage, account_access, bug, feature_request, other |
| `severity` | Literal enum | low, medium, high, critical |
| `routing_team` | Literal enum | support, billing, infra, product, security |
| `business_impact` | str | Free-text assessment of business impact |
| `summary` | str | Concise summary of the ticket |
| `draft_reply` | str | Suggested response to the customer |
| `confidence` | float (0–1) | Model's self-assessed confidence |
| `escalation` | bool | Whether the ticket should be escalated |

### Semantic constraints (cross-field validation)

- If `severity == "critical"`, then `escalation` must be `true`
- If `routing_team == "security"`, then `severity` must be `"high"` or `"critical"`
- If `confidence > 0.95`, log a warning (high-confidence overconfidence is a known LLM failure mode)

This set is initial and may grow as adversarial evaluation reveals new failure patterns.

### TraceRecord (per-request event log)

See the pydantic model definition in PLAN.md. Key fields: `request_id`, `run_id` (nullable — present only for eval runner traces), `model`, `provider`, `prompt_version`, `guardrail_result`, `validation_status`, `retry_count`, `latency_ms`, token counts, `failure_category` (if applicable), `timestamp`.

Traces are the single source of truth for all metrics. Summaries are computed from traces, never stored separately. See [ADR 0005](adr/0005-sqlite-trace-storage-with-repository-pattern.md).

---

## Deployment architecture

The system runs locally on consumer hardware. The Gradio app runs in a Docker container; Ollama runs natively on the host to preserve GPU/MLX acceleration. See [ADR 0007](adr/0007-local-deployment-with-docker.md) for the full reasoning.

```text
┌─────────────────────────────────┐
│         Host machine            │
│                                 │
│  ┌───────────┐  ┌────────────┐  │
│  │  Ollama   │  │  Docker    │  │
│  │  (native) │◄─┤  container │  │
│  │  :11434   │  │  (Gradio)  │  │
│  │           │  │  :7860     │  │
│  └───────────┘  └────────────┘  │
│                                 │
│  SQLite DB mounted as volume    │
└─────────────────────────────────┘
```
