# Evaluation Checklist

A working document for logging results as each phase produces data. Fill in as you go — this is a living record, not a planning document.

---

## Phase 0: Smoke Test

**Date started:** _______________
**Ollama version:** _______________
**Hardware:** MacBook Pro M4 Pro, 24GB unified memory
**macOS version:** _______________

### Model Pull Verification

| Model | Pull command | Size on disk | Pull successful? | Notes |
|---|---|---|---|---|
| Qwen 3.5 2B | `ollama pull qwen3.5:2b` | | ☐ Yes ☐ No | |
| Qwen 3.5 4B | `ollama pull qwen3.5:4b` | | ☐ Yes ☐ No | |
| Qwen 3.5 9B | `ollama pull qwen3.5:9b` | | ☐ Yes ☐ No | |

### MLX Acceleration Check

Run each model with `OLLAMA_MLX=1 ollama run <model> --verbose` and note whether MLX is engaged:

| Model | MLX engaged? | Prefill tokens/s | Decode tokens/s | Notes |
|---|---|---|---|---|
| Qwen 3.5 2B | ☐ Yes ☐ No ☐ Unknown | | | |
| Qwen 3.5 4B | ☐ Yes ☐ No ☐ Unknown | | | |
| Qwen 3.5 9B | ☐ Yes ☐ No ☐ Unknown | | | |

### Structured Output Smoke Test

Send 2–3 sample tickets to each model with a throwaway triage prompt. Record whether the model can produce JSON that roughly matches the expected schema.

**Sample ticket 1:** _______________________________________________

| Model | Valid JSON? | Correct fields? | Reasonable values? | Latency | Notes |
|---|---|---|---|---|---|
| Qwen 3.5 2B | ☐ Yes ☐ No | ☐ Yes ☐ Partial ☐ No | ☐ Yes ☐ No | | |
| Qwen 3.5 4B | ☐ Yes ☐ No | ☐ Yes ☐ Partial ☐ No | ☐ Yes ☐ No | | |
| Qwen 3.5 9B | ☐ Yes ☐ No | ☐ Yes ☐ Partial ☐ No | ☐ Yes ☐ No | | |

**Sample ticket 2:** _______________________________________________

| Model | Valid JSON? | Correct fields? | Reasonable values? | Latency | Notes |
|---|---|---|---|---|---|
| Qwen 3.5 2B | ☐ Yes ☐ No | ☐ Yes ☐ Partial ☐ No | ☐ Yes ☐ No | | |
| Qwen 3.5 4B | ☐ Yes ☐ No | ☐ Yes ☐ Partial ☐ No | ☐ Yes ☐ No | | |
| Qwen 3.5 9B | ☐ Yes ☐ No | ☐ Yes ☐ Partial ☐ No | ☐ Yes ☐ No | | |

**Sample ticket 3 (optional):** _______________________________________________

| Model | Valid JSON? | Correct fields? | Reasonable values? | Latency | Notes |
|---|---|---|---|---|---|
| Qwen 3.5 2B | ☐ Yes ☐ No | ☐ Yes ☐ Partial ☐ No | ☐ Yes ☐ No | | |
| Qwen 3.5 4B | ☐ Yes ☐ No | ☐ Yes ☐ Partial ☐ No | ☐ Yes ☐ No | | |
| Qwen 3.5 9B | ☐ Yes ☐ No | ☐ Yes ☐ Partial ☐ No | ☐ Yes ☐ No | | |

### Phase 0 Decision

- ☐ 2B stays in the comparison — can produce structured output
- ☐ 2B dropped from the comparison — reason: _______________________________
- ☐ Final model lineup confirmed: _______________________________
- ☐ Decision log entry written

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
