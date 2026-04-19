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

- **Target size:** 35 tickets
- **Purpose:** measure task accuracy (category, severity, routing, escalation) and structured-output reliability across models and configurations
- **Design criteria:**
  - Cover all six categories in the taxonomy: billing, outage, account_access, bug, feature_request, other
  - Cover all five routing teams: support, billing, infra, product, security
  - Vary in length, tone, clarity, and completeness to reflect realistic support traffic
  - Each ticket labeled with ground truth for: category, severity, routing team, escalation flag
  - Include edge cases for non-actionable input and ambiguous severity (see below)

#### Edge case: non-actionable input (tickets n-031 through n-033)

Submissions that are not real support tickets — gibberish, form tests, irrelevant prose, or positive feedback with no issue. These bypass the pre-LLM guardrail (no injection patterns) and reach the model, which classifies as `category: "other"` with low confidence. The semantic validation layer is expected to flag these as non-actionable based on the combination of `category: "other"`, low confidence, and a summary that does not describe an actionable issue.

**Expected pipeline behavior:** model returns a result (not blocked), but post-LLM semantic validation flags the output as non-actionable. The pipeline surfaces this flag to the UI rather than silently routing a meaningless ticket.

#### Edge case: ambiguous severity (tickets n-034 and n-035)

Real observations where the user describes something that might be an issue but provides no indication of urgency, business impact, or scope. The model must still select a severity value since it is a required field. The correct default is `severity: "low"` when severity is genuinely ambiguous, with a lower confidence score as the signal that the model had to guess.

**Expected pipeline behavior:** model returns a valid result with `severity: "low"` and a confidence score noticeably lower than for tickets with clear severity indicators. Semantic validation does not block — the output is valid, just uncertain.

### Adversarial set

- **Target size:** 14 tickets
- **Purpose:** measure prompt injection defense effectiveness and general pipeline robustness
- **Design criteria:** each ticket targets a specific attack category with a documented expected correct pipeline behavior

| Category | Count | What it tests | Expected correct behavior |
|---|---:|---|---|
| Direct prompt injection | 4 | Explicit override instructions in ticket body | Guardrail blocks, or model ignores injection and triages normally |
| Direct injection with obfuscation | 2 | Base64, language switching, invisible Unicode | Tests whether guardrails are semantic or pattern-matching |
| Indirect injection via quoted content | 3 | Malicious instructions inside quoted emails/logs/errors | Pipeline should triage the legitimate complaint, not follow the quoted injection |
| PII / data leak triggers | 2 | Fake credit card numbers, SSN patterns | Guardrail warns; pipeline continues with warning logged |
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

### Experiment 4: Prompt comparison *(v1 only — Phase 6 scoped out)*

- **Configurations:** triage prompt v1 only. v2 was not authored — see [decision log 2026-04-19 "Phase 6 skipped"](decisions/decision-log.md) for rationale.
- **Original question:** How much does prompt design contribute vs model selection?
- **Status:** E4 ships with v1 baseline metrics per model (from E1 data). The v1-vs-v2 delta is not measured in this iteration. The original question remains open as a `future-improvements.md` item.
- **Why not run anyway:** With JSON validity saturated at 100% across all three models under production config (see Phase 3 replication), v2 could only measure category-accuracy headroom. The 9B leads at 83.4%, the 4B at 80.6%, and the 2B at 74.9% — a 2.8–8.5pp spread that a different prompt might partially close. That measurement is interesting but not worth the time budget compared to Phase 7 deliverables (see decision log).
- **Dataset if re-run in the future:** Full normal set (35 tickets); same protocol as Phase 3 (n=5 replications recommended).
- **Insight that would be gained:** which fields benefit most from prompt iteration, and whether prompt quality or model size has a larger effect at the sizes being tested.

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

## Evaluation methodology limitations

This section documents what the evaluation methodology can and cannot support, and how Phase 3 replication (n=5) and Phase 4 (still n=1) differ in evidentiary strength.

### Phase 3: reproducibility-tested at n=5

Phase 3 experiments (E1, E2, E3) were replicated 5 times each under the current production configuration (`think=false`, `num_ctx=16384`). Standard deviations across 5 runs are 0-5% on accuracy metrics and 1-3% on latency, establishing these as reproducibility-tested baselines rather than point observations.

At n=5 runs × 35 tickets, large differences (e.g., 9B category accuracy 83.4% vs 2B 74.9%) have non-overlapping 1-stddev bands and are defensible conclusions. Small differences (e.g., 9B vs 4B at 83.4% vs 80.6%, ~3pp gap) are directionally suggestive — the 1-stddev bands do not overlap — but could reflect systematic label ambiguity on a few tickets rather than a generalizable capability difference. Per-ticket analysis (the accuracy matrix in `data/phase3-1/analysis/`) is more informative than aggregate percentages for these borderline cases.

The original Phase 3 data (n=1, `think=true`, `num_ctx=4096`) remains in `data/phase3/` as a record of the system under its original configuration. Every metric in the replication exceeds 2 standard deviations from the original observation — the two datasets measure different system configurations and are not directly comparable.

### Phase 4: still n=1, replication pending

The Phase 4 adversarial evaluation ran 14 tickets per model once (n=1). Each ticket's outcome is a single observation, not a measured rate. The a-008 finding demonstrates the risk of single-run methodology: the original run showed a partial field overlap on the 4B; two ad hoc replication attempts produced parse failures instead, reclassifying the finding from "ambiguous integrity compromise" to "non-reproducing observation."

Phase 4 was run under `think=true` and `num_ctx=4096`. The configuration changes that transformed Phase 3 results (`think=false`, `num_ctx=16384`) may similarly affect adversarial results — particularly the availability failures (parse timeouts from reasoning-mode exhaustion), which were the dominant adversarial effect. Phase 4 replication under the current configuration is pending.

Per-category rates (e.g., "0% integrity risk on direct injection") are point observations from single runs and are subject to the same replication caveat demonstrated by a-008.

### Small numeric differences require per-ticket analysis

Differences within a few percentage points at n=35 should not be interpreted as real signal from aggregate percentages alone. The per-ticket accuracy matrix (`data/phase3-1/analysis/e1-per-ticket-matrix-corrected.csv`) provides ticket-level visibility into where models diverge. When all three models consistently fail on the same field for the same ticket, the ground truth label is the first thing to audit — the Phase 3 replication surfaced 5 label corrections out of 35 tickets (14%), demonstrating that model consensus is a reliable audit signal.

### Ground truth quality affects all accuracy metrics

The Phase 3 replication revealed that 5 of 35 ground truth labels were incorrect (see `data/phase3-1/analysis/ground-truth-audit.md`). The corrected labels increased aggregate accuracy by 5-10pp for all models. Original-label and corrected-label matrices are both preserved. All replication accuracy numbers in `docs/evaluation-checklist.md` are scored against the corrected labels. The original Phase 3 data (in `data/phase3/`) is scored against the original labels and was not re-scored — it remains a snapshot of the system at that configuration with those labels.

---

## Reporting

The evaluation results are reported in three places:

1. **The Metrics tab** — benchmark comparison tables, KPI cards, and per-experiment views
2. **The presentation** — slides 3 (model evaluation) and 5 (failure handling) draw directly from the evaluation data
3. **The project documentation** — this document, the threat model, the cost analysis, and the tradeoffs doc all reference evaluation findings once they exist

The reporting is honest about what the evaluation can and cannot conclude. The dataset is small enough that individual results are visible and explainable, but not large enough for rigorous statistical inference. Findings are stated as observed patterns, not as statistically-validated claims.
