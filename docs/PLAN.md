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
- **Prompt v1/v2 comparison** asks: how much does prompt design buy you?

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

| Model | Quant | Approx RAM | Expected Role |
|---|---:|---:|---|
| Qwen 3.5 2B | Q4_K_M | ~2.7GB | Fast baseline / validator-pipeline stress test |
| Qwen 3.5 4B | Q4_K_M | ~3.3GB | Middle data point |
| Qwen 3.5 9B | Q4_K_M | ~6.6GB | Likely best-balance candidate |

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

### High-level pipeline

```text
[UI]
  -> [Input Validation]
  -> [Guardrail Check]
  -> [Prompt Builder + Prompt Version]
  -> [Provider Router]
        -> [Ollama Qwen Provider]
        -> [Cloud Qwen Provider]
  -> [LLM Output]
  -> [JSON Parse]
  -> [Schema Validation]
  -> [Semantic Checks]
  -> [Retry Service (max 1)]
  -> [Trace Store]
  -> [Metrics Store]
  -> [UI Result + Dashboard]
```

### Core design idea

The business workflow should be independent of the model host. Only the provider changes; the rest of the pipeline stays the same.

---

## Key Engineering Decisions

### 1. Structured JSON output

The model must return a fixed schema instead of free-form prose.

**Why:**

- easier to validate,
- easier to benchmark,
- easier to integrate into downstream systems.

### 2. Validator-first architecture

Treat model output as untrusted until it passes parsing and schema checks.

**Why:**

- LLMs are probabilistic,
- malformed output should not silently flow through the system,
- validation makes failure visible.

### 3. One bounded retry

Retry once only when parsing or schema validation fails.

**Why:**

- improves robustness,
- avoids hidden instability,
- keeps latency bounded.

### 4. Provider abstraction

Use a common provider interface so the same app can run local and cloud models.

**Why:**

- clean comparison framework,
- isolates infrastructure concerns,
- future-proofs deployment options.

### 5. Built-in observability dashboard

Benchmark and runtime metrics should appear in the app UI, not just in terminal logs.

**Why:**

- supports engineering analysis,
- helps demo the system,
- makes model selection and failure analysis visible.

### 6. Prompt injection defense as a load-bearing component

The guardrail and validation layers are not just hygiene — they are the project's central engineering investigation. Tickets are user-submitted by definition, which means the body of any ticket is untrusted input. The pipeline must treat the ticket body as adversarial and apply layered mitigations against direct, indirect (via quoted third-party content), and obfuscated injection attempts.

**Why:**

- prompt injection is the central unsolved problem in production LLM security right now,
- it cannot be *prevented* architecturally as long as instructions and data share a context window — it can only be *mitigated* through layered defenses,
- the only honest engineering stance is to build the mitigations, measure them on a real adversarial set, and document the residual risk,
- this is what converts the validator-first architecture from a checkbox into the spine of the project's argument.

The pipeline implements at least three layers of mitigation: (1) structural separation between system instructions and user content in the prompt, (2) a pre-LLM guardrail that screens the input for known injection patterns, and (3) post-LLM output validation that rejects responses that don't conform to the expected schema (which is itself a way of catching cases where the model was successfully redirected). The effectiveness of each layer is measured on the adversarial set described in the evaluation plan.

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
├── README.md
├── pyproject.toml                  # uv-managed, source of truth for deps
├── uv.lock
├── .env
├── .env.example
├── .gitignore
├── ruff.toml
│
├── docs/
│   ├── llm-ticket-triage-plan.md   # this document
│   ├── decision-log.md             # chronological scope/framing decisions
│   ├── decisions/                  # ADRs (adr-tools format)
│   │   ├── README.md
│   │   └── 0001-language-and-stack.md
│   ├── architecture.md             # forthcoming
│   ├── evaluation-plan.md          # forthcoming
│   ├── tradeoffs.md                # forthcoming
│   ├── prompt-versions.md          # forthcoming
│   ├── threat-model.md             # forthcoming — prompt injection threat model
│   ├── demo-script.md              # forthcoming
│   └── presentation-notes.md       # forthcoming
│
├── src/
│   └── ticket_triage_llm/
│       ├── __init__.py
│       ├── app.py                  # Gradio app entry point (gr.Blocks with tabs)
│       ├── config.py               # env loading, settings
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
│       │   ├── triage_v2.py
│       │   └── repair_json_v1.py
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
│       │   ├── trace_repo.py
│       │   ├── metrics_repo.py
│       │   └── benchmark_repo.py
│       │
│       └── eval/                   # evaluation harness
│           ├── __init__.py
│           ├── datasets/
│           │   ├── gold_tickets.json
│           │   └── adversarial_tickets.json
│           ├── runners/
│           │   ├── __init__.py
│           │   ├── run_local_comparison.py
│           │   ├── run_local_vs_cloud.py
│           │   ├── run_validation_impact.py
│           │   ├── run_prompt_comparison.py
│           │   └── summarize_results.py
│           └── reports/
│               └── (generated benchmark output)
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
- **Experiment 4** — prompt comparison: triage prompt v1 vs v2
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

Because the project is a single Gradio app rather than a split client/server, there are no HTTP endpoints. Instead, the UI tabs call into Python service modules in the same process:

#### `triage_service.run_triage(ticket_body, provider, prompt_version)`

Runs live triage inference and stores the trace.

#### `metrics_service.get_aggregate_metrics(filters)`

Returns aggregate benchmark and runtime metrics for the Metrics tab.

#### `trace_service.list_recent_traces(filters)`

Returns recent request traces for the Traces tab.

#### `metrics_service.get_experiment_summaries()`

Returns experiment summaries and comparison results for the Experiments tab.

---

## Suggested Metrics Schema

```json
{
  "provider": "qwen3.5-9b-local",
  "accuracy": 0.87,
  "json_validity_rate": 0.95,
  "avg_latency_ms": 3200,
  "p95_latency_ms": 4700,
  "retry_rate": 0.08,
  "guardrail_block_rate": 0.12,
  "estimated_cost_per_request": 0.0,
  "sample_count": 25,
  "prompt_version": "v1"
}
```

### Suggested trace schema (pydantic)

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel

class TraceRecord(BaseModel):
    request_id: str
    ticket_hash: str
    prompt_version: str
    model: str
    provider: str
    guardrail_result: Literal["pass", "warn", "block"]
    validation_status: Literal["pass", "fail"]
    semantic_check_status: Literal["pass", "fail"]
    retry_count: int
    latency_ms: int
    tokens_in: int
    tokens_out: int
    tokens_total: int
    tokens_per_sec: float
    estimated_cost: float
    timestamp: datetime
```

---

## Metrics & Benchmarking

### Per-Model Metrics

| Metric | Description |
|--------|-------------|
| Task accuracy | Category, severity, routing correctness |
| JSON validity rate | Parse + schema pass rate |
| Avg / p95 latency | Response time |
| Tokens/sec | Throughput (decoding speed) |
| Tokens used | Input, output, total per request |
| Retry rate | First-pass failure rate |
| Guardrail block rate | Block/warn/pass distribution |
| Estimated cost/request | Cloud only (from token usage) |

### Expected Benchmark Table

> The numbers below are **illustrative placeholders only**. Real values will come from the Phase 0 smoke test and the full evaluation runs. They are included here to show the *shape* of the table that will be populated, not to predict the result.

| Model | Accuracy | JSON Valid | Latency | Tokens/s | Tokens/req | Retries | Cost/req |
|-------|----------|------------|---------|----------|------------|---------|----------|
| Qwen 3.5 2B | TBD | TBD | TBD | TBD | TBD | TBD | $0 |
| Qwen 3.5 4B | TBD | TBD | TBD | TBD | TBD | TBD | $0 |
| Qwen 3.5 9B | TBD | TBD | TBD | TBD | TBD | TBD | $0 |

## Evaluation Plan

### Datasets

The evaluation uses two distinct datasets:

#### Normal labeled set

- **20–30 labeled normal tickets** representing realistic support traffic
- Each ticket labeled with ground truth for: category, severity, routing team, escalation flag
- Categories cover the full taxonomy (billing, outage, account_access, bug, feature_request, other)
- Tickets vary in length, tone, clarity, and completeness to reflect realistic input

#### Adversarial set

- **~12 adversarial tickets**, organized by attack type. The adversarial set is the central evidence base for the prompt-injection investigation.

| Category | Count (target) | What it tests |
|---|---:|---|
| Direct prompt injection | 3–4 | Explicit attempts to override the model's behavior in the ticket body |
| Direct injection with obfuscation | 2 | Base64, language switching, or invisible Unicode variants — tests whether guardrails are doing semantic checking or pattern matching |
| Indirect injection via quoted content | 2–3 | Tickets that legitimately quote third-party content (forwarded emails, error messages, log excerpts) where the malicious instructions are inside the quoted material |
| PII / data leak triggers | 1–2 | Tickets containing fake credit card numbers or other PII patterns that should trigger a guardrail |
| Hostile / abusive language | 1 | Legitimate but emotionally charged tickets, to test that the model still produces a useful triage |
| Length extremes | 1 | One very-short and one very-long ticket |
| Multilingual | 1 | A ticket in a language other than English |

Every adversarial ticket is labeled with both the attack type and the *expected correct behavior* (e.g., "guardrail should block," "model should ignore the injection and triage the underlying complaint normally," "should be routed to security with high severity").

### Core metrics

| Metric | Purpose |
|---|---|
| Category accuracy | classification quality |
| Severity accuracy | operational usefulness |
| Routing accuracy | downstream utility |
| JSON validity rate | structured-output reliability |
| Retry rate | stability signal — first-pass failure rate |
| Avg / p50 / p95 latency | operational responsiveness |
| Guardrail block success rate | safety behavior on adversarial set |
| Injection resistance rate | proportion of injection attempts that the pipeline correctly handled |
| Cost/request | cloud tradeoff |

### Experiments

The four experiments are designed as probes at the project's central question — *where does the value actually come from in a production LLM system?*

#### Experiment 1: Local model size comparison

- **Models:** Qwen 3.5 2B vs 4B vs 9B (subject to Phase 0 smoke test)
- **Question being asked:** how much does raw model size buy you on this task at this hardware tier?
- **Primary metrics:** task accuracy, JSON validity rate, latency, tokens/sec
- **Secondary observation:** which size first becomes useful at producing structured output reliably

#### Experiment 2: Model size vs engineering controls interaction

- **Configurations:** smallest viable local model WITH full validation/retry vs largest local model WITHOUT validation/retry
- **Question being asked:** can a smaller, cheaper model with strong engineering controls match or outperform a larger model running without them?
- **Primary metrics:** end-to-end task accuracy, JSON validity rate, routing correctness
- **Secondary observation:** what's the cost (in latency and retries) of compensating for model quality with engineering controls?

This experiment directly tests the project's central thesis. It replaces the originally planned local-vs-cloud comparison (deferred to future work) with a more focused probe at the same underlying question: *where does the value come from?*

#### Experiment 3: Validation impact

- **Configurations:** full pipeline (parse + schema + bounded retry) vs same pipeline with validation and retry disabled, on the same model
- **Question being asked:** how much do engineering controls buy you, independently of model choice?
- **Primary metrics:** end-to-end task accuracy with vs without validation, JSON validity rate, percentage of cases where retry recovers a failure
- **Secondary observation:** does a smaller model with strong validation outperform a larger model without validation?

This experiment is the most directly load-bearing for the project's central thesis. If the answer is "yes, validation matters more than model size in some regime," that finding alone justifies the project's framing.

#### Experiment 4: Prompt comparison

- **Configurations:** triage prompt v1 vs v2, on the same model
- **Question being asked:** how much does prompt design buy you?
- **Primary metrics:** task accuracy, JSON validity rate, retry rate
- **Secondary observation:** which fields benefit most from prompt iteration

### Prompt injection sub-evaluation

Beyond the four main experiments, the adversarial set is run separately as a focused security evaluation. For each model and each attack category, the metrics reported are:

- **Block rate** — proportion of adversarial inputs caught by the pre-LLM guardrail before the model sees them
- **Bypass rate** — proportion that reached the model
- **Successful injection rate** — proportion of bypassed inputs where the model actually followed the injected instructions
- **Recovery rate** — proportion of successful injections caught downstream by output validation (e.g., the model wrote `severity = critical` to comply with an injection but the validation layer flagged it as suspicious)
- **Residual risk** — proportion that succeeded end-to-end and produced a corrupted triage object

The honest engineering claim from this sub-evaluation is *not* "I built guardrails that stop prompt injection." It is "here are the layered mitigations I built, here's how each layer performs on a realistic adversarial set, and here's the residual risk I could not eliminate." That framing — measurement and honesty about residual risk — is the position the field currently sits in, and articulating it cleanly is itself a piece of the project's deliverable.

---

## Expected Benchmark Output Example

> Same caveat as the earlier table: numbers are **placeholders**. The shape of the table is what matters at the planning stage.

| Model | Accuracy | JSON Validity | Avg Latency | Tokens/s | RAM | Cost/Request | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| Qwen 3.5 2B local | TBD | TBD | TBD | TBD | ~2.7GB | $0.00 | fast baseline / pipeline stress test |
| Qwen 3.5 4B local | TBD | TBD | TBD | TBD | ~3.3GB | $0.00 | middle data point |
| Qwen 3.5 9B local | TBD | TBD | TBD | TBD | ~6.6GB | $0.00 | likely best balance |

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

Output: a single working slice end-to-end. One model, one prompt, one tab. Demo-able.

### Phase 2: Provider abstraction and second/third local models

- extract `LlmProvider` Protocol and refactor the existing provider to implement it
- add the remaining local models behind the same interface
- `provider_router` service to switch between them based on UI selection
- model selector dropdown in the Triage tab
- bounded retry policy (max 1) wired into the validation pipeline
- guardrail service stub (initial pass, just checks for obvious injection patterns and oversized inputs)

Output: pipeline supports all local models with one-click switching. Retry logic in place. Initial guardrail in place.

### Phase 3: Evaluation harness and labeled datasets

- build the `gold_tickets.json` normal labeled set (20–30 tickets)
- build the `adversarial_tickets.json` adversarial set (~12 tickets, organized by attack category)
- write the eval runners for each of the four experiments
- run each experiment, store results to SQLite
- generate the first real benchmark table (replacing the placeholder TBDs in this document)

Output: the project's central evidence base. Real numbers replace illustrative ones.

### Phase 4: Prompt injection hardening and adversarial evaluation

- run the adversarial set against all local models
- measure per-layer mitigation effectiveness (guardrail block rate, model bypass rate, output validation catch rate, residual risk)
- iterate on the guardrail implementation based on what the adversarial results reveal
- document findings in the threat model

### Phase 5: Dashboard and traces tab

- Metrics tab populated from the SQLite results
- Traces tab with filtering
- Experiments tab showing comparison views for the four experiments
- KPI cards on the Metrics tab
- latency chart

Output: the project is fully observable from the UI. The instructor can see the full story without leaving the app.

### Phase 6: Prompt v2 and prompt comparison

- author triage prompt v2 (a meaningfully different version, not just a tweak)
- run Experiment 4
- update the dashboards to support prompt-version filtering

Output: Experiment 4 has real data. Prompt comparison is available in the dashboard.

### Phase 7: Hardening, documentation, and presentation prep

- sweep adversarial cases that revealed weaknesses; iterate on guardrail or prompt
- write `architecture.md`, `evaluation-plan.md`, `tradeoffs.md`, `prompt-versions.md`, `threat-model.md`
- finalize ADRs based on what was actually decided during the build
- author the presentation slides
- rehearse the demo end-to-end (twice)

Output: complete deliverable. Everything ready for presentation day.

### Phase order, not phase duration

Phases are ordered so that the system is *demo-able after every phase from Phase 1 onward*. If the build runs out of time at any phase, what exists is still a coherent project, just with fewer experiments or thinner documentation. Nothing in this plan requires the project to be "done" before any of it is presentable.

---

## Final Recommendation

Build the system around **Qwen 3.5 local-first evaluation with prompt-injection-aware guardrails and dashboard-backed observability**.

Minimum viable strong version:

- Qwen 3.5 local at three sizes (subject to Phase 0 smoke test, default plan: 2B / 4B / 9B)
- validator-first pipeline with bounded retry
- guardrail layer with explicit attention to prompt injection
- 20–30 labeled normal tickets + ~12 labeled adversarial tickets
- four experiments (size, size-vs-controls interaction, validation-on/off, prompt-v1-vs-v2)
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

This section tracks decisions that have **not yet been made** and need to be resolved before or during the build. Every entry includes what the decision is, what's blocking it, and where it will be captured once made.

### ~~OD-1: Why Qwen 3.5 specifically (over Qwen 3.0)?~~ — RESOLVED

Resolved 2026-04-14. See [decision log](decisions/decision-log.md). Summary: Qwen 3.5's sub-10B variants deliver better structured-output quality and instruction following than their 3.0 equivalents at the same parameter count, which is the tier that fits on the project's consumer hardware. No licensing tradeoff (Apache 2.0). Vision/long-context features are available but unused and cost nothing.

### ~~OD-2: Cloud provider for the within-family comparison~~ — RESOLVED

Resolved 2026-04-14. See [decision log](decisions/decision-log.md). Summary: cloud comparison deferred to future work. The project is local-only for this iteration. The `LlmProvider` Protocol remains in the design so a cloud provider can be added without refactoring.

### ~~OD-3: Final local model lineup~~ — RESOLVED

Resolved 2026-04-14. See [decision log](decisions/decision-log.md). Summary: 2B / 4B / 9B, all three included pending Phase 0 verification. No a-priori exclusions — if a model can't produce structured output, the exclusion will be documented with evidence from the smoke test rather than assumed in advance.

### OD-4: Default model for the demo

- **What's needed:** which model is loaded by default when the Triage tab opens.
- **Why it's not yet decided:** depends on Phase 3 evaluation results. The default should be the model that won the multi-factor decision matrix, not the one with the highest single-metric score.
- **Will be captured in:** ADR for model selection (forthcoming, written after Phase 3)

### ~~OD-5: Cost analysis depth~~ — RESOLVED

Resolved 2026-04-14. See [decision log](decisions/decision-log.md). Summary: three components — (1) local compute resource cost per model (RAM, GPU, latency, disk), (2) hardware acquisition cost amortized over useful life, (3) hypothetical cloud comparison using published Qwen API pricing and actual token counts from the benchmarks, with a break-even calculation at projected daily volumes. Written up in `docs/cost-analysis.md` after Phase 3.

### ~~OD-6: Guardrail implementation depth~~ — RESOLVED

Resolved 2026-04-14. See [decision log](decisions/decision-log.md). Summary: heuristic-only baseline (pattern matching for known injection phrases, structural markers, length extremes, PII patterns). The heuristic will be measured against the adversarial set in Phase 4; expected failures on obfuscated attacks are treated as a finding, not a defect. Optional stretch: LLM-based second-pass classifier post-Phase 6 if time permits.

### ~~OD-7: Adversarial set final size and exact composition~~ — RESOLVED

Resolved 2026-04-14. See [decision log](decisions/decision-log.md). Summary: seven categories, ~12 tickets total. Categories and target counts are locked. Actual ticket text will be authored during Phase 3. Each ticket will be labeled with attack type and expected correct pipeline behavior.

---

## Documentation Plan

Documentation is split across multiple artifact types, each with a clear purpose:

- **This document** (`docs/llm-ticket-triage-plan.md`) — the working project plan, updated as the project evolves
- **`docs/decisions/`** — Architecture Decision Records (ADRs) for *architectural* decisions only, in `adr-tools` format
- **`docs/decision-log.md`** — chronological log of *scope, framing, and strategy* decisions that are not architectural
- **`docs/architecture.md`** — forthcoming, deeper detail on the pipeline, services, and component contracts
- **`docs/evaluation-plan.md`** — forthcoming, the executable version of the evaluation plan
- **`docs/threat-model.md`** — forthcoming, prompt injection threat model and mitigation map
- **`docs/tradeoffs.md`** — forthcoming, the cross-cutting tradeoffs document
- **`docs/prompt-versions.md`** — forthcoming, prompt v1 and v2 and the rationale for each
- **`docs/cost-analysis.md`** — forthcoming, the three-layer cost analysis
- **`docs/future-improvements.md`** — forthcoming, things explicitly out of scope and why
- **`docs/demo-script.md`** — forthcoming, the literal walkthrough used for the live demo
- **`docs/presentation-notes.md`** — forthcoming, slide-by-slide speaker notes

This split keeps the presentation short while preserving rigor in writing.
