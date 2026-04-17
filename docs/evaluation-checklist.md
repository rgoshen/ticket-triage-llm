# Evaluation Checklist

A working document for logging results as each phase produces data. Fill in as you go — this is a living record, not a planning document.

---

## Phase 0: Smoke Test

**Date started:** 2026-04-16
**Ollama version:** 0.20.7
**Hardware:** MacBook Pro M4 Pro, 24GB unified memory
**macOS version:** 26.4.1 (build 25E253)

**Runner:** `scripts/phase0_smoke_test.py`
**Sampling:** temperature=0.2, top_p=0.9 (CLAUDE.md-locked values)
**Raw outputs:** `data/phase0/qwen3.5-{2b,4b,9b}-smoke.jsonl`

### Model Pull Verification

| Model | Pull command | Size on disk | Pull successful? | Notes |
|---|---|---|---|---|
| Qwen 3.5 2B | `ollama pull qwen3.5:2b` | 2.7 GB | ☒ Yes | Q8_0 quantization; 2.3B params; 262K ctx. |
| Qwen 3.5 4B | `ollama pull qwen3.5:4b` | 3.4 GB | ☒ Yes | Q4_K_M quantization; 4.7B params; 262K ctx. |
| Qwen 3.5 9B | `ollama pull qwen3.5:9b` | 6.6 GB | ☒ Yes | Q4_K_M quantization; 9.7B params; 262K ctx. Pulled as `qwen3.5:latest` and aliased locally via `ollama cp qwen3.5:latest qwen3.5:9b` to match the tag the runner expects. |

### MLX Acceleration Check

Checked with `OLLAMA_MLX=1 ollama run <model> --verbose` on a throwaway "say hi as JSON" prompt. Decode rates are well below what MLX kernels would deliver on M4 Pro for this architecture, so MLX is treated as **not engaged** for the `qwen35` architecture in Ollama 0.20.7. Apple Metal (GGML) is the active backend.

| Model | MLX engaged? | Prefill tokens/s | Decode tokens/s | Notes |
|---|---|---|---|---|
| Qwen 3.5 2B | ☒ No | 40.95 | 61.72 | Backend: Metal GGML. Decode much lower than MLX-accelerated Qwen3/Mistral builds on same hardware. Reasoning mode produced 2720 eval tokens for a trivial prompt — consistent with thinking-mode being on by default. |
| Qwen 3.5 4B | ☒ No | 36.21 | 36.03 | Metal GGML. Latency dominated by parameter count, as expected without MLX. |
| Qwen 3.5 9B | ☒ No | 10.47 | 26.73 | Metal GGML. Still comfortably fits in 24 GB unified memory alongside IDE + app. |

**Takeaway:** MLX coverage for the `qwen35` architecture has not landed in Ollama 0.20.7, so planning must assume Metal GGML performance. If a later Ollama release adds MLX for this family, the benchmarks should be rerun — latency numbers will likely improve meaningfully.

### Structured Output Smoke Test

Sent 3 sample tickets (`n-004` outage, `n-007` billing, `n-003` feature request) to each model via the OpenAI-compatible endpoint (`http://localhost:11434/v1`) using the runner's single throwaway triage prompt. "Correct fields" = all 8 required keys present, no extras. "Reasonable values" = parsed `category` and `severity` matched expected ground truth.

**Sample ticket 1:** n-004 — *URGENT: Complete service outage* (expected: category=outage, severity=critical, routingTeam=infra, escalation=true)

| Model | Valid JSON? | Correct fields? | Reasonable values? | Latency | Notes |
|---|---|---|---|---|---|
| Qwen 3.5 2B | ☒ Yes | ☒ Yes | ☒ Yes | 43.55s | confidence 0.95; escalation=true; 2451 completion tokens (reasoning mode verbose). |
| Qwen 3.5 4B | ☒ Yes | ☒ Yes | ☒ Yes | 49.73s | confidence 0.95; escalation=true; 1575 completion tokens. Tightest summary of the three. |
| Qwen 3.5 9B | ☒ Yes | ☒ Yes | ☒ Yes | 84.92s | confidence 0.98; escalation=true; 1772 completion tokens. Most professional draftReply. First run after model load — subsequent requests were faster. |

**Sample ticket 2:** n-007 — *Billing discrepancy on latest invoice* (expected: category=billing, severity=medium, routingTeam=billing, escalation=false)

| Model | Valid JSON? | Correct fields? | Reasonable values? | Latency | Notes |
|---|---|---|---|---|---|
| Qwen 3.5 2B | ☒ Yes | ☒ Yes | ☒ Yes | 652.16s | **Outlier.** confidence 0.9; 3138 completion tokens. The 2B ran away in reasoning mode before emitting the final JSON. JSON itself was clean — latency was the failure, not correctness. Phase 1+ must apply a completion-token cap or a provider-side timeout. |
| Qwen 3.5 4B | ☒ Yes | ☒ Yes | ☒ Yes | 52.11s | confidence 0.95; 1776 completion tokens. |
| Qwen 3.5 9B | ☒ Yes | ☒ Yes | ☒ Yes | 45.01s | confidence 0.95; 1097 completion tokens. Most token-efficient on this ticket. |

**Sample ticket 3:** n-003 — *Feature request: Dark mode for mobile app* (expected: category=feature_request, severity=low, routingTeam=product, escalation=false)

| Model | Valid JSON? | Correct fields? | Reasonable values? | Latency | Notes |
|---|---|---|---|---|---|
| Qwen 3.5 2B | ☒ Yes | ☒ Yes | ☒ Yes | 42.24s | confidence 0.9; 2521 completion tokens. |
| Qwen 3.5 4B | ☒ Yes | ☒ Yes | ☒ Yes | 35.67s | confidence 0.95; 1143 completion tokens. Fastest run overall. |
| Qwen 3.5 9B | ☒ Yes | ☒ Yes | ☒ Yes | 47.04s | confidence 1.00; 1195 completion tokens. |

**Aggregate:** All three models hit 100% valid JSON, 100% fields present, and 100% correct-values on the 3-ticket sample. No malformed outputs, no missing fields, no wrong categories or severities.

### Phase 0 Decision

- ☒ 2B stays in the comparison — can produce structured output. 3/3 valid JSON, 3/3 correct fields, 3/3 correct values. Known risk to manage in Phase 1+: reasoning-mode over-generation can spike latency (observed 652s on a routine billing ticket). The retry policy and completion-token caps handle this; the model itself is not the problem.
- ☒ 4B stays in the comparison — 3/3 valid JSON, 3/3 correct fields, 3/3 correct values; 35–52s latency band with stable token counts.
- ☒ 9B stays in the comparison — 3/3 valid JSON, 3/3 correct fields, 3/3 correct values; 45–85s latency band (first-call warmup accounts for the high end).
- ☒ Final model lineup confirmed: **Qwen 3.5 2B, 4B, 9B** — all three kept for the Phase 3 size-comparison experiment.
- ☒ Decision log entry written — see `docs/decisions/decision-log.md` (2026-04-16 Phase 0 entry).

---

## Sampling Configuration Log

### Baseline Configuration

| Parameter | Planned value | Actual value used | Notes |
|---|---|---|---|
| Temperature | 0.2 | | Locked 2026-04-16 — see decision log |
| Top-p | 0.9 | | Locked 2026-04-16 — see decision log |
| Top-k | 40 | | |
| Repetition penalty | 1.0 (disabled) | | |

### Sampling Observations During Development

Log any observations about how sampling settings affect output quality as you encounter them:

| Date | Model | Parameter changed | From → To | Observed effect | Keep change? |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |

### Sampling Experiment (if time permits)

If time allows during or after Phase 3, test 2–3 temperature settings on the same model with the same dataset:

| Model | Temperature | JSON validity rate | Task accuracy | Avg latency | Notes |
|---|---|---|---|---|---|
| | 0.0 (greedy) | | | | |
| | 0.2 | | | | |
| | 0.5 | | | | |
| | 0.8 | | | | |

**Finding:** _______________________________________________

---

## Phase 3: Experiment Execution Log

### Experiment 1: Model Size Comparison

**Date run:** _______________
**Dataset:** gold_tickets.json (__ tickets)
**Prompt version:** v1
**Sampling config:** temperature=___ top_p=___ top_k=___

| Model | run_id | Category acc | Severity acc | Routing acc | JSON valid | Retry rate | Avg latency | p95 latency | Tokens/s | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen 3.5 2B | | | | | | | | | | |
| Qwen 3.5 4B | | | | | | | | | | |
| Qwen 3.5 9B | | | | | | | | | | |

**Key finding from Experiment 1:** _______________________________________________

### Experiment 2: Model Size vs Engineering Controls

**Date run:** _______________
**Dataset:** gold_tickets.json (__ tickets)
**Prompt version:** v1
**Sampling config:** temperature=___ top_p=___ top_k=___

| Configuration | run_id | Category acc | Severity acc | Routing acc | JSON valid | Retry rate | Avg latency | Notes |
|---|---|---|---|---|---|---|---|---|
| Smallest model + full validation | | | | | | | | |
| Largest model + no validation | | | | | | | | |

**Key finding from Experiment 2:** _______________________________________________

**Does this support or contradict the project thesis?** _______________________________________________

### Experiment 3: Validation Impact

**Date run:** _______________
**Model:** _______________
**Dataset:** gold_tickets.json (__ tickets)
**Prompt version:** v1
**Sampling config:** temperature=___ top_p=___ top_k=___

| Configuration | run_id | Category acc | Severity acc | Routing acc | JSON valid | Retry rate | Retries that recovered | Avg latency | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Full validation + retry | | | | | | | | | |
| No validation, no retry | | | | | | | | | |

**Key finding from Experiment 3:** _______________________________________________

**Percentage of cases where retry recovered a failure:** _____ %

### Experiment 4: Prompt Comparison

**Date run:** _______________
**Model:** _______________
**Dataset:** gold_tickets.json (__ tickets)
**Sampling config:** temperature=___ top_p=___ top_k=___

| Prompt version | run_id | Category acc | Severity acc | Routing acc | JSON valid | Retry rate | Notes |
|---|---|---|---|---|---|---|---|
| v1 | | | | | | | |
| v2 | | | | | | | |

**What changed between v1 and v2:** _______________________________________________

**Key finding from Experiment 4:** _______________________________________________

---

## Phase 4: Prompt Injection Sub-Evaluation

**Date run:** _______________
**Dataset:** adversarial_tickets.json (__ tickets)
**Sampling config:** temperature=___ top_p=___ top_k=___

### Per-Model Results

Run the adversarial set against each model. Record per-layer effectiveness.

**Model: Qwen 3.5 ___B**

| Attack category | # tickets | Guardrail blocked | Guardrail warned | Reached model | Model complied | Validation caught | End-to-end success (residual risk) |
|---|---|---|---|---|---|---|---|
| Direct injection | | | | | | | |
| Obfuscated injection | | | | | | | |
| Indirect (quoted content) | | | | | | | |
| PII triggers | | | | | | | |
| Hostile language | | | | | | | |
| Length extremes | | | | | | | |
| Multilingual | | | | | | | |
| **Totals** | | | | | | | |

(Duplicate this table for each model tested)

### Per-Rule Guardrail Hit Distribution

| Guardrail rule | Times triggered | On which attack categories |
|---|---|---|
| Injection phrase match | | |
| Base64 detection | | |
| Invisible Unicode | | |
| Character ratio anomaly | | |
| PII regex (credit card) | | |
| PII regex (SSN) | | |
| Length check | | |

### Residual Risk Summary

- **Total adversarial tickets:** ___
- **Blocked by guardrail:** ___ (___%)
- **Reached model but model resisted:** ___ (___%)
- **Model complied but validation caught:** ___ (___%)
- **End-to-end successful attacks (residual risk):** ___ (___%)

**Residual risk statement:** _______________________________________________

### Guardrail Iteration (if applicable)

Did any adversarial results prompt changes to the guardrail rules?

| Date | What changed | Why | Effect on re-run |
|---|---|---|---|
| | | | |
| | | | |

---

## Phase 5: Cost Analysis Data

Fill in from actual benchmark token counts. See `docs/cost-analysis.md` for the full template.

### Tokens Per Request (from Phase 3 experiments)

| Model | Avg tokens in | Avg tokens out | Avg total |
|---|---|---|---|
| Qwen 3.5 2B | | | |
| Qwen 3.5 4B | | | |
| Qwen 3.5 9B | | | |

### Hardware Cost

- **Machine purchase price:** $_______________
- **Amortized daily cost (3 years):** $_______________

### Hypothetical Cloud Break-Even

Using Qwen 3.5 Plus pricing ($0.26/M input, $1.56/M output):

- **Estimated cloud cost per request:** $_______________
- **Break-even daily volume:** _______________ tickets/day

---

## Cross-Platform Docker Testing (Phase 7)

| Platform | OS version | Ollama version | Docker version | Models pulled? | Container builds? | Container runs? | Triage works? | API works? | Notes |
|---|---|---|---|---|---|---|---|---|---|
| macOS (primary) | | | | ☐ | ☐ | ☐ | ☐ | ☐ | |
| Windows | | | | ☐ | ☐ | ☐ | ☐ | ☐ | |
| Linux (work laptop) | | | | ☐ | ☐ | ☐ | ☐ | ☐ | |

---

## Overall Project Completion Checklist

### Build phases
- ☐ Phase 0: Smoke test complete, model lineup confirmed
- ☐ Phase 1: Single happy-path slice working (native + Docker)
- ☐ Phase 2: Provider abstraction, multiple models, guardrail, retry
- ☐ Phase 3: Eval harness, labeled datasets, experiments run
- ☐ Phase 4: Adversarial evaluation, guardrail iteration
- ☐ Phase 5: Dashboard, traces, live monitoring
- ☐ Phase 6: Prompt v2, prompt comparison experiment
- ☐ Phase 7: Hardening, docs, deployment testing, presentation prep

### Rubric coverage
- ☐ Model running and producing meaningful outputs
- ☐ Evaluation dataset created and used
- ☐ Innovation demonstrated (prompt injection investigation)
- ☐ Deployed in production environment (local + Docker)
- ☐ Accessible via API endpoint (FastAPI + Swagger)
- ☐ Inference pipeline documented and optimized
- ☐ Sampling method documented with rationale
- ☐ Technical documentation comprehensive
- ☐ Demo rehearsed (at least twice)
- ☐ Presentation slides complete (6 max)

### Documentation deliverables
- ☐ PLAN.md current
- ☐ README.md current
- ☐ All ADRs written and indexed
- ☐ Decision log up to date
- ☐ architecture.md current
- ☐ evaluation-plan.md current
- ☐ threat-model.md current
- ☐ tradeoffs.md current
- ☐ cost-analysis.md populated with real data
- ☐ future-improvements.md current
- ☐ prompt-versions.md written
- ☐ DEPLOYMENT.md written and tested
- ☐ demo-script.md written
- ☐ presentation-notes.md written
