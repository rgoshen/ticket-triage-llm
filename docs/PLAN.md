# Ticket Triage LLM — Project Plan

## Project Overview

**Title:** Production-Style Support Ticket Triage with Local-First LLM Evaluation and Prompt Injection Defense

**Core Function:** Converts raw support tickets into structured triage output (category, severity, routing team, summary, escalation flag, confidence, draft response) through a validator-first pipeline with provider abstraction, a built-in benchmark dashboard, and an explicit threat model for prompt injection in user-submitted content.

**Presentation:** 5 min presentation, 5 min demo, 5 min Q&A

**Hardware:** MacBook Pro M4 Pro, 24GB unified memory (Apple Silicon)

**Primary Goal:** Demonstrate production engineering judgment under multiple competing constraints — task quality, structured-output reliability, prompt injection resistance, hardware fit, cost, and operational risk — and show the *process* of weighing those factors as the central deliverable, not just the final answer.

---

## Project Thesis

This project is not "a chatbot for support." It is a **production-style LLM inference pipeline** for support ticket triage with:

- structured output,
- schema validation,
- bounded retries,
- guardrails (with explicit attention to prompt injection),
- provider abstraction,
- evaluation across model variants,
- and a UI dashboard for benchmark and trace visibility.

The core argument of the project is:

> LLM usefulness in production comes from the surrounding engineering controls as much as from the model itself — and in a system where user-submitted content is by definition untrusted, those controls have to extend to a real, measurable threat model for prompt injection.

The project is structured to test that argument empirically. Each of the planned experiments is a probe at one part of it:

- **Model size comparison** asks: how much does raw model capability buy you?
- **Model size vs engineering controls interaction** asks: can a smaller model with strong controls match a larger model without them?
- **Validation on/off comparison** asks: how much do engineering controls buy you?
- **Prompt v1/v2 comparison** asks: how much does prompt design buy you? *(Scoped out — Phase 6 skipped per decision log 2026-04-19. E4 ships with v1 only; reliability saturation across all three models left the question narrower than the phase was designed to measure.)*

Together, the experiments produce a defensible answer to *where the value actually comes from* in this kind of system, on this kind of hardware, for this kind of task.

---

## Use Case

The system takes a raw support ticket and returns a validated triage object:

- `category`
- `severity`
- `routingTeam`
- `businessImpact`
- `summary`
- `draftReply`
- `confidence`
- `escalation`

Example categories:

- billing
- outage
- account_access
- bug
- feature_request
- other

Example routing teams:

- support
- billing
- infra
- product
- security

---

## Model Strategy

### Primary Family

Use the **Qwen 3.5** family as the main model family because it supports:

- local execution via Ollama with 256K context windows across all sizes,
- cloud variants available in the same family for future expansion (deferred for this iteration — see OD-2),
- strong instruction following and structured/JSON-oriented output behavior,
- native tool calling and "thinking" modes, available in all sizes,
- and Apache 2.0 licensing, suitable for any deployment context.

The choice of 3.5 over 3.0 is documented in the [decision log](decisions/decision-log.md): the 3.5 sub-10B variants deliver better structured-output quality and instruction following at the parameter sizes that fit on consumer hardware, with no licensing tradeoff.

### Recommended Comparison

The plan is to compare three local Qwen 3.5 sizes within the same family. This lets the comparison isolate model size as the primary variable without the confound of mixing model families. The provider abstraction supports adding a cloud variant later without pipeline changes.

#### Local models (planned)

- **Qwen 3.5 2B** — fast baseline, also serves as the stress-test for the validator-first pipeline (small models produce malformed JSON more often, which is where retry logic earns its keep)
- **Qwen 3.5 4B** — middle data point
- **Qwen 3.5 9B** — likely best balance candidate

The 2B is included even though it may produce lower task quality, because the experiment is about *characterizing how quality changes with size*, not just identifying the best model. A wide range produces a more interesting curve than a narrow one. If the 2B turns out to be unable to follow the structured-output format at all (verified in the Phase 0 smoke test described below), it will be dropped from the main comparison and that exclusion will be documented.

#### Cloud model

Cloud comparison is **deferred to future work** for this iteration. The `LlmProvider` Protocol and the `cloud_qwen.py` placeholder remain in the codebase so that a cloud provider can be added without refactoring, but no cloud model will be integrated, benchmarked, or demoed in the current build. See [decision log](decisions/decision-log.md), OD-2.

#### Models excluded by design

- **Qwen 3.5 27B** — exceeds the consumer-hardware RAM budget for comfortable use on 24GB unified memory. The Q4 weights are roughly 17GB, which leaves no headroom for macOS, the development environment, the Gradio app, and the Ollama runtime to coexist. The 27B is not MLX-accelerated in current Ollama releases either, so it would also be slow on the GGML backend. Deliberate exclusion under the consumer-hardware constraint.
- **Qwen 3.5 35B-A3B and larger** — require 32GB+ unified memory. Outside the project's hardware envelope.

### Why this comparison is strong

It lets the project compare:

- model size vs quality (across 2B / 4B / 9B),
- speed vs accuracy tradeoffs on consumer hardware,
- and practical engineering tradeoffs without adding extra-family confounds.

A cloud comparison variant can be added later via the provider abstraction without any pipeline changes.

### Phase 0 smoke test (decision point)

Before any pipeline code is written, the planned models will be smoke-tested on the actual target hardware to confirm three things:

1. Each model can be pulled via Ollama and runs on the available unified memory
2. Each model can produce roughly-valid structured output for 2–3 sample tickets with a single triage prompt
3. Whether MLX acceleration is engaged for any of the chosen sizes in the installed Ollama version (`OLLAMA_MLX=1` and `--verbose` timing)

Models that fail step 2 are excluded from the main comparison with a documented rationale. This is treated as more defensible than excluding them a priori.

---

## Expected Hardware Fit

For the **MacBook Pro M4 Pro, 24GB unified memory**:

| Model       |  Quant | Approx RAM | Expected Role                                  |
| ----------- | -----: | ---------: | ---------------------------------------------- |
| Qwen 3.5 2B | Q8_0   |     ~2.7GB | Fast baseline / validator-pipeline stress test |
| Qwen 3.5 4B | Q4_K_M |     ~3.3GB | Middle data point                              |
| Qwen 3.5 9B | Q4_K_M |     ~6.6GB | Likely best-balance candidate                  |

The 9B leaves comfortable headroom on a 24GB machine for the OS, the dev environment, Gradio, and the Ollama runtime to run concurrently, including during demo conditions.

### MLX acceleration

Ollama 0.20.x has been rolling out MLX (Apple's machine learning framework) acceleration for selected Qwen 3.5 model architectures on Apple Silicon. As of the time of writing, MLX coverage in Ollama is still being expanded one architecture at a time, and the exact set of MLX-supported Qwen 3.5 sizes in any given Ollama release is best confirmed empirically rather than from documentation. The Phase 0 smoke test will check whether MLX is engaged for the planned sizes via `OLLAMA_MLX=1` and `--verbose` timing output.

If MLX acceleration is engaged for the smaller Qwen 3.5 sizes in the installed Ollama version, latency numbers will be meaningfully better than they would be on the older Metal-only backend. This is treated as a pleasant possibility, not as a planning assumption.

### Ollama commands

```bash
ollama pull qwen3.5:2b
ollama pull qwen3.5:4b
ollama pull qwen3.5:9b
```

---

## System Architecture

The full architecture — pipeline flow, component responsibilities, data model, and deployment diagram — is documented in [architecture.md](architecture.md).

The core design idea: the business workflow is independent of the model host. Only the provider changes; the rest of the pipeline stays the same. All model output is treated as untrusted until validated. Every request produces a trace. See the ADRs for the reasoning behind each architectural choice: [ADR index](adr/README.md).

---

## Key Engineering Decisions

Each key architectural decision is captured in its own ADR with full context, options considered, rationale, tradeoffs, and consequences. See the [ADR index](adr/README.md) for the complete list.

Summary of the decisions and where to find them:

| Decision                                                                    | ADR                                                                  |
| --------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Python + Gradio + uv/pytest/ruff stack                                      | [ADR 0001](adr/0001-language-and-stack.md)                           |
| Validator-first pipeline with bounded retry, pydantic for schema validation | [ADR 0002](adr/0002-validator-first-pipeline-with-bounded-retry.md)  |
| Typed two-state error contract (TriageSuccess / TriageFailure)              | [ADR 0003](adr/0003-pipeline-failure-handling-and-error-contract.md) |
| Provider abstraction via Python Protocol                                    | [ADR 0004](adr/0004-provider-abstraction-via-python-protocol.md)     |
| SQLite for trace storage, single table, repository pattern                  | [ADR 0005](adr/0005-sqlite-trace-storage-with-repository-pattern.md) |
| Single-app Gradio architecture with tabbed layout                           | [ADR 0006](adr/0006-single-app-gradio-architecture.md)               |
| Local-only deployment with Docker for app, Ollama on host                   | [ADR 0007](adr/0007-local-deployment-with-docker.md)                 |
| Heuristic-only guardrail as baseline                                        | [ADR 0008](adr/0008-heuristic-only-guardrail-baseline.md)            |
| Monitoring distinct from benchmarking, with drift detection and alerting    | [ADR 0009](adr/0009-monitoring-distinct-from-benchmarking.md)        |

The prompt injection defense strategy — three defensive layers, what each catches and misses, and the residual risk — is documented in [threat-model.md](threat-model.md).

---

## Deployment

The system is deployed locally on consumer hardware, with two supported paths: native (`uv run`) and containerized (Docker for the Gradio app, Ollama on the host). Ollama runs outside the container to preserve GPU/MLX acceleration on Apple Silicon. Cross-platform testing is performed on macOS, Windows, and Linux.

Full deployment architecture, rationale for the Ollama-on-host split, and cross-platform testing plan: [ADR 0007](adr/0007-local-deployment-with-docker.md). Runtime instructions: [`docs/DEPLOYMENT.md`](DEPLOYMENT.md).

---

## Monitoring

The Metrics tab distinguishes **benchmarking** (static results from labeled eval runs) from **monitoring** (rolling metrics from live traffic). Live monitoring includes latency trends, error rate trends, category distribution as a drift indicator, and log-based alerting when configured thresholds are crossed.

Full monitoring design, alerting thresholds, drift detection approach, and what's intentionally out of scope: [ADR 0009](adr/0009-monitoring-distinct-from-benchmarking.md).

---

## API Endpoint

The rubric requires the model to be "accessible via an API endpoint." To satisfy this, a minimal FastAPI layer is added alongside Gradio in the same process. FastAPI is the outer app; Gradio is mounted inside it as a sub-application. One route (`POST /api/v1/triage`) calls the same service layer the Gradio Triage tab calls. Swagger UI is auto-generated at `/docs` from existing pydantic models.

This does not create a client/server split — it's one process, one codebase, one Docker container. The instructor can open `/docs` in a browser and submit a triage request via Swagger without using the Gradio UI.

Full reasoning for this addition: see the addendum to [ADR 0006](adr/0006-single-app-gradio-architecture.md). Decision log entry: [2026-04-15 — API endpoint](decisions/decision-log.md).

---

## Sampling Configuration

The pipeline uses pinned sampling parameters optimized for structured JSON output: temperature **0.2**, top-p **0.9**, top-k **40**, and repetition penalty **1.0** (disabled). These are module-level constants in `config.py`, not environment-configurable — drifting sampling values silently invalidates prior experiment results. Any change requires a decision-log entry. The rationale: structured JSON output requires the model to be predictable; every "creative" token choice is a potential validation failure.

Full configuration table and rationale: [architecture.md](architecture.md) (Sampling Configuration section). Decision log entry: [2026-04-15 — Sampling configuration](decisions/decision-log.md).

---

## Provider Interface

The provider abstraction is defined as a Python `Protocol` so that any class implementing the protocol can be used interchangeably without explicit inheritance. For this iteration, only the local Ollama provider is implemented. A `cloud_qwen.py` placeholder exists in the codebase so that a cloud provider can be added later without refactoring the pipeline.

```python
from typing import Protocol
from .schemas import ModelResult

class LlmProvider(Protocol):
    name: str

    def generate_structured_ticket(
        self,
        ticket_body: str,
        prompt_version: str,
    ) -> ModelResult:
        ...
```

### Implementations

- `OllamaQwenProvider` — local execution via Ollama, called through the `openai` client pointed at Ollama's OpenAI-compatible endpoint (`http://localhost:11434/v1`)
- `CloudQwenProvider` — placeholder for future cloud integration; not implemented this iteration

---

## Folder Structure

The project uses a single-app Python layout. There is no separate client and server — the Gradio UI and the backend services live in the same process and the same codebase, organized into modules.

```text
ticket-triage-llm/
├── .github/
├── .remember/
├── .adr-dir                          # adr tools config
├── README.md
├── Dockerfile                      # multi-stage app container build
├── .dockerignore
├── pyproject.toml                  # uv-managed, source of truth for deps
├── uv.lock
├── .env
├── .env.example
├── .gitignore
├── ruff.toml
├── data
│   ├── adversarial_set.jsonl
│   └── normal_set.jsonl
├── docs/
│   ├── PLAN.md                     # this document
│   ├── cost-analysis.md            # three-component cost analysis
│   ├── adr/                        # ADRs (adr-tools format)
│   │   ├── README.md
│   │   └── 0001-language-and-stack.md
│   ├── decisions/                  # scope/framing decisions (non-architectural)
│   │   └── decision-log.md         # chronological decision log
│   ├── archive/                    # original plan and rubric (reference)
│   ├── architecture.md             # written — pipeline flow, components, data model, deployment
│   ├── evaluation-plan.md          # written — datasets, metrics, experiments, reporting
│   ├── tradeoffs.md                # written — cross-cutting tradeoffs with reasoning
│   ├── threat-model.md             # written — prompt injection threat model
│   ├── DEPLOYMENT.md               # written — native and Docker quick-starts
│   ├── future-improvements.md      # written — deferred work with effort estimates
│   └── cost-analysis.md            # written — three-component cost analysis
│
├── src/
│   └── ticket_triage_llm/
│       ├── __init__.py
│       ├── app.py                  # FastAPI + Gradio entry point
│       ├── config.py               # env loading, settings
│       │
│       ├── api/                    # FastAPI route(s)
│       │   ├── __init__.py
│       │   └── triage_route.py     # POST /api/v1/triage
│       │
│       ├── ui/                     # Gradio tab definitions
│       │   ├── __init__.py
│       │   ├── triage_tab.py       # ticket input + result display
│       │   ├── metrics_tab.py      # benchmark dashboard
│       │   ├── traces_tab.py       # trace explorer
│       │   └── experiments_tab.py  # experiment comparison
│       │
│       ├── services/               # business logic
│       │   ├── __init__.py
│       │   ├── triage.py           # orchestrates the full pipeline
│       │   ├── prompt.py           # prompt building / versioning
│       │   ├── guardrail.py        # pre-LLM input screening
│       │   ├── validation.py       # parse + schema + semantic checks
│       │   ├── retry.py            # bounded retry policy
│       │   ├── trace.py            # trace recording
│       │   ├── metrics.py          # metrics aggregation
│       │   └── provider_router.py  # selects active provider
│       │
│       ├── providers/              # LLM provider implementations
│       │   ├── __init__.py
│       │   ├── base.py             # LlmProvider Protocol
│       │   ├── ollama_qwen.py      # local Ollama provider
│       │   └── cloud_qwen.py       # cloud Qwen provider (provider TBD)
│       │
│       ├── prompts/                # prompt templates by version
│       │   ├── __init__.py
│       │   ├── triage_v1.py
│       │   └── repair_json_v1.py    # (triage_v2.py not shipped — Phase 6 scoped out)
│       │
│       ├── schemas/                # pydantic models
│       │   ├── __init__.py
│       │   ├── triage_input.py
│       │   ├── triage_output.py
│       │   └── trace.py
│       │
│       ├── storage/                # SQLite + repository pattern
│       │   ├── __init__.py
│       │   ├── db.py               # connection / schema setup
│       │   └── trace_repo.py       # single repository — traces are the source of truth
│       │
│       └── eval/                   # evaluation harness
│           ├── __init__.py
│           ├── datasets.py                # dataset loader (GroundTruth, TicketRecord)
│           ├── results.py                 # ModelMetrics, ExperimentSummary
│           └── runners/
│               ├── __init__.py
│               ├── common.py              # run_experiment_pass() shared loop
│               ├── run_local_comparison.py # E1: model size comparison
│               ├── run_validation_impact.py# E3: validation on/off + E2 data
│               ├── run_prompt_comparison.py# E4: prompt comparison (v1 only)
│               ├── run_adversarial_eval.py # Phase 4: adversarial evaluation
│               └── summarize_results.py   # summarize_run(), compose_e2(), CLI
│
└── tests/
    ├── __init__.py
    ├── unit/
    │   ├── test_validation.py
    │   ├── test_guardrail.py
    │   ├── test_retry.py
    │   └── test_prompts.py
    ├── integration/
    │   ├── test_triage_pipeline.py
    │   └── test_providers.py
    └── eval/
        └── test_eval_runners.py
```

### Notes on the layout

- The `src/ticket_triage_llm/` package is the single application. There is no `client/` or `server/` split.
- `app.py` is the Gradio entry point and wires together the UI tabs and the service layer in-process.
- `services/` contains pure Python business logic with no Gradio dependencies, so it can be tested independently and reused outside the UI (e.g., from the `eval/runners/`).
- `providers/` follows the Protocol-based abstraction described above.
- `schemas/` uses `pydantic` for all input/output validation, including the structured triage output.
- `storage/` uses SQLite with a thin repository pattern. SQLite was chosen because it requires zero setup, is transaction-safe, and is more than sufficient for the project's scale (hundreds to low thousands of trace records).
- `eval/` is independent of the UI and can be invoked from the command line as a benchmark runner.

---

## UI Tabs

The Gradio app uses `gr.Blocks` with one tab per major view. All tabs share the same in-process service layer.

### 1. Triage tab

Purpose: main triage workflow. This is the primary tab and what the instructor or any user will interact with first.

Features:

- ticket input textarea (free-form, accepts unstructured text),
- sample ticket loader (preset normal and adversarial examples for demoing),
- provider/model selector (dropdown driven by available providers),
- structured result panel showing the parsed triage object,
- validation status indicator (pass / failed-and-retried / blocked-by-guardrail),
- trace summary for the current request (latency, tokens, retry count, validation result).

### 2. Metrics tab

Purpose: dashboard for benchmarks and runtime metrics, populated from stored eval runs and live request traces.

Features:

- KPI cards (best current model, average task accuracy, JSON validity rate, average latency, retry rate, estimated cost/request),
- benchmark comparison table across providers and prompt versions,
- latency chart (p50 and p95 by provider),
- JSON validity rate by provider,
- retry rate by provider,
- guardrail block/warn/pass distribution,
- cloud cost estimate (where applicable).

### 3. Traces tab

Purpose: inspect individual requests, mostly for debugging and demo evidence.

Features:

- recent run list,
- filter by provider,
- filter by prompt version,
- filter by validation status,
- inspect request/response metadata,
- inspect validation failures and which layer caught them.

### 4. Experiments tab

Purpose: compare experimental runs side by side, with the four planned experiments as the primary structure.

Features:

- **Experiment 1** — local size comparison: Qwen 3.5 2B vs 4B vs 9B
- **Experiment 2** — model size vs engineering controls: smallest model with full validation vs largest model without validation
- **Experiment 3** — validation impact: pipeline with validation/retry vs pipeline without
- **Experiment 4** — prompt comparison: triage prompt v1 only *(Phase 6 scoped out — v2 not authored)*
- exportable result summaries

---

## Dashboard Requirements

### Why dashboard output matters

Benchmarking should not end in a CSV file or terminal printout. The project should expose benchmark and observability data directly in the UI to demonstrate production thinking.

### Dashboard sections

#### KPI cards

- best current model,
- average task accuracy,
- JSON validity rate,
- average latency,
- retry rate,
- estimated cloud cost/request.

#### Benchmark table

Columns:

- model/provider,
- accuracy,
- JSON validity,
- average latency,
- p95 latency,
- retry rate,
- guardrail block rate,
- cost/request,
- notes.

#### Latency chart

Compare:

- model latency distribution,
- p50 and p95,
- local vs cloud.

#### Trace explorer

Show:

- sample/ticket id,
- provider,
- prompt version,
- latency,
- validation result,
- retry count,
- output preview.

---

## Data Flow for Dashboard

```text
eval runner -> SQLite results -> metrics service -> Metrics tab (Gradio)
live requests -> trace store -> trace service -> Traces tab (Gradio)
```

### In-process service interfaces

The project is a single-process app — FastAPI is the outer app, Gradio is mounted inside it as a sub-application (see ADR 0006 addendum). The REST API (`POST /api/v1/triage`) and the UI tabs both call the same Python service modules:

#### `triage_service.run_triage(ticket_body, provider, prompt_version)`

Runs live triage inference and stores the trace.

#### `metrics_service.get_aggregate_metrics(filters)`

Returns aggregate benchmark and runtime metrics for the Metrics tab.

#### `trace_service.list_recent_traces(filters)`

Returns recent request traces for the Traces tab.

#### `metrics_service.get_experiment_summaries()`

Returns experiment summaries and comparison results for the Experiments tab.

---

## Schemas and Data Model

The `TraceRecord`, `TriageOutput`, `TriageSuccess`, `TriageFailure`, and `TriageResult` pydantic models are defined in [architecture.md](architecture.md) (data model section) and implemented in `src/ticket_triage_llm/schemas/`. The trace record is the single source of truth for all metrics — summaries are computed from traces, never stored separately ([ADR 0005](adr/0005-sqlite-trace-storage-with-repository-pattern.md)).

---

## Evaluation Plan

The full evaluation plan — datasets, metrics, experiments, prompt injection sub-evaluation, execution process, and reporting approach — is in [evaluation-plan.md](evaluation-plan.md).

Summary of the four experiments:

1. **Model size comparison** — Qwen 3.5 2B vs 4B vs 9B: how does quality scale with size on consumer hardware?
2. **Model size vs engineering controls** — smallest model with full validation vs largest model without: can controls compensate for model size?
3. **Validation impact** — full pipeline vs no validation on same model: what do engineering controls actually buy?
4. **Prompt comparison** — prompt v1 only on same model *(Phase 6 scoped out per decision log 2026-04-19; v2 deferred because reliability saturated at 100% JSON validity across all three models under production config, leaving only a 2.8pp category-accuracy headroom for v2 to measure)*.

Plus a **prompt injection sub-evaluation** measuring per-layer effectiveness across attack categories. See [threat-model.md](threat-model.md) for the defensive layer design and residual risk framing.

Cost analysis methodology is in [cost-analysis.md](cost-analysis.md).

### Expected Benchmark Table

> Numbers are **placeholders** until Phase 3 produces real data. The shape of the table is what matters at the planning stage.

| Model       | Accuracy | JSON Valid | Latency | Tokens/s | Tokens/req | Retries | Cost/req |
| ----------- | -------- | ---------- | ------- | -------- | ---------- | ------- | -------- |
| Qwen 3.5 2B | TBD      | TBD        | TBD     | TBD      | TBD        | TBD     | $0       |
| Qwen 3.5 4B | TBD      | TBD        | TBD     | TBD      | TBD        | TBD     | $0       |
| Qwen 3.5 9B | TBD      | TBD        | TBD     | TBD      | TBD        | TBD     | $0       |

---

## Five-Minute Presentation Plan

Keep the live presentation to **6 slides max**.

### Slide 1: Problem + goal

- raw support tickets are messy,
- goal: structured triage with reliability controls.

### Slide 2: Architecture

- show the pipeline,
- emphasize provider abstraction and validator-first design.

### Slide 3: Model evaluation

- Qwen local size comparison,
- optional cloud baseline,
- key tradeoff table.

### Slide 4: Engineering decisions

- structured JSON,
- validation + bounded retry,
- dashboard + tracing.

### Slide 5: Failure handling

- one adversarial or malformed case,
- show guardrail or retry recovery.

### Slide 6: Takeaway

- best model is the best tradeoff, not just the largest,
- engineering controls matter.

---

## Five-Minute Demo Plan

### Step 1: Happy path

- submit a normal support ticket,
- run with the chosen default local Qwen 3.5 model,
- show structured output and trace panel.

### Step 2: Model switch

- switch to a different local size (e.g., 4B → 9B),
- show differences in latency, output quality, and JSON validity.

### Step 3: Failure case — adversarial input

- run a prompt-injection ticket from the adversarial set (ideally the indirect-via-quoted-content variant, which is the most interesting story to tell),
- show whether the guardrail blocked it, the model handled it correctly, the validation layer caught a corrupted output, or the injection succeeded end-to-end,
- be honest about which case occurred. The demo is more credible if at least one attack succeeds and the writeup acknowledges it as documented residual risk.

### Step 4: Metrics dashboard

- open the Metrics tab,
- show benchmark table across models,
- show latency chart,
- walk through the model selection decision and the factors that weighed into it.

---

## Build Plan (Phased)

The build is organized as a sequence of phases. Each phase is a coherent slice of work that can be checkpointed before moving on. Phases are intentionally not labeled with days because the build window is variable; what matters is that each phase produces a working, demo-able state of the system.

### Phase 0: Smoke test and baseline (must come first)

Before any code is written:

- pull Qwen 3.5 2B, 4B, and 9B via Ollama,
- verify each model loads and runs on the target hardware,
- send 2–3 sample tickets through each model with a single throwaway triage prompt to confirm structured output is at least possible,
- check whether MLX acceleration is engaged in the installed Ollama version (`OLLAMA_MLX=1` and `--verbose`),
- decide whether 2B stays in the comparison or is dropped with a documented reason,
- make the first eval-driven entry in the decision log.

The output of this phase is *empirical input* to all later decisions, not just a sanity check.

### Phase 1: Single happy-path slice

- create the Python project skeleton (`uv init`, package layout, `pyproject.toml`, `ruff` config, `pytest` config)
- pydantic schemas for `TriageInput`, `TriageOutput`, `TraceRecord`
- `OllamaQwenProvider` against one model (the most likely default from Phase 0)
- `triage_service.run_triage()` end-to-end: prompt builder → provider → JSON parse → schema validation
- one Gradio tab (Triage tab) that accepts a ticket and shows the structured result
- minimal SQLite trace storage
- one happy-path test, one failed-parse test
- basic `Dockerfile` for the Gradio app (Ollama runs on host, container connects via `host.docker.internal:11434` on Mac/Windows or host network on Linux)
- `.dockerignore`
- verify the container builds and runs locally on Mac

Output: a single working slice end-to-end. One model, one prompt, one tab. Demo-able both natively and via Docker.

### Phase 2: Provider abstraction and second/third local models

- extract `LlmProvider` Protocol and refactor the existing provider to implement it
- add the remaining local models behind the same interface
- `provider_router` service to switch between them based on UI selection
- model selector dropdown in the Triage tab
- bounded retry policy (max 1) wired into the validation pipeline
- guardrail service stub (initial pass, just checks for obvious injection patterns and oversized inputs)

Output: pipeline supports all local models with one-click switching. Retry logic in place. Initial guardrail in place.

### Phase 3: Evaluation harness and labeled datasets

- build the `gold_tickets.json` normal labeled set (35 tickets, including non-actionable and ambiguous-severity edge cases)
- build the `adversarial_tickets.json` adversarial set (14 tickets, organized by attack category)
- write the eval runners for each of the four experiments
- run each experiment, store results to SQLite
- generate the first real benchmark table (replacing the placeholder TBDs in this document)

Output: the project's central evidence base. Real numbers replace illustrative ones.

### Phase 4: Prompt injection hardening and adversarial evaluation

- run the adversarial set against all local models
- measure per-layer mitigation effectiveness (guardrail block rate, model bypass rate, output validation catch rate, residual risk)
- iterate on the guardrail implementation based on what the adversarial results reveal
- document findings in the threat model

### Phase 5: Dashboard, traces, and live monitoring

The Metrics tab is split into two distinct sections to reflect the difference between benchmarking and monitoring:

**Benchmark Results section** (static, from labeled eval runs):
- KPI cards for the latest benchmark run (best model, accuracy, JSON validity, p95 latency, retry rate)
- Per-experiment comparison tables (size comparison, validation impact, prompt comparison, model-vs-controls)
- Charts populated from the SQLite eval results

**Live Metrics section** (rolling, from live trace traffic):
- Time-series view of recent latency (p50 and p95) over configurable windows (last hour, last day, last week)
- Time-series view of error rate (validation failures and retry rate) over the same windows
- Category distribution over time as a basic drift indicator — if the distribution of assigned categories shifts meaningfully, something has changed (input distribution, model behavior, or both)
- Alerting thresholds with structured log warnings when configured limits are crossed (e.g., p95 latency > 5s, retry rate > 20%, single category exceeds 70% of recent traffic)

**Other UI work in this phase:**
- Traces tab with filtering by provider, prompt version, validation status
- Experiments tab showing side-by-side comparison views for the four experiments

Output: the project is fully observable from the UI. Static benchmark results and live monitoring are clearly distinguished. Someone watching the system would know when something is going wrong without having to dig through logs.

Much of this phase can be parallelized — the coding agent can build the time-series queries and chart rendering while the developer authors documentation or runs additional eval batches.

### Phase 6: Prompt v2 and prompt comparison *(SCOPED OUT — see decision log 2026-04-19)*

~~author triage prompt v2 (a meaningfully different version, not just a tweak)~~
~~run Experiment 4~~
~~update the dashboards to support prompt-version filtering~~

**Status: not executed.** Phase 3 replication showed all three models achieve 100% JSON validity under production config, leaving only a 2.8pp category-accuracy headroom for v2 to measure. The phase's original motivation (reliability + accuracy headroom) no longer applies. E4 is declared complete with v1 only. v2 remains an item in `docs/future-improvements.md` if category accuracy becomes the bottleneck in a later iteration.

### Phase 7: Hardening, documentation, and presentation prep

- document a-009 and other adversarial findings as known limitations (guardrail sweep not attempted — preserves ADR 0008 baseline)
- write `architecture.md`, `evaluation-plan.md`, `tradeoffs.md`, `threat-model.md` *(`prompt-versions.md` not authored — Phase 6 scoped out)*
- write `DEPLOYMENT.md` with native and Docker quick-starts, architecture note explaining Ollama-on-host design, and troubleshooting section
- add README "Managing models" section covering add/remove/change default + cloud-via-Ollama-passthrough
- fill in `cost-analysis.md` TBDs with Phase 3 measured values
- test the Docker setup on Windows and on the work laptop (Linux) — **cross-platform testing deferred to a follow-up branch**
- finalize ADRs via addenda based on what was actually decided during the build
- author the presentation slides + demo script
- rehearse the demo end-to-end (twice)

Output: complete deliverable. Everything ready for presentation day, deployable on macOS (primary) with Docker; cross-platform validation pending.

### Phase order, not phase duration

Phases are ordered so that the system is *demo-able after every phase from Phase 1 onward*. If the build runs out of time at any phase, what exists is still a coherent project, just with fewer experiments or thinner documentation. Nothing in this plan requires the project to be "done" before any of it is presentable.

---

## Final Recommendation

Build the system around **Qwen 3.5 local-first evaluation with prompt-injection-aware guardrails and dashboard-backed observability**.

Minimum viable strong version:

- Qwen 3.5 local at three sizes (subject to Phase 0 smoke test, default plan: 2B / 4B / 9B)
- validator-first pipeline with bounded retry
- guardrail layer with explicit attention to prompt injection
- 35 labeled normal tickets (including non-actionable and ambiguous-severity edge cases) + 14 labeled adversarial tickets
- four experiments (size, size-vs-controls interaction, validation-on/off, prompt-v1 — v2 comparison scoped out per decision log)
- prompt injection sub-evaluation across attack categories
- built-in metrics dashboard and trace explorer
- 6-slide presentation framed around the central engineering question, not the feature list

Optional stretch:

- add a cloud Qwen variant via the provider abstraction (requires API key and integration work)
- if Phase 0 reveals that the 2B is genuinely usable, the size comparison curve is more informative
- document `future-improvements.md` covering the things explicitly out of scope (cloud comparison, multimodal injection defense, LoRA fine-tuning on ticket data, role-based access, vision input)

This version matches the available hardware, the constraints we have chosen to honor, and the rubric's emphasis on engineering judgment, evaluation rigor, and decision-making.

---

## Open Decisions

This section tracked decisions that were open during the build. All have been resolved — see links to the decision log and ADRs in each entry.

### ~~OD-1: Why Qwen 3.5 specifically (over Qwen 3.0)?~~ — RESOLVED

Resolved 2026-04-14. See [decision log](decisions/decision-log.md). Summary: Qwen 3.5's sub-10B variants deliver better structured-output quality and instruction following than their 3.0 equivalents at the same parameter count, which is the tier that fits on the project's consumer hardware. No licensing tradeoff (Apache 2.0). Vision/long-context features are available but unused and cost nothing.

### ~~OD-2: Cloud provider for the within-family comparison~~ — RESOLVED

Resolved 2026-04-14. See [decision log](decisions/decision-log.md). Summary: cloud comparison deferred to future work. The project is local-only for this iteration. The `LlmProvider` Protocol remains in the design so a cloud provider can be added without refactoring.

### ~~OD-3: Final local model lineup~~ — RESOLVED

Resolved 2026-04-14. See [decision log](decisions/decision-log.md). Summary: 2B / 4B / 9B, all three included pending Phase 0 verification. No a-priori exclusions — if a model can't produce structured output, the exclusion will be documented with evidence from the smoke test rather than assumed in advance.

### ~~OD-4: Default model for the demo~~ — RESOLVED

Resolved 2026-04-18, **re-resolved 2026-04-19**. See [decision log](decisions/decision-log.md) and [ADR 0011](adr/0011-default-model-selection.md). The original n=1 decision selected the 4B (ADR 0011). The Phase 3 replication (n=5, `think=false`, `num_ctx=16384`) reversed the finding: the 9B leads on category accuracy (83.4% vs 80.6%) with all three models at 100% JSON validity. **The current default is Qwen 3.5 9B.** ADR 0011 is historical; the decision-log entry dated 2026-04-19 supersedes it.

### ~~OD-5: Cost analysis depth~~ — RESOLVED

Resolved 2026-04-14. See [decision log](decisions/decision-log.md). Summary: three components — (1) local compute resource cost per model (RAM, GPU, latency, disk), (2) hardware acquisition cost amortized over useful life, (3) hypothetical cloud comparison using published Qwen API pricing and actual token counts from the benchmarks, with a break-even calculation at projected daily volumes. Written up in `docs/cost-analysis.md` after Phase 3.

### ~~OD-6: Guardrail implementation depth~~ — RESOLVED

Resolved 2026-04-14. See [decision log](decisions/decision-log.md). Summary: heuristic-only baseline (pattern matching for known injection phrases, structural markers, length extremes, PII patterns). The heuristic was measured against the adversarial set in Phase 4; expected failures on obfuscated/indirect attacks are documented as findings, not defects. LLM-based second-pass classifier remains a [`future-improvements.md`](decisions/../future-improvements.md) item — not added in this project iteration.

### ~~OD-7: Adversarial set final size and exact composition~~ — RESOLVED

Resolved 2026-04-14. See [decision log](decisions/decision-log.md). Summary: seven categories, 14 tickets total. Categories and counts are locked. Ticket text authored and stored in `data/adversarial_set.jsonl`. Each ticket is labeled with attack type and expected correct pipeline behavior.

---

## Documentation Plan

Documentation is split across multiple artifact types, each with a clear purpose:

- **This document** (`docs/PLAN.md`) — the working project plan and map to all other docs
- **`docs/adr/`** — Architecture Decision Records for architectural decisions ([ADR index](adr/README.md)) — **11 ADRs written**
- **`docs/decisions/decision-log.md`** — chronological log of scope, framing, and strategy decisions — **written**
- **`docs/architecture.md`** — pipeline flow, component responsibilities, data model, deployment diagram — **written**
- **`docs/evaluation-plan.md`** — datasets, metrics, experiments, execution, reporting — **written**
- **`docs/threat-model.md`** — prompt injection threat model, attack categories, defensive layers, residual risk, measurement plan — **written**
- **`docs/tradeoffs.md`** — cross-cutting tradeoffs with reasoning — **written**
- **`docs/cost-analysis.md`** — three-component cost analysis with measured Phase 3 data — **written**
- **`docs/future-improvements.md`** — everything deliberately out of scope with reasoning and effort estimates — **written**
- **`docs/DEPLOYMENT.md`** — native and Docker quick-starts, architecture context, troubleshooting — **written**
- **`docs/SUMMARY.md`** — historical log across all phases — **written**
- **`docs/prompt-versions.md`** — not written (Phase 6 scoped out — v2 was never authored; see [decision log 2026-04-19](decisions/decision-log.md) and [`future-improvements.md`](future-improvements.md))

This split keeps the presentation short while preserving rigor in writing. PLAN.md is the map; the other docs are the territory.
