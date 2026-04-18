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

| Model       | Pull command             | Size on disk | Pull successful? | Notes                                                                                                                                                                     |
| ----------- | ------------------------ | ------------ | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Qwen 3.5 2B | `ollama pull qwen3.5:2b` | 2.7 GB       | ☒ Yes            | Q8_0 quantization; 2.3B params; 262K ctx.                                                                                                                                 |
| Qwen 3.5 4B | `ollama pull qwen3.5:4b` | 3.4 GB       | ☒ Yes            | Q4_K_M quantization; 4.7B params; 262K ctx.                                                                                                                               |
| Qwen 3.5 9B | `ollama pull qwen3.5:9b` | 6.6 GB       | ☒ Yes            | Q4_K_M quantization; 9.7B params; 262K ctx. Pulled as `qwen3.5:latest` and aliased locally via `ollama cp qwen3.5:latest qwen3.5:9b` to match the tag the runner expects. |

### MLX Acceleration Check

Checked with `OLLAMA_MLX=1 ollama run <model> --verbose` on a throwaway "say hi as JSON" prompt. Decode rates are well below what MLX kernels would deliver on M4 Pro for this architecture, so MLX is treated as **not engaged** for the `qwen35` architecture in Ollama 0.20.7. Apple Metal (GGML) is the active backend.

| Model       | MLX engaged? | Prefill tokens/s | Decode tokens/s | Notes                                                                                                                                                                                                                 |
| ----------- | ------------ | ---------------- | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Qwen 3.5 2B | ☒ No         | 40.95            | 61.72           | Backend: Metal GGML. Decode much lower than MLX-accelerated Qwen3/Mistral builds on same hardware. Reasoning mode produced 2720 eval tokens for a trivial prompt — consistent with thinking-mode being on by default. |
| Qwen 3.5 4B | ☒ No         | 36.21            | 36.03           | Metal GGML. Latency dominated by parameter count, as expected without MLX.                                                                                                                                            |
| Qwen 3.5 9B | ☒ No         | 10.47            | 26.73           | Metal GGML. Still comfortably fits in 24 GB unified memory alongside IDE + app.                                                                                                                                       |

**Takeaway:** MLX coverage for the `qwen35` architecture has not landed in Ollama 0.20.7, so planning must assume Metal GGML performance. If a later Ollama release adds MLX for this family, the benchmarks should be rerun — latency numbers will likely improve meaningfully.

### Structured Output Smoke Test

Sent 3 sample tickets (`n-004` outage, `n-007` billing, `n-003` feature request) to each model via the OpenAI-compatible endpoint (`http://localhost:11434/v1`) using the runner's single throwaway triage prompt. "Correct fields" = all 8 required keys present, no extras. "Reasonable values" = parsed `category` and `severity` matched expected ground truth.

**Sample ticket 1:** n-004 — *URGENT: Complete service outage* (expected: category=outage, severity=critical, routingTeam=infra, escalation=true)

| Model       | Valid JSON? | Correct fields? | Reasonable values? | Latency | Notes                                                                                                                                                 |
| ----------- | ----------- | --------------- | ------------------ | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Qwen 3.5 2B | ☒ Yes       | ☒ Yes           | ☒ Yes              | 43.55s  | confidence 0.95; escalation=true; 2451 completion tokens (reasoning mode verbose).                                                                    |
| Qwen 3.5 4B | ☒ Yes       | ☒ Yes           | ☒ Yes              | 49.73s  | confidence 0.95; escalation=true; 1575 completion tokens. Tightest summary of the three.                                                              |
| Qwen 3.5 9B | ☒ Yes       | ☒ Yes           | ☒ Yes              | 84.92s  | confidence 0.98; escalation=true; 1772 completion tokens. Most professional draftReply. First run after model load — subsequent requests were faster. |

**Sample ticket 2:** n-007 — *Billing discrepancy on latest invoice* (expected: category=billing, severity=medium, routingTeam=billing, escalation=false)

| Model       | Valid JSON? | Correct fields? | Reasonable values? | Latency | Notes                                                                                                                                                                                                                                                           |
| ----------- | ----------- | --------------- | ------------------ | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Qwen 3.5 2B | ☒ Yes       | ☒ Yes           | ☒ Yes              | 652.16s | **Outlier.** confidence 0.9; 3138 completion tokens. The 2B ran away in reasoning mode before emitting the final JSON. JSON itself was clean — latency was the failure, not correctness. Phase 1+ must apply a completion-token cap or a provider-side timeout. |
| Qwen 3.5 4B | ☒ Yes       | ☒ Yes           | ☒ Yes              | 52.11s  | confidence 0.95; 1776 completion tokens.                                                                                                                                                                                                                        |
| Qwen 3.5 9B | ☒ Yes       | ☒ Yes           | ☒ Yes              | 45.01s  | confidence 0.95; 1097 completion tokens. Most token-efficient on this ticket.                                                                                                                                                                                   |

**Sample ticket 3:** n-003 — *Feature request: Dark mode for mobile app* (expected: category=feature_request, severity=low, routingTeam=product, escalation=false)

| Model       | Valid JSON? | Correct fields? | Reasonable values? | Latency | Notes                                                         |
| ----------- | ----------- | --------------- | ------------------ | ------- | ------------------------------------------------------------- |
| Qwen 3.5 2B | ☒ Yes       | ☒ Yes           | ☒ Yes              | 42.24s  | confidence 0.9; 2521 completion tokens.                       |
| Qwen 3.5 4B | ☒ Yes       | ☒ Yes           | ☒ Yes              | 35.67s  | confidence 0.95; 1143 completion tokens. Fastest run overall. |
| Qwen 3.5 9B | ☒ Yes       | ☒ Yes           | ☒ Yes              | 47.04s  | confidence 1.00; 1195 completion tokens.                      |

**Aggregate:** All three models hit 100% valid JSON, 100% fields present, and 100% correct-values on the 3-ticket sample. No malformed outputs, no missing fields, no wrong categories or severities.

### Phase 0 Decision

- ☒ 2B stays in the comparison — can produce structured output. 3/3 valid JSON, 3/3 correct fields, 3/3 correct values. Known risk to manage in Phase 1+: reasoning-mode over-generation can spike latency (observed 652s on a routine billing ticket). The retry policy and completion-token caps handle this; the model itself is not the problem.
- ☒ 4B stays in the comparison — 3/3 valid JSON, 3/3 correct fields, 3/3 correct values; 35–52s latency band with stable token counts.
- ☒ 9B stays in the comparison — 3/3 valid JSON, 3/3 correct fields, 3/3 correct values; 45–85s latency band (first-call warmup accounts for the high end).
- ☒ Final model lineup confirmed: **Qwen 3.5 2B, 4B, 9B** — all three kept for the Phase 3 size-comparison experiment.
- ☒ Decision log entry written — see `docs/decisions/decision-log.md` (2026-04-16 Phase 0 entry).

### Phase 0 Observations

Analytical findings from the smoke test data. These inform Phase 1+ implementation decisions.

**1. Token consumption inversion.** The 2B uses the most completion tokens per request, not the fewest. Average completion tokens across the 3-ticket sample: 2B ~2,703 / 4B ~1,498 / 9B ~1,355. The visible JSON output is ~150 tokens in all cases — the remainder is consumed by internal reasoning. The smaller model does more "thinking" to arrive at the same correct answer.

**2. Thinking mode appears engaged despite defaults.** Unsloth documentation states that reasoning is disabled by default for Qwen 3.5 small models (0.8B–9B). However, the token counts from the smoke test strongly suggest thinking mode is active in Ollama 0.20.7. There is an open GitHub issue (ollama/ollama#14617) reporting that `/no_think` is ineffective for Qwen 3.5. The provider implementation must investigate `think=false` via the native ollama API and/or `/no_think` prompt tags as a potential fix.

**3. Reasoning runaway is a production reliability risk.** The 2B took 652 seconds on ticket n-007 (a routine billing inquiry) due to 3,138 completion tokens of reasoning before emitting the final JSON. The JSON itself was correct — the failure is latency, not quality. The provider implementation must apply a completion token cap (`max_tokens`) and/or a provider-side timeout. Before implementing the cap, verify whether `max_tokens` counts thinking tokens or only visible output — if it counts both, a low cap could truncate the response before the JSON is emitted.

**4. Cost analysis implication.** The assumption that smaller models are cheaper per request does not hold if token consumption inverts. Cost projections in `docs/cost-analysis.md` must use actual measured tokens-per-request from the Phase 3 benchmarks, not estimates derived from model size alone.

**5. Quality differentiation is subtle at this sample size.** All three models achieved 100% accuracy on category, severity, routing, and escalation across 3 tickets. Quality differences — summary precision, draft reply professionalism, confidence calibration — are visible but not measurable at n=3. The Phase 3 evaluation on 35 tickets will provide enough data to characterize quality differences meaningfully.

**6. Quantization levels differ across model sizes.** The 2B uses Q8_0 (8-bit) quantization while the 4B and 9B use Q4_K_M (4-bit). This is a confound in the size comparison: the 2B carries more precision per parameter than the larger models. Differences in structured-output reliability between the 2B and the others cannot be attributed purely to parameter count — the quantization scheme is also a variable. Ollama does not offer a Q4_K_M variant for the 2B or a Q8_0 variant for the larger sizes, so this confound cannot be controlled within the current toolchain.

---

## Sampling Configuration Log

### Baseline Configuration

| Parameter          | Planned value  | Actual value used | Notes                                                        |
| ------------------ | -------------- | ----------------- | ------------------------------------------------------------ |
| Temperature        | 0.2            | 0.2               | Locked 2026-04-16 — see decision log. Set in `config.py`.   |
| Top-p              | 0.9            | 0.9               | Locked 2026-04-16 — see decision log. Set in `config.py`.   |
| Top-k              | 40             | 40                | Set in `config.py`, passed via `extra_body` to Ollama.       |
| Repetition penalty | 1.0 (disabled) | 1.0               | Set in `config.py`, passed via `extra_body` to Ollama.       |

### Sampling Observations During Development

Log any observations about how sampling settings affect output quality as you encounter them:

| Date | Model | Parameter changed | From → To | Observed effect | Keep change? |
| ---- | ----- | ----------------- | --------- | --------------- | ------------ |
| — | — | None | — | No sampling parameter changes made through Phase 3. Baseline values (temperature=0.2, top_p=0.9, top_k=40, repetition_penalty=1.0) used unchanged across Phase 0 smoke test and all Phase 1–3 development. | N/A |
|      |       |                   |           |                 |              |
|      |       |                   |           |                 |              |

### Sampling Experiment (if time permits)

If time allows during or after Phase 3, test 2–3 temperature settings on the same model with the same dataset:

| Model | Temperature  | JSON validity rate | Task accuracy | Avg latency | Notes |
| ----- | ------------ | ------------------ | ------------- | ----------- | ----- |
|       | 0.0 (greedy) |                    |               |             |       |
|       | 0.2          |                    |               |             |       |
|       | 0.5          |                    |               |             |       |
|       | 0.8          |                    |               |             |       |

**Finding:** _______________________________________________

---

## Phase 3: Experiment Execution Log

### Experiment 1: Model Size Comparison

**Date run:** 2026-04-18
**Dataset:** normal_set.jsonl (35 tickets)
**Prompt version:** v1
**Sampling config:** temperature=0.2 top_p=0.9 top_k=40

| Model       | run_id | Category acc | Severity acc | Routing acc | JSON valid | Retry rate | Avg latency | p95 latency | Tokens/s | Notes |
| ----------- | ------ | ------------ | ------------ | ----------- | ---------- | ---------- | ----------- | ----------- | -------- | ----- |
| Qwen 3.5 2B | e1-2b-20260418T0103 | 2.9% | 0.0% | 2.9% | 2.9% | 97.1% | 69,077ms | 72,005ms | 58.4 | 1/35 successful. Q8_0 quant. Reasoning mode produces ~4,031 output tokens/req but almost never valid JSON. |
| Qwen 3.5 4B | e1-4b-20260418T0103 | 57.1% | 51.4% | 57.1% | 82.9% | 42.9% | 73,886ms | 129,101ms | 32.0 | 29/35 successful. Q4_K_M quant. Best accuracy and reliability of the three. |
| Qwen 3.5 9B | e1-9b-20260418T0103 | 54.3% | 48.6% | 54.3% | 74.3% | 51.4% | 107,012ms | 168,789ms | 24.3 | 26/35 successful. Q4_K_M quant. Slower and less reliable than 4B despite more parameters. |

**Key finding from Experiment 1:** The 4B is the best performer across all metrics — higher accuracy, better JSON validity, faster, and more successful retries than the 9B. The 2B is essentially unusable for structured output (1/35 success rate). Bigger is not better in this setup: the 9B's longer reasoning chains produce more malformed output than the 4B's.

**Limitation:** The 2B uses Q8_0 quantization while the 4B and 9B use Q4_K_M. The 2B's poor structured-output performance cannot be attributed solely to parameter count — the different quantization scheme is a confound. See Phase 0 Observation #6.

#### Experiment 1 Observations

**1. Unexpected finding: the 2B collapsed at scale.** Phase 0 showed the 2B producing 3/3 valid JSON on the smoke test. At n=35, it succeeded on only 1 ticket (2.9%). The difference is not sampling noise — the 2B's reasoning mode generates ~4,031 output tokens per request, almost all consumed by internal chain-of-thought, and the final JSON is malformed in 97% of cases. The `max_tokens=2048` cap introduced in Phase 1 appears insufficient to contain the reasoning overflow while still leaving room for the actual JSON output.

**2. Pattern: the quality-size curve is non-monotonic.** The 4B outperforms the 9B on every metric — category accuracy (57.1% vs 54.3%), JSON validity (82.9% vs 74.3%), retry rate (42.9% vs 51.4%), and latency (74s vs 107s). This inverts the naive expectation that more parameters = better quality. The likely explanation: the 9B's longer reasoning chains have more opportunities to produce structurally invalid output, and the repair prompt cannot recover them as reliably.

**3. Implementation implication: the 2B is not viable as a demo default.** With a 2.9% success rate, it cannot be the primary model. However, the default model decision (OD-4) remains open until E2 and E3 results determine whether engineering controls change the ranking between the 4B and 9B. The 2B stays in the dropdown for the size-comparison story — showing the failure mode is itself a finding.

**4. Cost implication: token consumption inversion confirmed at scale.** The 2B uses 4,951 tokens/request, the 4B uses 3,098, and the 9B uses 3,378. The Phase 0 observation (#4) that smaller models are not cheaper per request is now confirmed on the full 35-ticket dataset. Cloud cost projections must use actual token counts, not parameter-count proxies.

**5. Limitation: 57% category accuracy across all models suggests prompt v1 needs iteration.** Even the best model (4B) only matches ground truth on category 57% of the time. This could reflect genuine ambiguity in the dataset labels, a prompt that doesn't constrain the taxonomy tightly enough, or both. Phase 6 (prompt v2) is the designed mechanism to test this. The accuracy numbers should not be compared to production NLP systems evaluated on thousands of samples — at n=35, individual ticket disagreements move the needle by ~3% each.

### Experiment 2: Model Size vs Engineering Controls

**Date run:** 2026-04-18
**Dataset:** normal_set.jsonl (35 tickets)
**Prompt version:** v1
**Sampling config:** temperature=0.2 top_p=0.9 top_k=40

| Configuration                    | run_id | Category acc | Severity acc | Routing acc | JSON valid | Retry rate | Avg latency | Notes |
| -------------------------------- | ------ | ------------ | ------------ | ----------- | ---------- | ---------- | ----------- | ----- |
| Smallest model + full validation (2B) | e1-2b-20260418T0103 | 2.9% | 0.0% | 2.9% | 2.9% | 97.1% | 69,077ms | 1/35 successful. From E1 data. 2B is broken regardless of controls. |
| Largest model + no validation (9B) | e2-9b-noval-20260418T0332 | 48.6% | 40.0% | 48.6% | 48.6% | 0% | 70,252ms | 17/35 successful. Without validation, nearly half of outputs are usable. |

**Key finding from Experiment 2:** The 9B without validation (17/35) massively outperforms the 2B with full validation (1/35). However, this result is confounded by the 2B's fundamental inability to produce structured output — the 2B fails before validation has anything to work with. The E2 comparison as designed does not cleanly test the thesis because the "smallest viable model" turned out to be non-viable.

**Does this support or contradict the project thesis?** Inconclusive as designed. The more informative comparison is 4B-with-validation (29/35, from E3) vs 9B-without-validation (17/35, from E2): a mid-size model with controls outperforms a larger model without them. This supports the thesis that engineering controls compensate for model size — but only when the baseline model can produce structured output at all.

#### Experiment 2 Observations

**1. Unexpected finding: E2 as designed is confounded.** The experiment intended to compare "smallest model + controls" vs "largest model - controls" to test whether engineering controls can compensate for model size. But the 2B's 2.9% success rate means controls have nothing to rescue — the model fails at the JSON generation level, not the validation level. The comparison is between "broken" and "partially working," not between "small+controlled" and "large+uncontrolled."

**2. Pattern: the informative comparison crosses E2 and E3.** Comparing the 4B-validated (29/35, 57.1% category acc from E3) against the 9B-no-validation (17/35, 48.6% category acc from E2) provides the test the thesis needs: a smaller model with controls beats a larger model without them on both coverage (83% vs 49%) and accuracy (57% vs 49%).

**3. Implementation implication: E2 should be reframed in the presentation.** Rather than presenting the 2B vs 9B comparison (which is uninteresting because the 2B is broken), the thesis-supporting comparison is 4B-validated vs 9B-unvalidated. This is more honest and more compelling.

### Experiment 3: Validation Impact

**Date run:** 2026-04-18
**Model:** Qwen 3.5 4B
**Dataset:** normal_set.jsonl (35 tickets)
**Prompt version:** v1
**Sampling config:** temperature=0.2 top_p=0.9 top_k=40

| Configuration           | run_id | Category acc | Severity acc | Routing acc | JSON valid | Retry rate | Retries that recovered | Avg latency | Notes |
| ----------------------- | ------ | ------------ | ------------ | ----------- | ---------- | ---------- | ---------------------- | ----------- | ----- |
| Full validation + retry | e3-4b-validated-20260418T0332 | 57.1% | 48.6% | 54.3% | 82.9% | 40.0% | 57.1% (8/14 retried) | 69,889ms | 29/35 successful. Retry recovered 8 tickets that would have failed. |
| No validation, no retry | e3-4b-skipped-20260418T0332 | 62.9% | 48.6% | 60.0% | 65.7% | 0% | N/A | 49,909ms | 23/35 successful. Higher per-ticket accuracy but fewer usable tickets. |

**Key finding from Experiment 3:** Validation + retry increases coverage from 23/35 to 29/35 (6 additional successful tickets). However, accuracy *per successful ticket* is slightly higher without validation — the tickets that need retry tend to produce lower-accuracy outputs on the second attempt. The net effect: validation buys reliability (more tickets triaged) at the cost of ~20s additional latency per request from retries.

**Percentage of cases where retry recovered a failure:** 57.1% (8 of 14 retried tickets succeeded on the repair attempt)

#### Experiment 3 Observations

**1. Unexpected finding: accuracy is higher without validation.** Category accuracy is 62.9% without validation vs 57.1% with it. This is counterintuitive — validation should not reduce accuracy. The explanation: retried tickets that succeed on the repair prompt tend to produce lower-quality classifications (the model is correcting its JSON format, not improving its reasoning). The 6 recovered tickets dilute the accuracy average.

**2. Pattern: validation's value is coverage, not accuracy.** The pipeline with validation triages 29/35 tickets vs 23/35 without. That's 6 additional tickets that would have been dropped as failures. In a production triage system, a ticket that gets a mediocre classification is better than a ticket that gets no classification at all. The accuracy difference (57% vs 63%) is within the noise band at n=35 (~3% per ticket).

**3. Cost implication: validation adds latency but not proportionally.** Average latency is 70s with validation vs 50s without — a 40% increase. But this includes the 40% of requests that triggered a retry (each roughly doubling that request's latency). For the 60% of requests that pass on the first attempt, validation adds negligible overhead.

**4. Implementation implication: validation should remain on by default.** The coverage gain (6 additional tickets) outweighs the accuracy dilution and latency cost. The accuracy difference is not statistically meaningful at this sample size. For the demo, the "retries that recovered" stat (57.1%) is the headline number — it directly demonstrates the value of the engineering control.

**5. Limitation: the "no validation" mode still parses and schema-checks.** `skip_validation=True` bypasses `validate_or_retry()` but still does a best-effort `parse_json()` + `validate_schema()` for recording purposes. Tickets that fail parsing are counted as failures. A true "raw model output" mode (no parsing at all) would show even lower success rates for the unvalidated path.

### Experiment 4: Prompt Comparison

**Date run:** _______________
**Model:** _______________
**Dataset:** gold_tickets.json (__ tickets)
**Sampling config:** temperature=___ top_p=___ top_k=___

| Prompt version | run_id | Category acc | Severity acc | Routing acc | JSON valid | Retry rate | Notes |
| -------------- | ------ | ------------ | ------------ | ----------- | ---------- | ---------- | ----- |
| v1             |        |              |              |             |            |            |       |
| v2             |        |              |              |             |            |            |       |

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

| Attack category           | # tickets | Guardrail blocked | Guardrail warned | Reached model | Model complied | Validation caught | End-to-end success (residual risk) |
| ------------------------- | --------- | ----------------- | ---------------- | ------------- | -------------- | ----------------- | ---------------------------------- |
| Direct injection          |           |                   |                  |               |                |                   |                                    |
| Obfuscated injection      |           |                   |                  |               |                |                   |                                    |
| Indirect (quoted content) |           |                   |                  |               |                |                   |                                    |
| PII triggers              |           |                   |                  |               |                |                   |                                    |
| Hostile language          |           |                   |                  |               |                |                   |                                    |
| Length extremes           |           |                   |                  |               |                |                   |                                    |
| Multilingual              |           |                   |                  |               |                |                   |                                    |
| **Totals**                |           |                   |                  |               |                |                   |                                    |

(Duplicate this table for each model tested)

### Per-Rule Guardrail Hit Distribution

| Guardrail rule          | Times triggered | On which attack categories |
| ----------------------- | --------------- | -------------------------- |
| Injection phrase match  |                 |                            |
| Base64 detection        |                 |                            |
| Invisible Unicode       |                 |                            |
| Character ratio anomaly |                 |                            |
| PII regex (credit card) |                 |                            |
| PII regex (SSN)         |                 |                            |
| Length check            |                 |                            |

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
| ---- | ------------ | --- | ---------------- |
|      |              |     |                  |
|      |              |     |                  |

---

## Phase 5: Cost Analysis Data

Fill in from actual benchmark token counts. See `docs/cost-analysis.md` for the full template.

### Tokens Per Request (from Phase 3 experiments)

| Model       | Avg tokens in | Avg tokens out | Avg total |
| ----------- | ------------- | -------------- | --------- |
| Qwen 3.5 2B | 920           | 4,031          | 4,951     |
| Qwen 3.5 4B | 729           | 2,369          | 3,098     |
| Qwen 3.5 9B | 765           | 2,612          | 3,378     |

### Hardware Cost

- **Machine purchase price:** $_______________
- **Amortized daily cost (3 years):** $_______________

### Hypothetical Cloud Break-Even

Using Qwen 3.5 Plus pricing ($0.26/M input, $1.56/M output):

- **Estimated cloud cost per request:** $_______________
- **Break-even daily volume:** _______________ tickets/day

---

## Cross-Platform Docker Testing (Phase 7)

| Platform            | OS version | Ollama version | Docker version | Models pulled? | Container builds? | Container runs? | Triage works? | API works? | Notes |
| ------------------- | ---------- | -------------- | -------------- | -------------- | ----------------- | --------------- | ------------- | ---------- | ----- |
| macOS (primary)     |            |                |                | ☐              | ☐                 | ☐               | ☐             | ☐          |       |
| Windows             |            |                |                | ☐              | ☐                 | ☐               | ☐             | ☐          |       |
| Linux (work laptop) |            |                |                | ☐              | ☐                 | ☐               | ☐             | ☐          |       |

---

## Overall Project Completion Checklist

### Build phases
- ☒ Phase 0: Smoke test complete, model lineup confirmed
- ☒ Phase 1: Single happy-path slice working (native + Docker)
- ☒ Phase 2: Provider abstraction, multiple models, guardrail, retry
- ☒ Phase 3: Eval harness, labeled datasets, experiments run
- ☐ Phase 4: Adversarial evaluation, guardrail iteration
- ☐ Phase 5: Dashboard, traces, live monitoring
- ☐ Phase 6: Prompt v2, prompt comparison experiment
- ☐ Phase 7: Hardening, docs, deployment testing, presentation prep

### Rubric coverage
- ☒ Model running and producing meaningful outputs
- ☒ Evaluation dataset created and used
- ☐ Innovation demonstrated (prompt injection investigation) — Phase 4
- ☒ Deployed in production environment (local + Docker)
- ☒ Accessible via API endpoint (FastAPI + Swagger)
- ☒ Inference pipeline documented and optimized
- ☒ Sampling method documented with rationale
- ☐ Technical documentation comprehensive — Phase 7
- ☐ Demo rehearsed (at least twice) — Phase 7
- ☐ Presentation slides complete (6 max) — Phase 7

### Documentation deliverables
- ☒ PLAN.md current
- ☒ README.md current
- ☒ All ADRs written and indexed
- ☒ Decision log up to date
- ☒ architecture.md current
- ☒ evaluation-plan.md current
- ☒ threat-model.md current
- ☒ tradeoffs.md current
- ☐ cost-analysis.md populated with real data — token data filled, costs pending
- ☒ future-improvements.md current
- ☐ prompt-versions.md written — Phase 6
- ☐ DEPLOYMENT.md written and tested — Phase 7
- ☐ demo-script.md written
- ☐ presentation-notes.md written
