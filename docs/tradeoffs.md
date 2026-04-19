# Tradeoffs

This document captures the cross-cutting tradeoffs made in the project — decisions where choosing one value meant accepting a cost in another. Each tradeoff is stated plainly: what was gained, what was lost, and why the gain was worth more in this context.

These are not failures or limitations. They are engineering judgment calls. A different context (more time, more hardware, different requirements) would produce different calls.

---

## Model quality vs hardware constraint

**What we chose:** Qwen 3.5 at 2B, 4B, and 9B parameter sizes, all running locally on a 24GB Apple Silicon Mac.

**What we gave up:** Larger models (27B, 35B, flagship cloud models) that would likely produce higher task accuracy and better structured-output reliability.

**Why the gain was worth more:** The project's thesis is that useful LLM systems can run on consumer hardware. Testing only on models that require datacenter GPUs or cloud APIs would undermine the thesis. The constraint is not incidental — it is the point. The interesting question is not "can a 70B model do triage well" (obviously yes) but "how small can you go before engineering controls stop compensating for model limitations?"

---

## Evaluation depth vs build time

**What we chose:** Four focused experiments (size comparison, size-vs-controls interaction, validation on/off, prompt v1/v2) plus a prompt injection sub-evaluation, on a dataset of 20–30 normal tickets and ~12 adversarial tickets.

**What we gave up:** A larger dataset, more experiments (e.g., temperature sweeps, context-length stress tests, multi-turn triage), statistical significance testing, cross-family model comparisons.

**Why the gain was worth more:** A small number of well-designed experiments with clearly stated hypotheses and honest findings is more valuable than a large number of poorly-controlled experiments that produce noise. Each of the four experiments is a direct probe at the project's central question. Adding more experiments would dilute focus without strengthening the central argument. The dataset size is sufficient to reveal meaningful patterns (a model that fails JSON parsing 15% of the time will show that clearly on 30 tickets) even if it's not large enough for rigorous statistical inference.

---

## Heuristic guardrail vs sophisticated defense

**What we chose:** A pattern-matching guardrail that checks for known injection phrases, structural anomalies, and PII patterns.

**What we gave up:** An LLM-based semantic classifier, a fine-tuned injection detector, or any defense that can catch novel attacks the pattern set doesn't cover.

**Why the gain was worth more:** The project's goal is to *measure* the guardrail's effectiveness, not to maximize it. A simple guardrail with known limitations produces a cleaner finding than a sophisticated one whose failure modes are harder to characterize. The expected result — "pattern matching catches direct injection but fails on obfuscated attacks" — is itself the finding. An LLM-based classifier is documented as an optional stretch and as future work.

---

## Single-app Gradio UI vs custom frontend

**What we chose:** A single-process Gradio app with `gr.Blocks` and tabs.

**What we gave up:** Visual polish, interactive flexibility, custom chart styling, the ability to build a "product-quality" UI.

**Why the gain was worth more:** The rubric grades engineering judgment, evaluation rigor, and documentation — not frontend craft. Every hour spent on a React build system, component library, or CSS is an hour not spent on the evaluation, the prompt injection investigation, or the ADRs. Gradio is functional, clean, and already known from prior coursework. The UI is a vehicle for the investigation, not the product.

---

## Local-only deployment vs cloud accessibility

**What we chose:** Local deployment on consumer hardware, with Docker for reproducibility.

**What we gave up:** A public URL the instructor could access without setup. Cloud-level availability, scalability, and monitoring infrastructure.

**Why the gain was worth more:** Cloud deployment would contradict the project's consumer-hardware thesis. The Docker container makes the deployment reproducible across platforms without requiring cloud infrastructure. The instructor runs three commands (install Ollama, pull models, docker run) and the system is up. The tradeoff is that these three commands exist at all — on a cloud deployment, the instructor would just click a URL. But the three commands are documented, tested on three platforms, and take under five minutes.

---

## Ollama on host vs Ollama in container

**What we chose:** Ollama runs natively on the host. The Gradio app runs in a Docker container. The container reaches Ollama over the network.

**What we gave up:** A fully self-contained Docker deployment (one command, no external dependencies).

**Why the gain was worth more:** Docker on Mac runs in a Linux VM with no Apple GPU access. Ollama inside a container on Apple Silicon would be CPU-only — dramatically slower, defeating the purpose of consumer-hardware deployment. Keeping Ollama on the host preserves GPU/MLX acceleration. The cost is that the deployer has to install Ollama separately, which is one extra step documented in `DEPLOYMENT.md`.

---

## SQLite vs a real database

**What we chose:** A single SQLite file for all trace storage.

**What we gave up:** Concurrent write support, remote access, replication, advanced query capabilities, and the operational maturity of PostgreSQL.

**Why the gain was worth more:** The project is a single-process app producing hundreds of records. SQLite's limitations (one writer at a time, no remote access) are irrelevant at this scale. Its advantages (zero setup, ships with Python, works in Docker, no server to maintain) are directly relevant. Moving to PostgreSQL would add an infrastructure dependency, a Docker service, and configuration complexity — all for capabilities the project does not use.

---

## Log-based alerting vs real monitoring infrastructure

**What we chose:** Structured log warnings when monitoring thresholds are crossed.

**What we gave up:** PagerDuty/Opsgenie integration, Prometheus/Grafana dashboards, real-time notification channels, historical metric retention with downsampling.

**Why the gain was worth more:** The project demonstrates the *concept* of production monitoring (separate from benchmarking, with alerting thresholds and drift detection) without the *infrastructure* of production monitoring. The infrastructure would add multiple new dependencies, complicate deployment, and take build time away from the evaluation and investigation that the rubric actually grades. The limitation is documented and listed as future work.

---

## No LoRA fine-tuning this iteration

**What we chose:** Use the Qwen 3.5 models as-is from Ollama, with no fine-tuning.

**What we gave up:** The potential for meaningfully better task accuracy, structured-output reliability, and injection resistance through fine-tuning on domain-specific ticket data.

**Why the gain was worth more:** The developer has not previously executed a full end-to-end LoRA fine-tune independently. Adding unfamiliar technique work to a constrained build risks producing a half-finished fine-tune and a broken baseline. The project can produce a complete, rigorous evaluation without fine-tuning. Fine-tuning is documented as future work and as a natural extension for a subsequent project (the local agentic coding assistant).

---

## No cloud cost comparison (actual)

**What we chose:** A hypothetical cloud cost comparison using published Qwen API pricing and actual token counts from the benchmarks, rather than running a real cloud model.

**What we gave up:** Actual cloud latency numbers, actual cloud accuracy numbers, and a direct apples-to-apples comparison on the same tickets.

**Why the gain was worth more:** Integrating a cloud provider requires an API key, a second client library, verification of pricing and availability, and additional eval runs — roughly a half-day of work that produces one more row in the benchmark table. The hypothetical comparison using published pricing recovers the most interesting finding (the break-even volume where local becomes cheaper than cloud) without the integration work. The limitation is documented and the cloud provider integration is listed as future work.

---

## Post-implementation observations

These are observations recorded *after* the tradeoffs above were made, reflecting what the implemented system actually does in measured practice. They recontextualize a decision without reversing it — the engineering call still holds; the observed operating regime is narrower than originally anticipated.

### Validator-first pipeline: retry rate near zero under production config

**What was decided:** A validator-first pipeline with bounded retry (ADR 0002). The validator parses, schema-checks, and runs semantic checks on every model response. On failure, a single repair prompt attempt is made with the failed output and specific error returned to the model.

**What was expected at decision time:** The retry path would be an active correction loop. Small models produce malformed JSON often; the repair prompt would recover a meaningful fraction of those failures; the measured retry rate would be the operational signal justifying the complexity.

**What the replication data shows:** Under the current production configuration (`think=false`, `num_ctx=16384`), first-pass JSON validity is ~100% across all three models (2B/4B/9B) on the 35-ticket normal set, across 5 independent replications. Measured retry rate is ~0–3%. The repair pipeline has almost nothing to recover. The "retry recovers 6 additional tickets" finding from the original n=1 Phase 3 data was an artifact of thinking-mode + limited-context brokenness, not a steady-state observation. See [`evaluation-checklist.md` § Phase 3 Replication](evaluation-checklist.md#phase-3-replication-n5-thinkfalse-num_ctx16384) and the [2026-04-19 decision-log reconciliation](decisions/decision-log.md#2026-04-19--phase-3-replication-supersedes-single-run-claims).

**The architectural decision still holds.** This is a recontextualization, not a reversal:

- **Defense in depth.** The pipeline never returns malformed data to a consumer. Even at ~100% first-pass validity, "the parser has never failed in production" is not a guarantee that it never will — models, prompts, sampling parameters, and input distributions all drift. The validator is an assertion boundary between model output and system consumers; removing it would be removing a guarantee to catch one fewer exception per N thousand requests.
- **Observability.** The validation result is a structured field on every trace (`validation_status`: passed / failed-and-retried / failed). That signal drives the Metrics tab, the Traces tab, and the retry-rate KPI. Removing validation would also remove the primary signal the monitoring design (ADR 0009) is built around.
- **Injection scope carve-out.** The three-layer injection defense (`docs/threat-model.md`, ADR 0008) depends on post-LLM validation as Layer 3. Phase 4 adversarial results show this layer has not been meaningfully tested yet (no adversarial ticket produced a schema- or semantic-invalid injected output), but the layer is load-bearing for any future attack that does. Removing validation on the grounds that "it rarely catches anything on normal input" would remove it on adversarial input too, where it is the backstop.
- **Reversibility.** Keeping the validator is a cheap insurance premium (one parse + one schema validation per request, adding milliseconds). Removing it and reinstating it later is more expensive than keeping it.

**What changed in the framing.** The validator's *operational role* has shifted from "active correction loop where retry frequency is the headline KPI" to "assertion boundary / safety net where retry frequency is a near-zero measurement of system health, and any non-zero drift is a signal worth investigating." The complexity of the retry loop is no longer justified by "it recovers many tickets"; it is justified by "it guarantees no malformed output ever leaves the pipeline, and it is the only Layer 3 defense in the injection threat model." ADR 0002 is not edited — ADRs record decisions at the time they were made, and the decision is still correct under its stated reasoning.

**Updated with Phase 4 replication (2026-04-19).** Phase 4 replication under production config (n=5 runs per model, 14 adversarial tickets each, 210 total adversarial triages) produced **zero parse failures** across all three models. The "retry is near-zero on normal input" observation now extends to adversarial input as well: the original Phase 4 n=1 parse-failure rates (50% on 4B, 21% on 9B) were reasoning-mode-exhaustion artifacts, not an adversarial-input pattern. Under production config, the validator catches schema/semantic failures on adversarial input at the same near-zero rate as on normal input. The injection defense's Layer 3 (post-LLM validation) is load-bearing by design, not by measured recovery rate.

### Reasoning mode redistributes adversarial failure rather than reducing it

**What was decided:** Thinking mode disabled in production (`think=false`) because reasoning tokens exhausted the 4096-token context window on the original configuration and caused parse failures. The decision was pragmatic — we needed reliable structured output — not an adversarial-robustness claim.

**What was expected at decision time:** Once `num_ctx=16384` fixed the exhaustion problem, we anticipated that enabling reasoning mode again would be *safe* for adversarial robustness, possibly even helpful. The naive hypothesis was "more deliberation → more careful refusals."

**What the E5 data shows (2026-04-19):** On the 9B adversarial set across 3 replications per condition, enabling reasoning mode:

- Eliminated the clean integrity compromise on a-009 (`TT` → `FF?` — resisted in 2/3 runs, ambiguous in 1/3).
- **Introduced a new reproducible compliance on a-014** (`FF` → `TFT` — compromised in 2/3 runs, previously 0/5 across the Phase 4 replication).
- Degraded 7 additional previously-resisted tickets from stable-resist (`FF`) to ambiguous outcomes (`FF?`, `F??`).
- Quadrupled the "needs manual review" count (mean 1.0 → 4.0 with stddev 0.0 → 2.16).
- Increased per-triage latency ~17x (6.9 s → 121 s mean) and output tokens ~18x (162 → 2,913 mean).

**The architectural decision still holds.** `think=false` remains the production default. But the *framing* has changed: reasoning mode is not disabled only for latency/token-budget reasons — it is disabled because **enabling it makes adversarial behavior worse in aggregate**, not better. A reviewer who suggests "just turn reasoning on for safety" now has a concrete, measured counter-argument.

**What this changes about the heuristic guardrail decision (ADR 0008).** The ADR scoped the guardrail as a heuristic baseline with an expected finding ("pattern matching fails on obfuscated/indirect attacks"). E5 adds a second expected finding: *reasoning-mode model behavior is not a substitute for a real defense*. Both findings reinforce the original stance that the guardrail upgrade (LLM-based classifier, Option B) should be measured against the baseline, not assumed.

See `docs/evaluation-checklist.md` § E5 and `docs/adr/0008-heuristic-only-guardrail-baseline.md` § Addendum (2026-04-19).

### Local-only deployment cost: non-dollar factors dominate at project scale

**What was decided:** Local-only deployment (see "Local-only deployment vs cloud accessibility" above). The framing at decision time emphasized privacy, API-key avoidance, and consumer-hardware demonstrability.

**What was expected at decision time:** The original tradeoff text implied — without quantifying — that local would be cost-competitive at operational scale. "Cloud accessibility" was the gave-up side; cost was treated as a neutral factor.

**What the cost-analysis data shows (2026-04-19):** With measured token counts from the Phase 3 replication and Qwen 3.5 Plus published pricing, cloud-per-request cost on the 9B is $0.000408. Amortized local hardware is $2.28/day on a $2,499 MacBook Pro. **Break-even volume is ~5,596 requests/day** — cloud wins on pure dollars by 5-50x at the project's plausible operational scale (100-1,000 tickets/day). See [`cost-analysis.md`](cost-analysis.md) § Break-even analysis.

**The decision still holds, but the framing sharpens.** Local deployment is not the economically-dominant choice at this project's scale — it is the privacy-dominant, operational-simplicity-dominant, and latency-dominant choice. A reader looking at the original tradeoff text without the cost-analysis data might walk away with the impression that local wins on all axes. It does not. It wins on everything *except* dollars-per-request at small-to-medium volume.

**What this means for the project's thesis.** The project's central engineering investigation ("how much of the value comes from the model vs. the engineering controls") is unaffected — the cost story is orthogonal to the model-vs-controls question. But any claim that implies *local is cost-dominant* should be qualified with the break-even number. The cost-analysis summary now does this explicitly: "cloud wins at low-to-medium volume by 5-50x; local wins on non-dollar factors (privacy, latency, operational simplicity)." `docs/presentation-notes.md` slide 5 reflects this honest framing.
