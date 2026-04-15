# LLM Support Ticket Triage Copilot - Final Project Plan

## Project Overview

**Title:** Production-Oriented Support Ticket Triage Copilot with Qwen Local/Cloud Evaluation

**Core Function:** Converts raw support tickets into structured triage output (category, severity, routing team, summary, escalation flag, confidence, draft response) through a validator-first pipeline with provider abstraction and a built-in benchmark dashboard.

**Timebox:** 5 days build, 5 min presentation, 5 min demo, 5 min Q&A

**Hardware:** MacBook Pro M4 Pro, 24GB RAM

**Primary Goal:** Build a small but rigorous LLM system that demonstrates production engineering decisions, not just prompt usage.

---

## Project Thesis

This project is not “a chatbot for support.” It is a **production-style LLM inference pipeline** for support ticket triage with:

- structured output,
- schema validation,
- bounded retries,
- guardrails,
- provider abstraction,
- evaluation across model variants,
- and a UI dashboard for benchmark and trace visibility.

The core argument of the project is:

> LLM usefulness comes from the surrounding engineering controls as much as from the model itself.

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

Use **Qwen 3 / Qwen 3.5** as the main model family because it supports:

- local execution via Ollama,
- cloud/API variants,
- strong instruction following,
- and good structured/JSON-oriented output behavior.

### Recommended Comparison

Use **two or three Qwen variants** rather than many unrelated families.

#### Local models

- **Qwen3 3B** — fast baseline
- **Qwen3 8B** — likely best balance
- **Qwen3 14B** — higher-quality local baseline

#### Optional cloud model

- **Qwen-Plus** or **Qwen-Max** as a cloud/API comparison point

### Why this comparison is strong

It lets you compare:

- model size vs quality,
- local speed vs cloud cost,
- and practical engineering tradeoffs without adding too much scope.

---

## Expected Hardware Fit

For your **MacBook Pro M4 Pro, 24GB RAM**:

| Model | Quant | Approx RAM | Expected Role |
|---|---:|---:|---|
| Qwen3 3B | Q4_K_M | ~3GB | Fast baseline |
| Qwen3 8B | Q4_K_M | ~6GB | Balanced candidate |
| Qwen3 14B | Q4_K_M | ~10–12GB | Higher-quality local baseline |

This hardware should be very comfortable for local experiments with these model sizes.

### Ollama commands

```bash
ollama pull qwen3:3b
ollama pull qwen3:8b
ollama pull qwen3:14b
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

---

## Provider Interface

```ts
interface LlmProvider {
  name: string;
  generateStructuredTicket(input: string, promptVersion: string): Promise<ModelResult>;
}
```

### Implementations

- `OllamaQwenProvider`
- `CloudQwenProvider`

---

## Folder Structure

```text
llm-ticket-triage-qwen/
├── README.md
├── package.json
├── .env
├── .env.example
├── docs/
│   ├── architecture.md
│   ├── evaluation-plan.md
│   ├── tradeoffs.md
│   ├── prompt-versions.md
│   ├── demo-script.md
│   └── presentation-notes.md
│
├── client/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   │   ├── TicketInputForm.tsx
│   │   │   ├── TriageResultCard.tsx
│   │   │   ├── TracePanel.tsx
│   │   │   ├── ProviderSelector.tsx
│   │   │   ├── MetricsSummary.tsx
│   │   │   ├── BenchmarkTable.tsx
│   │   │   └── LatencyChart.tsx
│   │   ├── pages/
│   │   │   ├── HomePage.tsx
│   │   │   ├── MetricsPage.tsx
│   │   │   ├── TracesPage.tsx
│   │   │   └── ExperimentsPage.tsx
│   │   └── lib/
│   │       ├── api.ts
│   │       └── types.ts
│
├── server/
│   └── src/
│       ├── app.ts
│       ├── server.ts
│       ├── config/
│       │   ├── env.ts
│       │   └── providers.ts
│       ├── routes/
│       │   ├── triage.routes.ts
│       │   ├── metrics.routes.ts
│       │   ├── traces.routes.ts
│       │   └── experiments.routes.ts
│       ├── controllers/
│       ├── services/
│       │   ├── triage.service.ts
│       │   ├── prompt.service.ts
│       │   ├── guardrail.service.ts
│       │   ├── validation.service.ts
│       │   ├── retry.service.ts
│       │   ├── trace.service.ts
│       │   ├── metrics.service.ts
│       │   └── provider-router.service.ts
│       ├── providers/
│       │   ├── llm-provider.interface.ts
│       │   ├── ollama-qwen.provider.ts
│       │   └── cloud-qwen.provider.ts
│       ├── prompts/
│       │   ├── triage.v1.ts
│       │   ├── triage.v2.ts
│       │   └── repair-json.v1.ts
│       ├── schemas/
│       │   ├── triage-input.schema.ts
│       │   ├── triage-output.schema.ts
│       │   └── trace.schema.ts
│       ├── storage/
│       │   ├── db.ts
│       │   ├── trace.repository.ts
│       │   ├── metrics.repository.ts
│       │   └── benchmark.repository.ts
│       └── eval/
│           ├── datasets/
│           │   ├── gold-tickets.json
│           │   └── adversarial-tickets.json
│           ├── runners/
│           │   ├── run-local-qwen-comparison.ts
│           │   ├── run-local-vs-cloud.ts
│           │   └── summarize-results.ts
│           └── reports/
│               ├── local-comparison.json
│               └── local-vs-cloud.json
```

---

## UI Pages

### 1. Home Page

Purpose: main triage workflow.

Features:

- ticket input form,
- sample ticket loader,
- provider/model selector,
- result panel,
- validation status,
- trace summary.

### 2. Metrics Page

Purpose: dashboard for benchmarks and runtime metrics.

Features:

- KPI cards,
- benchmark comparison table,
- latency chart,
- JSON validity rate,
- retry rate,
- guardrail rate,
- cloud cost estimate where applicable.

### 3. Traces Page

Purpose: inspect individual requests.

Features:

- recent run list,
- filter by provider,
- filter by prompt version,
- inspect request/response metadata,
- inspect validation failures.

### 4. Experiments Page

Purpose: compare experimental runs.

Features:

- local 3B vs 8B vs 14B comparison,
- local vs cloud comparison,
- prompt v1 vs v2 comparison,
- exportable result summaries.

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
eval runner -> JSON/SQLite results -> metrics service -> dashboard API -> Metrics UI
live requests -> trace store -> traces API -> trace explorer UI
```

### Backend endpoints

#### `POST /triage`

Runs live triage inference and stores trace data.

#### `GET /metrics`

Returns aggregate benchmark and runtime metrics.

#### `GET /traces`

Returns recent request traces.

#### `GET /experiments`

Returns experiment summaries and comparison results.

---

## Suggested Metrics Schema

```json
{
  "provider": "qwen3-8b-local",
  "accuracy": 0.87,
  "jsonValidityRate": 0.95,
  "avgLatencyMs": 3200,
  "p95LatencyMs": 4700,
  "retryRate": 0.08,
  "guardrailBlockRate": 0.12,
  "estimatedCostPerRequest": 0.0,
  "sampleCount": 25,
  "promptVersion": "v1"
}
```

### Suggested trace schema

```typescript
interface TraceRecord {
  requestId: string;
  ticketHash: string;
  promptVersion: string;
  model: string;
  provider: string;
  guardrailResult: 'pass' | 'warn' | 'block';
  validationStatus: 'pass' | 'fail';
  semanticCheckStatus: 'pass' | 'fail';
  retryCount: number;
  latencyMs: number;
  tokensIn: number;
  tokensOut: number;
  tokensTotal: number;
  tokensPerSec: number;
  estimatedCost: number;
  timestamp: string;
}
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

| Model | Accuracy | JSON Valid | Latency | Tokens/s | Tokens/req | Retries | Cost/req |
|-------|----------|------------|---------|----------|------------|---------|----------|
| Qwen3 3B | ~78% | ~85% | ~1.8s | ~52 | ~800 | ~18% | $0 |
| **Qwen3 8B** | **~87%** | **~95%** | **~3.2s** | **~32** | **~950** | **~8%** | **$0** |
| Qwen3 14B | ~91% | ~97% | ~6.8s | ~18 | ~1050 | ~5% | $0 |
| Cloud Qwen | ~93% | ~98% | ~2.5s | ~45 | ~900 | ~3% | ~$0.002 |

## Evaluation Plan

### Dataset

Build:

- **20–30 labeled normal tickets**
- **5–10 adversarial/malformed tickets**

Each normal ticket should have labels for:

- category,
- severity,
- routing team,
- escalation.

### Core metrics

| Metric | Purpose |
|---|---|
| Category accuracy | classification quality |
| Severity accuracy | operational usefulness |
| Routing accuracy | downstream utility |
| JSON validity rate | structured-output reliability |
| Retry rate | stability signal |
| Avg / p95 latency | operational responsiveness |
| Guardrail block success | safety behavior |
| Cost/request | cloud tradeoff |

### Experiments

#### Experiment 1: Local model size comparison

- Qwen3 3B vs Qwen3 8B vs Qwen3 14B

#### Experiment 2: Local vs cloud

- best local model vs cloud Qwen model

#### Experiment 3: Validation impact

- with validation/retry vs without validation/retry

#### Experiment 4: Prompt comparison (optional)

- triage prompt v1 vs v2

---

## Expected Benchmark Output Example

| Model | Accuracy | JSON Validity | Avg Latency | Tokens/s | RAM | Cost/Request | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| Qwen3 3B local | 0.78 | 0.85 | 1800 ms | 52 | 3GB | $0.00 | fastest |
| Qwen3 8B local | 0.87 | 0.95 | 3200 ms | 32 | 6GB | $0.00 | best balance |
| Qwen3 14B local | 0.91 | 0.97 | 6800 ms | 18 | 12GB | $0.00 | highest local quality |
| Cloud Qwen | 0.93 | 0.98 | 2500 ms | N/A | N/A | $0.0015 | cost but strong quality |

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
- run with local Qwen3 8B,
- show structured output and trace panel.

### Step 2: Model switch

- switch to local Qwen3 14B or cloud Qwen,
- show differences in latency and output quality.

### Step 3: Failure case

- run adversarial or malformed ticket,
- show guardrail or validation/retry handling.

### Step 4: Metrics dashboard

- open metrics page,
- show benchmark table,
- show latency chart,
- show why one model was selected.

---

## Documentation Plan

Move deeper detail into docs:

- architecture decisions,
- full dataset,
- full benchmark results,
- prompt versions,
- tradeoff analysis,
- known limitations,
- future improvements.

This keeps the presentation short while preserving rigor.

---

## Four-Day Build Plan

### Day 1

- create backend skeleton,
- build triage route,
- integrate one local Qwen model,
- build schema validation,
- make one happy path work.

### Day 2

- add provider abstraction,
- add 2nd and 3rd local models,
- add trace logging,
- add basic UI for ticket submission and result display.

### Day 3

- build benchmark runner,
- create labeled dataset,
- run evaluation,
- store benchmark results,
- add dashboard metrics page.

### Day 4

- polish dashboard,
- add traces page,
- finalize presentation slides,
- write documentation,
- rehearse demo and Q&A.

### Day 5

- presentation day.

---

## Final Recommendation

Build the system around **Qwen local-first evaluation with dashboard-backed observability**.

Minimum viable strong version:

- Qwen3 3B local,
- Qwen3 8B local,
- Qwen3 14B local,
- validator-first pipeline,
- built-in metrics dashboard,
- trace explorer,
- 20–30 labeled ticket benchmark,
- 6-slide presentation.

Optional stretch:

- add one cloud Qwen/API baseline for cost comparison.

This version best matches your time limit, hardware, and class emphasis on engineering rigor.

---

## Decision Checklist

### ADR 001 — Model Selection

- [ ] Which model becomes the app default?
- [ ] Which models are compared in eval?
- [ ] Is cloud comparison included?
- **Justify with:** accuracy, JSON validity, latency, tokens/sec, tokens/request, retry rate, cost

### ADR 002 — Output Format

- [ ] JSON schema vs free-form text?
- **Justify with:** parse reliability, field-level accuracy, downstream automation needs

### ADR 003 — Validation and Retry

- [ ] Parse only, or parse + semantic checks?
- [ ] How many retries?
- **Justify with:** retry rate improvement, latency impact, failure visibility

### ADR 004 — Guardrails

- [ ] Minimal heuristics vs stronger classifier?
- [ ] What categories of input do you detect?
- **Justify with:** block rate, false positives, false negatives on adversarial set

### ADR 005 — Observability and Dashboard

- [ ] What metrics appear in the UI?
- [ ] What trace fields are stored?
- **Justify with:** tokens/sec, tokens used, latency, prompt version comparisons

### ADR 006 — Dataset and Eval Scope

- [ ] How many normal tickets?
- [ ] How many adversarial tickets?
- **Justify with:** label quality over quantity, coverage of edge cases

---

## ADR Template

Use this for each file in `docs/decisions/`.

```markdown
# ADR NNN: <Decision Title>

## Status
Accepted | Proposed | Deprecated

## Context
- What problem is this decision solving?
- Why does it matter for this project?
- What constraints apply? (deadline, hardware, class emphasis on rigor)

## Options Considered
- Option A: ...
- Option B: ...
- Option C: ...

## Decision
We decided to **[chosen option]**.

## Rationale
- Reason 1 (tie to metrics where possible)
- Reason 2
- Reason 3

Example:
> On the 25-ticket benchmark, Qwen3 8B achieved 87% accuracy,
> 95% JSON validity, ~3.2s avg latency, ~32 tokens/sec,
> ~950 tokens/request, and 8% retry rate — best overall
> balance for this workload on M4 Pro hardware.

## Tradeoffs
- **Upside:** ...
- **Downside:** ...
- **Why we accept the downside:** ...

## Consequences
- How this affects implementation.
- What follow-up work or monitoring is needed.

## Alternatives Not Chosen
- Why Option A was rejected.
- Why Option B was rejected.
```
