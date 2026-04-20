# Decision Log

A chronological log of scope, framing, and strategy decisions for `ticket-triage-llm`.

This is not the place for architectural decisions — those belong in [ADRs](../adr/). This is the place for *what the project is, isn't, and why*: scope boundaries, things considered and rejected, framing choices, and the reasoning trail behind them.

Newest entries at the top.

---

## 2026-04-19 — ADR framing retrospective: rubric-driven justification pattern

**Decision:** Documented a framing pattern across early ADRs (0001-0003, 0005-0007, 0009, 0010) where decisions are justified partly by citing rubric criteria, grading tiers, or instructor expectations rather than standing on independent engineering reasoning. The decisions themselves are sound — in every case the underlying technical driver would justify the choice without a rubric. The articulation would be sharper today.

See [ADR 0012](../adr/0012-adr-framing-retrospective.md) for the full inventory and the corrected framing principle for future ADRs.

---

## 2026-04-19 — Phase 6 skipped: prompt v2 comparison deferred

**Decision:** Phase 6 (prompt v2 authoring + E4 v1-vs-v2 comparison) is not executed in this project iteration. The E4 experiment remains declared complete with v1-only results. `src/ticket_triage_llm/prompts/triage_v2.py` (a stub file containing only a docstring) is deleted. Time budget redirects to Phase 7 deliverables.

This is a scope decision, not a slipped deliverable.

**Original Phase 6 goal:** Author a meaningfully different prompt v2 and run E4 to quantify how much prompt design contributes vs. model selection. The question was "how much does a careful prompt buy you, holding model and pipeline constant?"

**Why skip:**

1. **Reliability saturated.** Phase 3 replication (n=5, production config) showed all three models (2B, 4B, 9B) produce 100% JSON validity on the 35-ticket normal set. First-pass validity is ~100%; retry rate is ~0–3%. A v2 prompt cannot improve reliability because there's no reliability headroom left to measure. The v1 prompt is already doing its structural job across the size range.

2. **The measurement v2 would produce is narrower than planned.** The original Phase 6 motivation (`docs/PLAN.md` § Project Thesis, "how much does prompt design buy you?") was framed when JSON validity was 82.9% on the 4B and 74.3% on the 9B under the original configuration. Under production config, the question collapses from "validity + accuracy" to "accuracy only" — a ~3 percentage-point range between the 4B (80.6%) and 9B (83.4%) category accuracy. A v2 comparison would measure headroom inside that narrow band, not the structural reliability question the phase was designed to answer.

3. **Remaining time produces more value elsewhere.** Phase 7 deliverables (DEPLOYMENT.md, cross-platform notes, cost-analysis completion, README model-management documentation, cloud-model path documentation, demo materials, ADR addenda reflecting Phase 4/5/E5 findings) are visible deliverables that a reviewer will evaluate directly. Writing v2 and running a comparison that's bounded by the 2.8pp gap between 4B and 9B is less visible value per unit time.

4. **The question isn't permanently closed.** If category accuracy (~83% on the 9B) becomes the bottleneck in any future scenario, v2 authoring + comparison is a clean ~1-2 day workstream. Added to `docs/future-improvements.md` with the same "What / Why deferred / What was done instead / Effort" template as other deferred items.

**What was done instead (this branch):**

- Phase 7 execution: hardening, documentation, demo materials. See the Phase 7 SUMMARY.md entry for the full list.
- Reconciliation of ~14 stale Phase-6 references across `README.md`, `CLAUDE.md`, `TODO.md`, `PLAN.md`, `docs/evaluation-plan.md`, `docs/evaluation-checklist.md`, and `src/ticket_triage_llm/eval/runners/run_prompt_comparison.py`. Stale references would have misled future readers (and future Claude sessions) into thinking v2 was still an active workstream.
- `docs/future-improvements.md` gains a "Prompt v2 comparison" section.

**E4 status update:** E4 is declared complete, v1 only. The comparison dimension (v1 vs v2) is reduced to a one-value dataset; the experiment's measured deliverable becomes "v1 baseline metrics per model" rather than "v1 vs v2 delta." `docs/evaluation-checklist.md` and `docs/evaluation-plan.md` are updated to reflect this framing.

**Honest acknowledgement:** The original rubric (archived at `docs/archive/Final Project Rubric.docx`) and PLAN.md listed four experiments. With Phase 6 skipped, only three experiments have a full dataset (E1 size comparison, E2 size-vs-controls composed from E1/E3, E3 validation impact). E4 has a partial dataset (v1 only, no v2). This reduces the breadth of the prompt-comparison story and should be acknowledged in the presentation — the point to make is that reliability saturation under production config made the original v1-vs-v2 framing less informative than it was designed to be, not that the work ran out of time.

**References:** This decision was made after Phase 4 replication (n=5), E5 reasoning-mode experiment, and OD-4 re-resolution landed. The accumulated evidence from the Phase 3 replication (commits `749bd81`..`f394f54`) is what makes "reliability saturated" a defensible claim.

---

## 2026-04-19 — OD-4 re-resolved: Qwen 3.5 9B is the default demo model (supersedes 4B)

**Decision:** The default model loaded when the Triage tab opens is now **Qwen 3.5 9B** (`qwen3.5:9b`). This supersedes the [2026-04-18 OD-4 resolution](#2026-04-18--od-4-resolved-qwen-35-4b-is-the-default-demo-model), which selected the 4B based on n=1 Phase 3 data collected under `think=true` / `num_ctx=4096`. That data has since been superseded by the Phase 3 replication (n=5, production config) — see [2026-04-19 Phase 3 replication supersedes single-run claims](#2026-04-19--phase-3-replication-supersedes-single-run-claims).

The 4B ADR ([ADR 0011](../adr/0011-default-model-selection.md)) is not modified — ADRs are historical records of decisions as they were made. ADR 0011 now captures the reasoning behind the n=1 4B selection; this decision-log entry captures the reasoning behind the n=5 9B re-selection. Future readers should treat ADR 0011 as superseded by this entry.

**Evidence from Phase 3 replication (n=5, `think=false`, `num_ctx=16384`, 35 normal tickets, prompt v1):**

| Metric              | Qwen 3.5 2B   | Qwen 3.5 4B   | Qwen 3.5 9B   |
| ------------------- | ------------- | ------------- | ------------- |
| Category accuracy   | 74.9%         | 80.6%         | **83.4%**     |
| Severity accuracy   | ~62%          | ~74%          | **~76%**      |
| Escalation accuracy | ~77%          | ~82%          | **~85%**      |
| JSON validity       | 100%          | 100%          | 100%          |
| First-pass validity | ~100%         | ~100%         | ~100%         |
| Accuracy stddev     | ≤ 5%          | ≤ 5%          | ≤ 5%          |

**Evidence from Phase 4 replication (n=5, `think=false`, `num_ctx=16384`, 14 adversarial tickets + 35 normal tickets for FP baseline):**

| Metric                         | Qwen 3.5 2B  | Qwen 3.5 4B  | Qwen 3.5 9B  |
| ------------------------------ | ------------ | ------------ | ------------ |
| Residual risk (mean / 14)      | 5.4 ± 0.49   | 1.2 ± 0.40   | **1.0 ± 0.0** |
| Residual-risk reproducibility  | unstable     | unstable     | **stddev=0** |
| Parse failures                 | 0            | 0            | 0            |
| False-positive guardrail rate  | 0%           | 0%           | 0%           |
| Only reproducible vulnerability | 5-6 tickets | 1-2 tickets | **1 ticket (a-009)** |

**Evidence from E5 replication (n=3 think-on, n=2 think-off, 9B only, adversarial set):**

| Metric                    | think=off         | think=on           |
| ------------------------- | ----------------- | ------------------ |
| Residual risk             | 1.0 ± 0.0         | 0.0 ± 0.0          |
| Model complied            | 1.0 ± 0.0         | 0.67 ± 0.47        |
| Needs manual review       | 1.0 ± 0.0         | 4.0 ± 2.16         |
| Per-triage latency        | ~7 s              | ~121 s             |
| Per-triage output tokens  | ~162              | ~2,913             |
| New compliance tickets    | 0                 | 1 (a-014, 2/3 runs) |

**Why the 9B, not the 4B:**

1. **Highest category accuracy.** 83.4% vs 80.6% vs 74.9%. With all three models producing 100% JSON validity under production config, category accuracy is the primary differentiator. The 9B wins on the primary metric by ~3 percentage points over the 4B and ~8.5 percentage points over the 2B.

2. **Best adversarial resistance.** 1.0 compromised out of 14 adversarial tickets with stddev=0 across 5 runs. The 4B has 1.2 ± 0.40 (less reproducible, more exposure to a-009 and partial compromise on a-008). The 2B has 5.4 ± 0.49 (substantially worse). On the a-008 indirect-injection attack that bypasses the guardrail by design, the 9B resists 5/5 runs while the 4B complies 5/5 runs — the single most important ticket-level difference.

3. **Highest reproducibility.** Adversarial residual risk stddev=0 across 5 runs. The 9B's adversarial behavior is deterministic: the one ticket it compromises (a-009) is the same ticket every run, and the 13 it resists are the same 13 every run. This is a production-relevant property — a-009 becomes a known-and-documented vulnerability rather than an intermittent mystery.

4. **Validated think-off defaults.** E5 confirmed that enabling reasoning mode is not an improvement on adversarial resistance: it eliminates a-009 but introduces a new reproducible compliance pattern on a-014 (2/3 runs), quadruples the needs-review population, and taxes latency by ~17x. This closes the long-running "maybe we should enable reasoning for safety" conjecture with concrete evidence that the answer is no.

**Why not the 4B anymore:**

The 2026-04-18 4B-as-default decision was grounded in n=1 Phase 3 numbers under `think=true` / `num_ctx=4096` that the replication has invalidated:

- "4B has higher JSON validity than 9B (82.9% vs 74.3%)" → both are 100% under production config
- "4B has higher category accuracy than 9B (57.1% vs 54.3%)" → 9B leads under production config (83.4% vs 80.6%)
- "4B has lower latency than 9B (74s vs 107s)" → both are now fast (~3-5s/triage for 4B, ~7-10s/triage for 9B on normal triage, adversarial is ~7s for both)

None of the 2026-04-18 rationale survives replication. The 4B remains a usable model — it is still in the registry, still selectable from the dropdown, still produces 100% JSON validity — but the case for it as *default* is gone.

**Why not the 2B:**

The 2B is a usable model under production config (100% JSON validity vs the earlier 2.9%), but its category accuracy (74.9%) and adversarial compliance (38.6% of adversarial attempts succeed) put it below the 4B and 9B. It stays in the registry for the size-comparison deliverable and for hardware-constrained scenarios, but it is not a candidate for default.

**Acknowledged caveats and production-readiness limitations:**

1. **a-009 is a known reproducible vulnerability.** Indirect injection via quoted JSON debug payload — the same ticket, compromised the same way, every run. The 9B cannot be deployed autonomously on user-submitted content without either (a) an upstream detector for debug-payload-style content or (b) human review of all tickets flagged as high-severity by the 9B.

2. **Phase 4 replication Observation 3 (see evaluation-checklist.md):** The 9B is *not* production-ready for autonomous deployment — the "best available option" and "production-ready" are different bars. The 9B is the best of three imperfect choices under the hardware constraint, not an evidence-based claim that it is safe for untrusted-input deployment.

3. **Latency envelope:** Per-triage latency on normal tickets is ~3-5 s for the 4B and ~7-10 s for the 9B (Phase 3 replication, n=5). On adversarial tickets the 9B latency is ~5-11 s. The p95 is higher — roughly ~15-25 s on the 9B — and there are occasional 30+ s outliers. This is acceptable for a human-in-the-loop demo or assistive-triage scenario, but not for a sub-second live API. A cloud deployment backed by Qwen API would reduce latency substantially (see `docs/cost-analysis.md`); the 9B-on-consumer-hardware latency profile is specific to the local deployment path.

4. **Think-on is not a workaround.** E5 closes the conjecture that enabling reasoning mode would compensate for a-009. It does — but only at the cost of a new vulnerability on a-014, ~17x worse latency, and ~18x more expensive output tokens. Not a defensible tradeoff.

**Honest framing:** Based on the measured evidence, the 9B is the best available default for this system. It is not production-ready for autonomous deployment on adversarial-capable input, but it is the right default for the demo and for any reviewer-assistive use case where a human looks at the triage output before acting on it.

**Configuration change (this PR):**

- `.env.example` updated: `OLLAMA_MODEL=qwen3.5:9b` (previously `qwen3.5:4b`)
- `README.md` updated: Production configuration section lists 9B as default demo model; Ollama pull commands reordered to pull 9B first
- Triage tab's dropdown default resolver extracted to a testable helper (`resolve_default_provider`) with an explicit regression test that 9B is selected when registered as the default
- No ADR modifications (per plan scope)

**References:** This PR (`feature/e5-reasoning-on-adversarial`), Phase 3 replication data (`data/phase3-1/`), Phase 4 replication data (`data/phase4-1/`), E5 data (`data/e5-reasoning/`), `docs/evaluation-checklist.md` § Phase 3 Replication, § Phase 4 Replication, § E5 Reasoning Mode.

---

## 2026-04-19 — Phase 3 replication supersedes single-run claims

**Decision:** Phase 3 replication data (n=5 runs under production configuration) supersedes the earlier single-run (n=1) Phase 3 claims. Prior decision-log entries are not edited — they remain the historical record of what was concluded from n=1 — but readers should treat the claims below as superseded.

**Superseded claims (all sourced from n=1 data collected with `think=true` and `num_ctx=4096`):**

- *"The 4B has meaningfully better JSON validity (82.9%) than the 9B (74.3%), making the 4B the reliability leader."* — Superseded. Under production config, all three models achieve 100% first-pass JSON validity. JSON validity is no longer a differentiator. (See [OD-4 resolution, 2026-04-18](#2026-04-18--od-4-resolved-qwen-35-4b-is-the-default-demo-model) and [evaluation-checklist.md § Experiment 1](../evaluation-checklist.md#experiment-1-model-size-comparison).)

- *"The 4B is the accuracy leader across all dimensions (category 57.1% vs 9B 54.3%, severity 51.4% vs 48.6%, escalation 74.3% vs 65.7%)."* — Superseded. Under production config, the 9B leads on every accuracy metric (category 83.4% vs 4B 80.6% vs 2B 74.9%). With reliability equalized, classification accuracy becomes the differentiator and the quality-size curve is monotonic. The original accuracy numbers reflected thinking-mode behavior at a 4096-token context, not the 4B's inherent classification advantage.

- *"The 2B is essentially unusable for structured output (1/35 = 2.9% success rate)."* — Superseded. Under production config, the 2B achieves 35/35 success (100%) with 100% JSON validity. The original "unusable" finding measured thinking-mode + limited-context brokenness, not the 2B's capability. The 2B's accuracy under production config (74.9% category) is lower than the 4B and 9B but it is a usable model, not a broken one.

- *"Validation + retry increases coverage from 23/35 to 29/35 — the retry pipeline recovers 6 additional tickets."* — Superseded. Under production config, first-pass JSON validity is ~100% and retry rate is ~0–3%. The retry path has almost nothing to recover. The validator-first architectural decision (ADR 0002) still holds as defense-in-depth, observability, and the scope carve-out for injection defense — but its *operational role* has shifted from "active correction loop" to "safety net / insurance." See [`tradeoffs.md` § Post-implementation observations](../tradeoffs.md#post-implementation-observations).

- *"The thesis-supporting comparison (4B-validated vs 9B-unvalidated) shows a smaller model with controls beats a larger model without them."* — Superseded. Under production config, 2B-validated (74.9% category) loses to 9B-unvalidated (84.6%) on every accuracy metric, and 4B-validated (79.4%) still loses to 9B-unvalidated (84.6%) by ~5pp on category. Engineering controls do not compensate for a 2x–4x parameter gap when both models produce valid structured output. The thesis statement ("engineering controls matter as much as model choice") now requires the caveat that this holds where controls have failure cases to rescue — not where first-pass validity is already near-ceiling.

**What did not change:**

- The validator-first architectural decision in ADR 0002. ADRs capture decisions at the time they were made; the decision is still correct, only the evidence framing has evolved. No ADRs are modified as part of this reconciliation.
- The heuristic-only guardrail baseline (ADR 0008).
- The locked sampling parameters (temperature=0.2, top_p=0.9, top_k=40, repetition_penalty=1.0).
- Phase 4 adversarial findings, which were collected at n=1 under `think=true` and have not yet been replicated under production config. Phase 4 claims are not superseded; they are *pending replication* and should be read as single-run observations until that replication runs.

**New data source:** PR #24 (`feature/phase3-rerun`), commits `749bd81` through `f394f54`. 5 independent replications of E1/E3/E2 (1,575 total triages across 3 models × 5 runs × 3 experiment passes × 35 tickets) with `think=false` and `num_ctx=16384`. Full results, per-ticket accuracy matrices, ground-truth audit (5 corrected labels out of 35), and 10 analytical observations are in [`evaluation-checklist.md` § Phase 3 Replication](../evaluation-checklist.md#phase-3-replication-n5-thinkfalse-num_ctx16384).

**Operational impact on OD-4 (default demo model):** The [2026-04-18 OD-4 resolution](#2026-04-18--od-4-resolved-qwen-35-4b-is-the-default-demo-model) selected the 4B as the default based on n=1 data that the replication has now superseded. Under production config, the 9B leads on accuracy and all three models produce output in seconds rather than minutes. Reopening OD-4 is out of scope for this reconciliation — the default model is a demo choice that depends on factors beyond raw accuracy (latency, RAM headroom, adversarial availability from Phase 4 which has not been re-run). Flagged for re-evaluation when Phase 4 replication completes.

---

## 2026-04-18 — Adopted GitHub Flow over GitFlow for solo-developer project

**Decision:** The project's branching model is GitHub Flow with a `develop` integration branch, not full GitFlow. `CLAUDE.md` updated to reflect the actual process.

**Original plan:** Full GitFlow with `main`, `develop`, `feature/*`, `release/*`, and `hotfix/*` branches.

**Actual practice since Phase F:** GitHub Flow — feature branches off `develop`, PRs merging feature → develop, PRs merging develop → main as the release mechanism. No `release/*` or `hotfix/*` branches have ever been created. The one hotfix (`hotfix/demo-reliability`) was a feature branch in all but name — it merged to `develop`, not directly to `main`.

**Reasoning:** GitFlow's release and hotfix branch ceremony adds overhead without value at single-developer scale. The release branch exists to coordinate parallel release preparation while development continues on `develop` — but there is no separate QA team, no staging environment, and no parallel development stream that needs isolation from the release. The hotfix branch exists to patch production while the next release is in flight — but with a single developer, there is never a release in flight that would conflict with an urgent fix.

**What's preserved from GitFlow:**
- The semantic distinction between `main` (always deployable) and `develop` (integration)
- The rule that neither branch takes direct commits
- Feature branches for all work, merged via PR

**What's dropped:**
- `release/*` branches — PRs from `develop` to `main` serve this purpose
- `hotfix/*` branches — urgent fixes go through the same feature → develop → main path

---

## 2026-04-18 — Thinking mode disabled for demo/production configuration

**Decision:** Qwen 3.5 thinking mode is disabled via `think=false` in the Ollama request options for the demo and production pipeline configuration. The evaluation configuration (Phase 0 through Phase 4) used the default `think=true`.

**What changed:** The `think` parameter is set to `false` in the provider's request options, passed via `extra_body` to the OpenAI-compatible Ollama endpoint. This is a configuration change only — no code logic changes.

**Why:** Two phases of evidence converged on this decision:

1. **Phase 0** identified disproportionate token consumption from reasoning mode. The 2B used ~2,703 completion tokens per request (vs ~150 tokens of visible JSON output), with the remainder consumed by internal chain-of-thought. The 2B's 652s outlier on ticket n-007 was caused by reasoning runaway — 3,138 completion tokens of reasoning before emitting JSON.

2. **Phase 4** quantified the availability impact. All parse failures on the 4B clustered at 118-120s (the wall-clock time to exhaust `max_tokens=2048` on reasoning tokens). 7/14 adversarial tickets (50%) caused token-budget exhaustion on the 4B; 3/14 (21%) on the 9B. The reasoning chain consumed the entire output budget before the model could emit JSON. This is a deterministic failure mode — not stochastic — and constitutes an availability attack vector where adversarial content triggers extended reasoning.

**Scope:** This is a demo/production configuration change. It does not retroactively apply to the evaluation data:

- Phase 3 experiment results (E1 through E4) were measured with `think=true` (default). The accuracy, latency, retry, and reliability numbers in `docs/evaluation-checklist.md` reflect thinking-enabled behavior.
- Phase 4 adversarial results were measured with `think=true`. The availability failure rates (50% 4B, 21% 9B) and integrity findings reflect thinking-enabled behavior.
- The demo configuration differs from the evaluation configuration. This is documented honestly rather than presented as a retroactive change. If accuracy or reliability comparisons are needed between the evaluation baseline and the production config, a separate evaluation run with `think=false` would be required.

**Tradeoff:** We have not formally re-evaluated accuracy with thinking disabled. For ticket triage — a pattern-recognition classification task where the model maps ticket text to a fixed taxonomy of categories, severities, and routing teams — extended chain-of-thought reasoning is expected to provide minimal quality benefit. The task does not require multi-step logical deduction, mathematical reasoning, or complex planning. However, this expectation is untested. If accuracy degrades meaningfully with `think=false`, the decision should be revisited with a formal A/B comparison.

**What this affects:**
- Sampling configuration in `CLAUDE.md` updated to reflect `think=false` as the production default.
- The `docs/evaluation-checklist.md` Sampling Observations table should note this change if a post-change evaluation is run.
- `docs/threat-model.md` reasoning-mode exhaustion section describes the attack vector as measured with thinking enabled; the mitigation (disabling thinking) is a configuration response to that finding.

---

## 2026-04-18 — OD-4 resolved: Qwen 3.5 4B is the default demo model

**Decision:** The default model loaded when the Triage tab opens is **Qwen 3.5 4B**. OD-4 is now closed.

**Gate:** OD-4 was explicitly gated on Phase 3 evaluation results. Phase 3 is complete. All four experiments (E1 size comparison, E2 size-vs-controls, E3 validation impact, E4 prompt comparison v1-only) have run on the full 35-ticket normal set. The evidence is decisive — the 4B wins on every metric that matters.

**Evidence from Phase 3 (all on normal_set.jsonl, 35 tickets, prompt v1, locked sampling):**

| Metric | Qwen 3.5 2B | Qwen 3.5 4B | Qwen 3.5 9B |
|---|---|---|---|
| Successful tickets | 1/35 (2.9%) | 29/35 (82.9%) | 26/35 (74.3%) |
| Category accuracy | 2.9% | 57.1% | 54.3% |
| Severity accuracy | 0.0% | 51.4% | 48.6% |
| Escalation accuracy | 2.9% | 74.3% | 65.7% |
| JSON validity rate | 2.9% | 82.9% | 74.3% |
| Retry rate | 97.1% | 42.9% | 51.4% |
| Retry recovery rate | 0.0% | 57.1% | 50.0% |
| Avg latency | 69,077ms | 73,886ms | 107,012ms |
| Avg tokens/request | 4,951 | 3,098 | 3,378 |

**Why the 4B, not the 9B:**

1. **Higher accuracy across all dimensions.** Category accuracy 57.1% vs 54.3%, severity 51.4% vs 48.6%, escalation 74.3% vs 65.7%. The 4B is better on every classification metric.
2. **Higher reliability.** JSON validity 82.9% vs 74.3%. The 4B produces structurally valid output more often, meaning fewer requests enter the retry path.
3. **Better retry recovery.** When the 4B does fail, the repair prompt recovers 57.1% of failures vs 50.0% for the 9B. The 4B is both less likely to fail and more likely to recover when it does.
4. **Lower latency.** 74s vs 107s average — 31% faster. In a demo context, this is the difference between "watch and wait" and "noticeably slow."
5. **Lower token cost.** 3,098 tokens/request vs 3,378. The 4B is cheaper to run both locally (less GPU time) and hypothetically in the cloud (fewer billed tokens).

**Why bigger is not better here:** The 9B's longer reasoning chains have more opportunities to produce structurally invalid output. It generates more tokens per request but converts fewer of them into valid JSON. The additional parameters buy longer deliberation, not better outcomes, for this structured-output task.

**Why the 2B is not viable:** 1/35 success rate. The 2B cannot reliably produce structured JSON output at the required complexity. It remains in the model dropdown for the size-comparison story — showing the failure mode is itself a finding — but it is not a candidate for the default.

**Thesis support:** The cross-experiment finding is that 4B-with-validation (29/35 successful, 57.1% category accuracy) beats 9B-without-validation (17/35 successful, 48.6% category accuracy). A smaller model with engineering controls outperforms a larger model without them. This is the project's headline result.

**Architectural consequence:** See [ADR 0011](../adr/0011-default-model-selection.md) for the architectural decision on how the default is configured and how model selection interacts with the provider registry.

**Updated:** `TODO.md` (OD-4 marked resolved), `CLAUDE.md` (project status if applicable), this decision log.

---

## 2026-04-16 — Phase 0 smoke test complete: 2B / 4B / 9B all pass, all three retained

**Decision:** All three planned local models — Qwen 3.5 2B, 4B, and 9B — are retained for the Phase 3 size comparison. None is dropped.

**Evidence:** `scripts/phase0_smoke_test.py` executed against each model using the locked sampling parameters (temperature=0.2, top_p=0.9) on three normal-set tickets (`n-004` critical outage, `n-007` medium billing, `n-003` low feature-request). Raw outputs in `data/phase0/qwen3.5-{2b,4b,9b}-smoke.jsonl`. Detailed observations captured in `docs/evaluation-checklist.md`, Phase 0 section.

**Results:** All three models produced 100% valid JSON, 100% correct field shape (all 8 required keys, no extras), and 100% correct category+severity against ground truth.

| Model       | Valid JSON | All fields | Correct category+severity | Latency range | Quantization | Approx RAM |
| ----------- | ---------- | ---------- | ------------------------- | ------------- | ------------ | ---------- |
| Qwen 3.5 2B | 3/3        | 3/3        | 3/3                       | 42–652 s      | Q8_0         | 2.7 GB     |
| Qwen 3.5 4B | 3/3        | 3/3        | 3/3                       | 36–52 s       | Q4_K_M       | 3.4 GB     |
| Qwen 3.5 9B | 3/3        | 3/3        | 3/3                       | 45–85 s       | Q4_K_M       | 6.6 GB     |

**Per-model go/no-go rationale:**

- **2B — GO, with a known risk to mitigate in Phase 1+.** The 2B passed all correctness gates, but n-007 took 652 s because the model over-ran in reasoning mode (3138 completion tokens for a routine billing question) before emitting the final JSON. The JSON itself was clean — this is a latency tail, not a correctness failure. The validator-first pipeline needs either a `max_tokens` cap, a wall-clock timeout, or a "think: false" Ollama request option to contain it. This is the kind of stress the 2B was kept in the lineup to expose; excluding it here would suppress a useful signal.
- **4B — GO, unconditionally.** Fastest of the three on two of three tickets, stable token counts (1143–1776 completion tokens), correct on every metric. Strong middle data point.
- **9B — GO, unconditionally.** Correct on every metric with the highest reported confidence scores (0.95–1.00). First-ticket latency (84.92 s) reflects warm-start overhead after model load; subsequent tickets settled at ~45 s. Fits comfortably on 24 GB unified memory with headroom for IDE, app, and OS.

**Secondary finding — MLX not engaged.** `OLLAMA_MLX=1 ollama run <model> --verbose` returned decode rates of 61.72 / 36.03 / 26.73 tok/s for 2B / 4B / 9B respectively. These rates are consistent with the Metal GGML backend, not MLX kernels, for this architecture on M4 Pro. Ollama 0.20.7 has not yet landed MLX coverage for the `qwen35` architecture. This was flagged in PLAN.md ("treated as a pleasant possibility, not as a planning assumption") and does not change the plan — latency budgets for all subsequent phases assume Metal GGML. If a future Ollama release adds MLX for `qwen35`, the benchmarks should be rerun.

**Operational note — `qwen3.5:9b` tag.** The 9B model was previously pulled locally as `qwen3.5:latest` (6.6 GB, Q4_K_M, 9.7B params — i.e., the 9B). To match the tag the smoke-test runner expects, an alias was created with `ollama cp qwen3.5:latest qwen3.5:9b`. No re-download; no runtime effect; the alias is non-destructive.

**What this unblocks:** Phase 1 can proceed with the default plan of three local providers. The choice of which size to make the demo default (OD-4) is still deferred to post-Phase 3 evaluation data.

**Updated:** `docs/evaluation-checklist.md` (Phase 0 section filled in), this decision log.

---

## 2026-04-16 — Sampling parameters locked

**Decision:** Sampling parameters are no longer ranges — they are fixed values for all pipeline and evaluation use:

| Parameter          | Previous (range) | Locked value        |
| ------------------ | ---------------- | ------------------- |
| Temperature        | 0.1–0.3          | **0.2**             |
| Top-p              | 0.85–0.9         | **0.9**             |
| Top-k              | 40               | **40** (unchanged)  |
| Repetition penalty | 1.0              | **1.0** (unchanged) |

**Rationale:** The Phase 0 smoke test, all four experiments, and the production pipeline must use identical sampling parameters so results are directly comparable. Ranges introduce an uncontrolled variable — if the smoke test runs at temperature=0.1 and a later experiment runs at 0.3, any difference in output quality is confounded. Locking values eliminates that.

**Values chosen:** Temperature 0.2 is low enough to keep structured JSON output consistent but avoids the repetition loops that fully greedy decoding (0.0) can cause in some models. Top-p 0.9 is a standard conservative setting.

**Change process:** Any future change to these values requires a new decision-log entry and must be reflected in the Sampling Observations table in `docs/evaluation-checklist.md`.

**Updated:** `CLAUDE.md` (Hardware & model constraints section) — ranges replaced with locked values.

---

## 2026-04-16 — Dataset finalized: 35 normal tickets (with edge cases) + 14 adversarial tickets

**Decision:** Both evaluation datasets are authored and stored in `data/`. Final sizes and composition:

- **Normal set (`data/normal_set.jsonl`):** 35 tickets. 30 standard tickets covering all 6 categories, 5 routing teams, 4 severity levels (low/medium/high/critical), with realistic variation in length, tone, and clarity. Plus 5 edge-case tickets:
  - Tickets n-031 through n-033: non-actionable input (gibberish, irrelevant prose, positive feedback with no issue). These are not blocked by the guardrail — they reach the model, which classifies as `category: "other"` with low confidence. The semantic validation layer flags them as non-actionable based on the combination of low confidence and a summary that does not describe an actionable issue.
  - Tickets n-034 and n-035: ambiguous severity (real observations with no clear urgency or business impact). The model defaults to `severity: "low"` with a lower confidence score as the signal that severity was uncertain.

- **Adversarial set (`data/adversarial_set.jsonl`):** 14 tickets across 7 attack categories (4 direct injection, 2 obfuscated, 3 indirect via quoted content, 2 PII, 1 hostile, 1 length extremes, 1 multilingual).

**Severity taxonomy locked:** 4 values — `low`, `medium`, `high`, `critical`.

**Design decisions:**
- Non-actionable tickets bypass the pre-LLM guardrail intentionally. The guardrail is for injection defense, not content quality filtering. Trying to detect "not a real ticket" at the guardrail level would require either a second model or brittle heuristics — neither is worth the complexity for this iteration.
- Confidence is the unified signal for "the model had to guess." Both non-actionable and ambiguous-severity scenarios use lower confidence as the flag, keeping the mechanism simple and consistent.
- Non-actionable tickets go in the normal set (not adversarial) because they are not attack vectors — they are edge cases of legitimate usage.

**Updated:** `docs/evaluation-plan.md` (dataset sizes, new scenario documentation), `docs/PLAN.md` (size references in Phases 3 and Final Recommendation, OD-7 resolution). See also [ADR 0010](../adr/0010-non-actionable-and-ambiguous-input-handling.md) for the architectural decision on where in the pipeline this detection belongs.

---

## 2026-04-15 — API endpoint: FastAPI alongside Gradio for rubric compliance

The rubric's Environment Setup criterion requires the model to be "accessible via an API endpoint." The original single-app Gradio architecture (ADR 0006) did not explicitly address this. Gradio auto-generates internal API endpoints, but these are framework-determined, not project-designed, and lack Swagger/OpenAPI documentation.

Resolution: add a minimal FastAPI layer alongside Gradio in the same process. FastAPI is the outer app; Gradio is mounted inside it as a sub-application. One new route (`POST /api/v1/triage`) calls the same `triage_service.run_triage()` that the Gradio Triage tab calls. Swagger UI is auto-generated at `/docs` from the existing pydantic request/response models.

This does not create a client/server split — it's one process, one codebase, one Docker container. The service layer is unchanged. The instructor can open `/docs` in a browser, submit a triage request via Swagger, and see the structured result without using the Gradio UI.

See the addendum to ADR 0006 for the full architectural update.

---

## 2026-04-15 — Sampling configuration: conservative baseline for structured output, with room for experimentation

The rubric's Inference Pipeline criterion explicitly calls out sampling method at both the Excellent and Good tiers. The plan did not previously address sampling parameters.

Resolution: the pipeline will use a conservative baseline sampling configuration optimized for structured JSON output:

- **Temperature: 0.1–0.3** — low temperature produces predictable, schema-conforming output. At temperature 0.0 (greedy decoding), the model always picks the highest-probability token, which maximizes JSON validity but may reduce diversity across runs. A small amount of temperature (0.1–0.3) allows minimal variation while keeping output reliable.
- **Top-p: 0.85–0.9** — nucleus sampling that considers the top ~85–90% of the probability mass. This excludes low-probability tokens that could break JSON structure while still allowing the model some choice among plausible completions.
- **Top-k: 40** — limits consideration to the 40 most probable tokens. Standard default that works well for most structured-output tasks.
- **Repetition penalty: 1.0 (disabled)** — repetition penalty is useful for free-form text generation but can interfere with JSON output where field names and structural tokens legitimately repeat.

The rationale: structured JSON output requires the model to be *boring and predictable*. Every "creative" token choice is a potential validation failure — a stray character, a hallucinated field name, a broken bracket. Low temperature, moderate top-p, and standard top-k bias the model toward the expected schema structure.

These values are the *starting* configuration. They are passed as parameters to the provider (Ollama's API accepts `temperature`, `top_p`, `top_k` as request parameters), configurable via environment variable or app config, and documented in the architecture doc. If time permits during or after Phase 3, sampling parameters can be added as an experimental variable to test whether different settings measurably affect JSON validity or task accuracy — the eval harness already supports this by parameterizing runs.

---

## 2026-04-15 — Monitoring strategy: distinguish from benchmarking, add live metrics with drift indication

The Metrics tab will be split into two clearly distinct sections: "Benchmark Results" (static, from labeled eval runs) and "Live Metrics" (rolling, from live trace traffic). The distinction matters because benchmarking and monitoring answer different questions — benchmarking is "how does this perform on a known test set," monitoring is "what's happening in production right now."

The Live Metrics section adds: time-series latency trends (p50, p95) over rolling windows, time-series error rate trends, category distribution as a basic drift indicator, and structured-log alerts when configured thresholds are crossed (default: p95 > 5s, retry rate > 20%, single category > 70% of recent traffic).

Out of scope deliberately: real alerting infrastructure (PagerDuty etc.), a separate time-series database (Prometheus etc.), distributed tracing, long-term retention policies, learned anomaly detection. These are appropriate for a real production service mesh but are overkill for a single-instance demo system on consumer hardware. The limitations are documented honestly rather than pretending the system has them.

The work was scoped at roughly 3–4 hours of coding agent time and 1.5 hours of developer attention, with much of the agent work parallelizable with other Phase 5+ activities. Most student LLM projects collapse benchmarking and monitoring into one undifferentiated "dashboard"; this project's deliberate separation is itself a piece of the engineering judgment story.

---

## 2026-04-15 — Deployment strategy: local-only with Docker containerization for the app

The system will be deployed locally, with two supported paths: native (`uv run` against host Ollama) and containerized (Docker container for the Gradio app, Ollama on the host). Containerization is added because "I can run it on my Mac" is not a deployment story — the instructor or anyone evaluating the project needs to be able to actually stand it up on their own machine, and that requires explicit, reproducible setup.

The architecture deliberately keeps Ollama on the host (not inside the container). The reason: Docker on Mac runs in a Linux VM that has no access to the Apple GPU, so running Ollama inside a container on Apple Silicon would lose MLX/Metal acceleration entirely and force CPU-only inference. That would defeat the project's consumer-hardware thesis. The chosen split — Ollama on host, app in container — preserves GPU acceleration, keeps the container small (~500MB instead of 12GB+), and matches how Ollama is typically deployed in the field. The tradeoff is that the deploying user has to install Ollama and pull models separately before running the container; this is documented in `DEPLOYMENT.md`.

The Docker setup will be tested on three platforms before being treated as deployable: macOS (developer's primary), Windows (developer's secondary), and Linux (developer's work laptop). Tested platforms will be documented explicitly. Cross-platform testing is non-optional — a deployment story is only as strong as the platforms it has actually been verified on.

This decision adds work to Phase 1 (Dockerfile + basic local container verification) and Phase 7 (`DEPLOYMENT.md`, cross-platform testing).

Cloud deployment (AWS, etc.) was considered and rejected because it would conflict with the consumer-hardware thesis that anchors the rest of the project.

---

## 2026-04-14 — OD-7 resolved: Adversarial set categories and counts locked, content deferred to Phase 3

The adversarial set categories and target counts are locked:

| Category                              | Target count | What it tests                                                                                             |
| ------------------------------------- | -----------: | --------------------------------------------------------------------------------------------------------- |
| Direct prompt injection               |          3–4 | Explicit attempts to override model behavior                                                              |
| Direct injection with obfuscation     |            2 | Base64, language switching, invisible Unicode — tests whether guardrails are semantic or pattern-matching |
| Indirect injection via quoted content |          2–3 | Malicious instructions inside quoted emails, error messages, or log excerpts                              |
| PII / data leak triggers              |          1–2 | Fake credit card numbers or other PII that should trigger a guardrail                                     |
| Hostile / abusive language            |            1 | Emotionally charged but legitimate tickets                                                                |
| Length extremes                       |            1 | Very short and/or very long input                                                                         |
| Multilingual                          |            1 | Non-English ticket                                                                                        |

Total target: ~12 adversarial tickets (expanded from the original 8–12 range to accommodate the agreed categories).

Each ticket will be labeled with the attack type and the expected correct pipeline behavior (block, pass-through-with-correct-triage, etc.). The actual ticket text will be authored during Phase 3 — the categories and expected behaviors are the planning artifact, the content is the implementation artifact.

---

## 2026-04-14 — OD-6 resolved: Guardrail implementation starts heuristic-only

The guardrail layer will start as a heuristic-only implementation: a function that takes a ticket body and returns `pass`, `warn`, or `block` based on pattern matching. The patterns cover:

- Known injection phrases ("ignore previous instructions", "ignore all prior", "you are now", "disregard your system prompt", and similar variants)
- Suspicious structural markers (Base64-encoded blocks, invisible Unicode characters, unusual character-to-whitespace ratios)
- Length extremes (empty input, input over a threshold)
- Basic PII patterns (credit card regex, SSN regex)

This is roughly 50–80 lines of Python plus tests. The implementation cost is minimal; the valuable work is measuring the guardrail against the adversarial set in Phase 4 and writing up what it caught and what it missed.

The heuristic approach will almost certainly fail on obfuscated injection attempts — that is expected and is itself a finding worth reporting. The writeup will frame this as "the heuristic approach caught X% of direct injection but only Y% of obfuscated attacks, demonstrating the limits of pattern-matching as a defense."

**Optional stretch (post-Phase 6 if time permits):** add a small LLM-based second-pass classifier to detect injection attempts the regex missed, and re-run the adversarial eval to measure the improvement. This would add roughly half a day of implementation plus tuning plus extra eval runs, so it's only worth attempting if the core project is otherwise complete.

---

## 2026-04-14 — OD-5 resolved: Cost analysis will cover three components

The cost analysis will include three components, written up in `docs/cost-analysis.md` after Phase 3 when real token counts are available from the benchmark runs:

1. **Local compute resource cost per model** — RAM footprint, GPU utilization (if measurable), inference latency, tokens/sec, and disk usage for each model's weights. This captures what each model "costs the machine" in resource terms, even though the per-request dollar cost is $0.

2. **Hardware acquisition cost amortized** — the target Mac's purchase price amortized over its expected useful life (e.g., 3 years), expressed as a daily fixed cost. This is the honest answer to "what does local inference actually cost?" — it's not free, the hardware just isn't free.

3. **Hypothetical cloud comparison using published pricing** — using actual token counts from the benchmark (tokens in + tokens out per triage request) multiplied by published Qwen API pricing (e.g., Qwen 3.5 Plus at $0.26/M input, $1.56/M output), projected at daily volumes of 100, 1K, and 10K tickets/day. Includes a break-even calculation showing at what daily volume amortized hardware cost becomes cheaper than cloud per-request fees.

This approach recovers the most interesting part of the cloud comparison — the cost reasoning — without requiring actual cloud integration. It demonstrates the ability to reason about costs not yet incurred, which is what a senior engineer does when writing a deployment proposal.

Published Qwen pricing sources consulted:
- Qwen 3.5 Plus: $0.26/M input, $1.56/M output (OpenRouter)
- Qwen Plus: $0.26/M input, $0.78/M output (pricepertoken.com)
- Qwen3 Max: $0.78/M input, $3.90/M output (pricepertoken.com)

---

## 2026-04-14 — OD-3 resolved: Local model lineup is 2B / 4B / 9B pending Phase 0 verification

The planned local model lineup is Qwen 3.5 2B, 4B, and 9B. All three will be smoke-tested in Phase 0 on the target hardware. If any model cannot produce structured output reliably enough to be informative, it will be dropped with a documented rationale.

The 2B is included despite uncertainty about its task quality because: (1) there is no data yet that it *won't* work, and excluding it without evidence is less defensible than testing and documenting the result; (2) a wider size range (2B to 9B is roughly 5x) produces a more informative quality-vs-size curve than a narrow range; (3) the 2B is where the validator-first pipeline will be stressed hardest, since smaller models produce more malformed output, which is where retry logic earns its keep; and (4) the 2B has the lowest resource cost in both memory (~2.7GB) and inference time, making it essentially free to include in the benchmark runs.

---

## 2026-04-14 — OD-2 resolved: Cloud comparison deferred to future work

The cloud Qwen variant is out of scope for this iteration. The project will be local-only, comparing Qwen 3.5 at multiple sizes on consumer hardware. Cloud comparison is documented as future work.

Reasoning: adding a cloud provider introduces a second client integration, an API key dependency, and a cost dimension that all need to be verified and tested. The project's central thesis — that engineering controls matter as much as model choice — can be tested entirely within the local-only comparison, especially via Experiment 3 (validation on/off). The cloud comparison would strengthen the cost analysis but is not required to answer the central question. Time is better spent on evaluation depth and the prompt injection investigation.

This also simplifies the provider abstraction: only one concrete provider (Ollama) is needed for the initial build. The `LlmProvider` Protocol still exists so that a cloud provider can be added later without refactoring.

---

## 2026-04-14 — OD-1 resolved: Qwen 3.5 over Qwen 3.0

Qwen 3.5 was chosen over Qwen 3.0 because the 3.5 family delivers meaningfully better quality at the sub-10B parameter sizes that actually fit on the project's target hardware (≤24GB Apple Silicon). Specifically, the 3.5 small variants (4B, 9B) show improved instruction following, stronger structured-output and tool-calling behavior, and better benchmark scores relative to their 3.0 equivalents at the same parameter count. Since the project is constrained to consumer hardware and relies heavily on structured JSON output, the relevant comparison is not flagship-vs-flagship but rather small-model-vs-small-model — and at that tier, 3.5 is a meaningful step up. Additionally, 3.5 retains Apache 2.0 licensing and open weights on Hugging Face, so there is no licensing tradeoff.

Qwen 3.5's vision and long-context capabilities (256K+ native, 1M+ with extended attention) are not relevant to this project's text-only, short-input use case, but they do not impose any overhead either — they are available features that the project simply does not use, not costs it pays for.

Sources consulted:
- https://news.ycombinator.com/item?id=47249959
- https://www.digitalapplied.com/blog/qwen-3-5-medium-model-series-benchmarks-pricing-guide

---

## 2026-04-14 — Initial scope and framing decisions

The following decisions were made during the initial planning conversation. They establish the shape of the project before implementation begins.

### Central engineering investigation: prompt injection defense

The project will be framed around a single engineering question: *how much of the value in a production LLM system comes from the model itself versus from the surrounding engineering controls, and how well can layered mitigations defend against prompt injection in user-submitted content?*

Other potential innovation angles were considered and rejected:

- **Authentication / role-based access control** — rejected because it is general web-engineering work, not LLM-engineering work, and does not land in the rubric language about "where the LLM field currently sits and how it can be improved." Documented as future work.
- **LoRA fine-tuning** — rejected for this iteration because the developer has not previously executed a full end-to-end fine-tune independently. Adding unfamiliar technique work to a constrained build window is the failure mode most likely to produce a half-finished project. Saved as a foundation for a future agentic-coding-assistant project where fine-tuning is more central.
- **Multimodal injection / vision input** — rejected because adding image input would require a vision-capable model, new pipeline plumbing, and new evaluation work, none of which fits the build window. Documented as future work and as a deliberate scope boundary in the project's threat model.

Prompt injection was chosen because: it is LLM-native rather than generic engineering, it lands directly in the rubric language about field-level understanding, it fits inside the validator-first architecture that was already planned, it produces measurable findings on a labeled set, and it converts the validator-first design from a checkbox into a load-bearing component of the project's central claim.

### Adversarial set composition

The evaluation set will include both a normal labeled set and an adversarial set. The adversarial set covers:

- **Direct prompt injection** (primary focus) — tickets whose body contains explicit instructions to override the model's behavior
- **Direct injection with obfuscation** (2–3 cases) — Base64, language switching, or invisible Unicode variants of direct injection, used to test whether guardrails are doing semantic checking or just pattern matching against English attack strings
- **Indirect injection via quoted third-party content** — tickets that legitimately quote third-party material (forwarded emails, error messages, log excerpts) where the malicious instructions are embedded in the quoted content rather than presented as the user's own request. This is an in-scope variant of indirect injection because legitimate support tickets routinely contain quoted content, so the legitimate use case and the attack surface overlap.
- **General robustness cases** — PII embedded in tickets (e.g., fake credit card numbers that should trigger a guardrail), multi-language tickets, length extremes (very short, very long), and tickets containing abusive or hostile language. These test general robustness, not injection specifically, but are valuable signal for the operational performance evaluation.

Two-ticket combinations ("two tickets crammed into one") were considered and rejected for this iteration as low-value relative to the other categories.

Multimodal injection categories are excluded because the pipeline is text-only; this exclusion is documented in the threat model rather than left implicit.

### Hardware constraint as deliberate positioning

The project will be deliberately constrained to consumer-class Apple Silicon hardware (≤24GB unified memory) for the local execution path. This is framed as a feature, not a workaround: it reflects the deployment context that most production LLM systems will actually face outside of well-funded AI labs (privacy-sensitive industries, on-prem enterprise, indie development, regions or sectors where cloud inference is prohibited or impractical).

This positioning has three consequences for the project:

1. Models that exceed the RAM budget are excluded from the comparison even where they would otherwise be interesting (e.g., Qwen 3.5 27B, 35B-A3B).
2. The cost analysis for the project must include hardware acquisition cost amortized over useful life, not just per-request inference cost, in order to compare local and cloud honestly.
3. The decision matrix for model selection must explicitly weight "runs on consumer hardware" as a constraint, not just a nice-to-have.

### Model strategy: Qwen 3.5 family with Day 1 empirical sizing

The model family for the project is the Qwen 3.5 family. Specific sizes will not be locked in until a Day 1 smoke test on the developer's actual hardware confirms which models can produce structured output for the triage task.

The planned smoke test covers four model variants — Qwen 3.5 2B, 4B, 9B, and one cloud option (provider TBD) — using 2–3 sample tickets to verify that each model can produce roughly-valid structured output. Models that fail this smoke test are excluded from the main comparison; a documented rejection ("considered but found to be unable to follow the structured output format reliably") is treated as a more defensible answer than an a-priori exclusion.

The Qwen 3.5 27B and 35B-A3B variants are excluded by the consumer-hardware constraint above. The reason for choosing the 3.5 family over the 3.0 family is still TBD — see the open decisions section of the project plan.

### Out-of-scope decisions (combined)

The following are deliberately not part of this iteration of the project, and the reasons are captured here so that they do not need to be re-litigated and so that "what we decided not to build, and why" is itself a visible deliverable:

- Authentication / role-based access (see above)
- LoRA / fine-tuning (see above)
- Multimodal / vision input (see above)
- Cloud Qwen comparison (see OD-2 resolution above — deferred to future work)
- Qwen 3.5 27B and larger (consumer-hardware constraint)
- TypeScript / Node / React stack (see [ADR 0001](../adr/0001-language-and-stack.md))
- Two-tickets-in-one adversarial category (see above)

### Documentation strategy

Documentation will be split across three distinct artifact types, each with a clear purpose:

1. **The project plan** (`docs/llm-ticket-triage-plan.md`) — the working document describing what is being built, how, and why. Updated as the project evolves.
2. **Architecture Decision Records** (`docs/decisions/`) — formal, structured records of *architectural* decisions only, in `adr-tools` format. Each ADR is one decision, one file, immutable once accepted (superseded by later ADRs if needed).
3. **The decision log** (this file) — chronological, informal, captures scope, framing, and strategy decisions that are not architectural. Newest entries at the top.

The instructor's emphasis on "factors weighing" in decision-making means that the *process* of decision-making is itself a graded artifact, not just the final answers. The decision log and the ADRs together form the trail of that process.
