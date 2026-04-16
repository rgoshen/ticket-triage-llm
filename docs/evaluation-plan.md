# Evaluation Plan

This document describes the evaluation methodology for the ticket triage pipeline: what is being measured, how, on what data, and what the planned experiments are designed to reveal.

For the prompt injection threat model and adversarial set design rationale, see [threat-model.md](threat-model.md). For the cost analysis methodology, see [cost-analysis.md](cost-analysis.md).

---

## Evaluation thesis

The evaluation is structured around the project's central question:

> **In a production LLM system, how much of the value comes from the model itself versus from the surrounding engineering controls?**

Each experiment probes a different dimension of that question. The evaluation is not a leaderboard — it's an investigation. The goal is findings, not just numbers.

---

## Datasets

### Normal labeled set

- **Target size:** 20–30 tickets
- **Purpose:** measure task accuracy (category, severity, routing, escalation) and structured-output reliability across models and configurations
- **Design criteria:**
  - Cover all six categories in the taxonomy: billing, outage, account_access, bug, feature_request, other
  - Cover all five routing teams: support, billing, infra, product, security
  - Vary in length, tone, clarity, and completeness to reflect realistic support traffic
  - Each ticket labeled with ground truth for: category, severity, routing team, escalation flag

### Adversarial set

- **Target size:** ~12 tickets
- **Purpose:** measure prompt injection defense effectiveness and general pipeline robustness
- **Design criteria:** each ticket targets a specific attack category with a documented expected correct pipeline behavior

| Category | Target count | What it tests | Expected correct behavior |
|---|---:|---|---|
| Direct prompt injection | 3–4 | Explicit override instructions in ticket body | Guardrail blocks, or model ignores injection and triages normally |
| Direct injection with obfuscation | 2 | Base64, language switching, invisible Unicode | Tests whether guardrails are semantic or pattern-matching |
| Indirect injection via quoted content | 2–3 | Malicious instructions inside quoted emails/logs/errors | Pipeline should triage the legitimate complaint, not follow the quoted injection |
| PII / data leak triggers | 1–2 | Fake credit card numbers, SSN patterns | Guardrail warns; pipeline continues with warning logged |
| Hostile / abusive language | 1 | Angry but legitimate ticket | Pipeline triages normally; tone does not corrupt output |
| Length extremes | 1 | Very short and/or very long input | Graceful handling; may produce lower-quality triage |
| Multilingual | 1 | Non-English ticket | Tests cross-language capability |

For full rationale on the adversarial categories, see [threat-model.md](threat-model.md).

---

## Metrics

### Task quality metrics (from normal set)

| Metric | What it measures |
|---|---|
| Category accuracy | Proportion of tickets where the assigned category matches ground truth |
| Severity accuracy | Proportion of tickets where the assigned severity matches ground truth |
| Routing accuracy | Proportion of tickets where the assigned routing team matches ground truth |
| Escalation accuracy | Proportion of tickets where the escalation flag matches ground truth |

### Structured-output reliability metrics (from both sets)

| Metric | What it measures |
|---|---|
| JSON validity rate | Proportion of requests where the model's output parses as valid JSON |
| Schema pass rate | Proportion of parsed outputs that conform to the `TriageOutput` pydantic model |
| Semantic check pass rate | Proportion of schema-valid outputs that pass cross-field consistency checks |
| Retry rate | Proportion of requests that required a retry (first-pass validation failure) |
| Retry success rate | Of retried requests, what proportion succeeded on the second attempt |

### Operational metrics (from both sets)

| Metric | What it measures |
|---|---|
| Avg / p50 / p95 latency | Response time distribution |
| Tokens/sec (decode) | Throughput at decode time |
| Tokens in / out / total per request | Token usage for cost projection |
| Time-to-first-token | Responsiveness for streaming UX (if applicable) |

### Prompt injection metrics (from adversarial set only)

| Metric | What it measures |
|---|---|
| Guardrail block rate | Proportion of adversarial inputs caught by the pre-LLM guardrail |
| Guardrail bypass rate | Proportion of adversarial inputs that reached the model |
| Model compliance rate | Of bypassed inputs, proportion where the model followed the injected instructions |
| Validation catch rate | Of compliant-model outputs, proportion caught by post-LLM validation |
| Residual risk rate | Proportion that succeeded end-to-end (bypassed all three layers) |
| Per-rule hit distribution | Which guardrail rules triggered on which attack categories |

### Cost metrics (computed, not measured live)

| Metric | What it measures |
|---|---|
| Tokens per request (avg) | Input for cost projection |
| Hypothetical cloud cost per request | Projected from published Qwen API pricing |
| Hardware amortized daily cost | Fixed cost regardless of volume |
| Break-even volume | Daily ticket count where local becomes cheaper than cloud |

For full cost methodology, see [cost-analysis.md](cost-analysis.md).

---

## Experiments

### Experiment 1: Model size comparison

- **Models:** Qwen 3.5 2B vs 4B vs 9B (subject to Phase 0 smoke test)
- **Question:** How does task quality, latency, and reliability scale across model sizes on consumer hardware?
- **Dataset:** Full normal set + full adversarial set
- **Primary metrics:** task accuracy, JSON validity rate, latency, tokens/sec
- **Expected insight:** the quality-vs-size curve — how much you lose by going smaller, and whether the degradation is linear or has a cliff

### Experiment 2: Model size vs engineering controls interaction

- **Configurations:** smallest viable model WITH full validation/retry vs largest model WITHOUT validation/retry
- **Question:** Can a smaller, cheaper model with strong engineering controls match or outperform a larger model running without them?
- **Dataset:** Full normal set
- **Primary metrics:** end-to-end task accuracy (including cases where retry recovered a failure), JSON validity rate, routing correctness
- **Expected insight:** this is the most direct test of the project's central thesis. If a 4B with validation outperforms a 9B without it on routing accuracy, that's a publishable finding.

### Experiment 3: Validation impact

- **Configurations:** full pipeline (parse + schema + semantic checks + bounded retry) vs same pipeline with validation and retry disabled, on the same model
- **Question:** How much do engineering controls contribute to overall reliability, independent of model choice?
- **Dataset:** Full normal set
- **Primary metrics:** end-to-end task accuracy with vs without validation, JSON validity rate, percentage of cases where retry recovered a failure
- **Expected insight:** quantifies the "value of controls" in isolation

### Experiment 4: Prompt comparison

- **Configurations:** triage prompt v1 vs v2, on the same model
- **Question:** How much does prompt design contribute vs model selection?
- **Dataset:** Full normal set
- **Primary metrics:** task accuracy, JSON validity rate, retry rate
- **Expected insight:** which fields benefit most from prompt iteration, and whether prompt quality or model size has a larger effect at the sizes being tested

### Prompt injection sub-evaluation

- **Models:** all local models
- **Dataset:** full adversarial set
- **Question:** how effective is each defensive layer, and what's the residual risk?
- **Primary metrics:** per-layer effectiveness (block rate, bypass rate, compliance rate, validation catch rate, residual risk rate), broken down by attack category
- **Expected insight:** which attack categories each layer catches and misses, and the honest residual risk statement

For the defensive layer design and residual risk framing, see [threat-model.md](threat-model.md).

---

## Execution

All experiments are run by the eval harness in `src/ticket_triage_llm/eval/`. Each run:

1. Takes a dataset (normal, adversarial, or both) and a configuration (model, prompt version, validation on/off)
2. Runs each ticket through the pipeline
3. Stores a trace for every request, tagged with a `run_id` identifying the experiment run
4. The metrics service computes summaries from the tagged traces on demand

Results are viewable in the Metrics tab (Benchmark Results section) and the Experiments tab. Raw traces are inspectable in the Traces tab.

---

## Reporting

The evaluation results are reported in three places:

1. **The Metrics tab** — benchmark comparison tables, KPI cards, and per-experiment views
2. **The presentation** — slides 3 (model evaluation) and 5 (failure handling) draw directly from the evaluation data
3. **The project documentation** — this document, the threat model, the cost analysis, and the tradeoffs doc all reference evaluation findings once they exist

The reporting is honest about what the evaluation can and cannot conclude. The dataset is small enough that individual results are visible and explainable, but not large enough for rigorous statistical inference. Findings are stated as observed patterns, not as statistically-validated claims.
