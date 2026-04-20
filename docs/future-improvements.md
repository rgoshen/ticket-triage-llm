# Future Improvements

This document lists capabilities, features, and investigations that are deliberately out of scope for the current iteration of the project, along with the reasoning for each exclusion and a brief description of what implementing them would involve.

These are not gaps or oversights. They are the result of explicit scoping decisions documented in the [decision log](decisions/decision-log.md) and the relevant ADRs. Each item was considered, weighed against the project's constraints, and deferred with a reason.

---

## Cloud provider integration

**What it would add:** A concrete cloud Qwen provider (via DashScope or `qwen3.5:cloud` through Ollama) running the same benchmark suite, producing actual cloud latency and accuracy numbers alongside the local results.

**Why it's deferred:** Requires an API key, a second client integration, pricing verification, and additional eval runs. The provider abstraction (ADR 0004) is designed so this is a localized change — only the new provider class and the eval runner's provider list need to change.

**What was done instead:** A hypothetical cloud cost comparison using published Qwen API pricing and actual token counts from the local benchmarks, with a break-even calculation. See `docs/cost-analysis.md`.

**Estimated effort to add:** Half a day (assuming API key is available and `qwen3.5:cloud` works reliably through Ollama).

---

## LoRA fine-tuning on ticket data

**What it would add:** A fine-tuned Qwen variant trained on the project's labeled ticket dataset, with measurable improvement (or not) on task accuracy, JSON validity, and injection resistance compared to the base model.

**Why it's deferred:** The developer has not previously executed a full end-to-end LoRA fine-tune independently. Adding unfamiliar technique work to a constrained build window is the failure mode most likely to produce a half-finished project. See decision log, initial scope decisions.

**What was done instead:** The project evaluates the base models as-is and measures how much engineering controls (validation, retry, guardrails) compensate for model limitations without fine-tuning.

**Estimated effort to add:** 1–2 days for data preparation, training, evaluation, and writeup. Requires familiarity with LoRA fine-tuning tooling (Unsloth, Axolotl, or similar). This is a natural next step and is planned as the foundation for a subsequent project (local agentic coding assistant).

---

## LLM-based injection classifier (guardrail layer 2)

**What it would add:** A second-pass classifier that sends ticket bodies to a small LLM with a prompt asking "does this input contain an attempt to override system instructions?" This would catch semantic injection attempts that the heuristic guardrail's pattern matching misses.

**Why it's deferred:** Adds latency to every request, requires a separate prompt template, and introduces design questions (which model for classification? the same triage model or a different one?). The heuristic baseline comes first because it's cheaper and produces a clear finding on its own. See ADR 0008.

**What was done instead:** The heuristic guardrail is measured against the adversarial set and its limitations are documented. The expected finding — that pattern matching fails on obfuscated attacks — is itself valuable.

**Estimated effort to add:** Half a day. The evaluation framework already exists; adding a second layer means implementing the classifier prompt, wiring it into the guardrail service, and re-running the adversarial set.

---

## Multimodal input and multimodal injection defense

**What it would add:** The ability to accept image attachments on support tickets (screenshots of error messages, UI issues, etc.) and guardrails against multimodal injection (malicious text hidden in images that a vision model would read).

**Why it's deferred:** Requires a vision-capable model (Qwen 3.5 has vision variants but they are a different deployment surface), new pipeline plumbing for image handling, new evaluation criteria, and a new category of adversarial testing. Each of these is a meaningful scope expansion. See decision log, initial scope decisions.

**What was done instead:** The pipeline is text-only. Multimodal injection is documented in the threat model as a known threat category that is out of scope because the system does not accept the modality where the attack lives.

**Estimated effort to add:** 1–2 days for image handling pipeline, vision model integration, and basic multimodal adversarial testing.

---

## Authentication and role-based access control

**What it would add:** A login system with at least two roles — a "user" role that sees only the Triage tab, and an "admin" role that has access to the full dashboard including Metrics, Traces, and Experiments tabs.

**Why it's deferred:** Authentication is general web-engineering work, not LLM-engineering work. It does not land in the rubric language about understanding the LLM field. The build time is better spent on evaluation depth and the prompt injection investigation. See decision log, initial scope decisions.

**What was done instead:** All tabs are visible to all users. The instructor sees the full system during the demo without any login friction.

**Estimated effort to add:** Half a day for a minimal implementation (Gradio's built-in `auth` parameter for basic access gating, plus session-state-based tab visibility for role separation). A production-quality implementation with proper password hashing, session management, and role persistence would take longer.

---

## External alerting infrastructure

**What it would add:** Integration with real alerting systems (PagerDuty, Opsgenie, Slack webhooks) so that monitoring threshold breaches produce actionable notifications rather than log entries.

**Why it's deferred:** Adds external service dependencies, API keys, and configuration that complicate deployment and are disproportionate to the project's single-instance scale. See ADR 0009.

**What was done instead:** Alerting is log-based. Structured warnings are written to the application log with key=value formatting when thresholds are crossed. The concept of alerting is demonstrated; the infrastructure is not.

**Estimated effort to add:** A few hours for a single integration (e.g., Slack webhook). More for a full alerting stack.

---

## Real time-series database

**What it would add:** Metric storage in a time-series database (Prometheus, InfluxDB) with proper retention policies, downsampling, and purpose-built query languages for time-windowed aggregation.

**Why it's deferred:** SQLite with time-windowed queries against the trace table is sufficient at the project's data scale (hundreds of records). Adding a time-series database would mean another service to deploy, configure, and maintain. See ADR 0009.

**What was done instead:** Time-series queries hit the SQLite trace store directly. Monitoring dashboards compute rolling aggregates in Python from recent trace records.

**Estimated effort to add:** Half a day for basic Prometheus metric export + Grafana dashboard. More for production-quality retention and alerting rules.

---

## Larger and more diverse evaluation dataset

**What it would add:** A larger labeled dataset (100+ normal tickets, 30+ adversarial tickets) with broader category coverage, multiple difficulty levels, and enough samples for basic statistical significance testing.

**Why it's deferred:** Label quality matters more than label quantity at this project's scale. 20–30 well-labeled normal tickets and ~12 carefully-designed adversarial tickets are sufficient to reveal meaningful patterns in model behavior. Building a larger set would take time away from the investigation and documentation that the rubric rewards. See decision log, OD-7.

**What was done instead:** The dataset is small but deliberately designed: each adversarial ticket targets a specific attack category with a documented expected behavior, and the normal tickets cover the full category taxonomy.

**Estimated effort to add:** 1–2 days for dataset expansion, re-running all experiments, and updating the writeup.

---

## Multi-issue ticket detection and splitting

**What it would add:** Detection and handling of tickets that contain multiple distinct issues in a single submission (e.g., "my password won't reset AND my billing is wrong"). Currently the pipeline produces a single `TriageOutput` per ticket, which means one of the issues is under-served — the triage reflects whichever issue the model deemed primary, and the secondary issue receives no routing, severity, or escalation assessment.

**Scope of the improvement:**

1. A pre-LLM check (heuristic or LLM-based) that flags tickets likely to contain multiple distinct issues, based on structural cues (conjunctions joining unrelated topics, multiple question marks addressing different systems, explicit "also" / "separately" / "unrelated" markers).
2. A decision layer for flagged tickets: split into separate triage requests (each processed independently through the pipeline), route to human review for manual splitting, or prompt the user to resubmit as separate tickets.
3. Evaluation criteria for the detector (precision/recall on a labeled multi-issue subset) and for the splitter (whether each sub-ticket produces better triage than the combined original).

**Why it's deferred:** The current pipeline's contract is one ticket in, one `TriageOutput` out. Multi-issue handling requires redesigning this contract — either the pipeline returns a list of results, or it returns a single result with a "multi-issue detected" flag that triggers a secondary workflow. Both options affect the `TriageResult` discriminated union (ADR 0003), the trace schema (ADR 0005), the UI display, and the evaluation harness. The design surface is larger than the implementation.

**What was done instead:** The pipeline triages the ticket as a single unit. If the model's output reflects only one of the issues, the other is effectively dropped. This is a known limitation of the one-ticket-one-output design.

**Estimated effort to add:** 2–3 days. Includes: multi-issue detection heuristic or classifier (~0.5 day), pipeline contract redesign and splitting logic (~1 day), evaluation dataset with labeled multi-issue tickets and per-sub-ticket ground truth (~0.5 day), evaluation run and writeup (~0.5 day).

---

## Cross-family model comparison

**What it would add:** Comparing Qwen 3.5 against other model families (Llama, Mistral, Gemma, DeepSeek) on the same benchmark suite.

**Why it's deferred:** The project's comparison strategy is deliberately within-family to isolate model *size* as the variable without the confound of model *architecture*. Adding cross-family comparisons would muddy the size analysis and expand the eval matrix significantly.

**What was done instead:** The comparison stays within the Qwen 3.5 family (2B, 4B, 9B). The choice to stay within-family is documented in the decision log and model strategy section of [`PLAN.md`](PLAN.md).

**Estimated effort to add:** Half a day per additional family (pull models, verify structured output, run benchmark, add to results). The provider abstraction and eval harness support this with no code changes — just adding new provider instances to the runner's list.

---

## Category-distribution drift indicator

**What it would add:** A chart in the Live Metrics section showing the distribution of assigned categories over time, flagging when a single category dominates recent traffic (>70%) as a signal that input distribution or model behavior has shifted.

**Why it's deferred:** Requires enough live traffic to produce a meaningful distribution. During a 5-minute demo, the volume of live requests is too low to show drift. The chart would render as single bars or be empty, undermining rather than supporting the demo narrative.

**What was done instead:** The Metrics tab shows rolling aggregate metrics (success rate, latency, retry rate) that are meaningful even at low traffic volumes. Category distribution can be inferred from the Traces tab's filterable list.

**Estimated effort to add:** A few hours. The trace data already includes category in `triage_output_json`. Implementation is a time-bucketed aggregation query and a Gradio bar chart.

---

## ~~Versioned container image tags~~ — DONE

**Implemented** in the `feature/release-workflow-v2` branch. The `docker-publish.yml` workflow now triggers on `v*` tag pushes in addition to `main` pushes, and produces `:latest`, `:v1.0.0` (full semver), and `:v1.0` (major.minor) image tags via the Docker metadata action. The automated release workflow (`.github/workflows/release.yml`) creates tags on merge to `main`, completing the end-to-end automation.

---

## Log-based alerting

**What it would add:** Structured log warnings (`WARN [monitoring] threshold_breached: p95_latency=6200ms > limit=5000ms`) emitted when configured thresholds are crossed (p95 latency > 5s, retry rate > 20%, single category > 70% of recent traffic). See [ADR 0009](adr/0009-monitoring-distinct-from-benchmarking.md) for the threshold values and log format.

**Why it's deferred:** Log-based alerts are invisible to the audience during a demo unless specifically surfaced in the UI. The monitoring value is real but the demo impact is low compared to the visible dashboard components.

**What was done instead:** The Live Metrics section shows the same threshold-relevant numbers (p95 latency, retry rate) as KPI cards, making threshold violations visually apparent without log parsing.

**Estimated effort to add:** A few hours. The metrics service already computes the relevant values; adding threshold checks and structured log output is straightforward.

---

## Prompt v2 comparison

**What it would add:** A meaningfully different prompt v2 authored against the same `TriageOutput` schema, measured against v1 on the same model (9B) and dataset (35-ticket normal set) with the same n=5 replication methodology as Phase 3. Produces a quantitative answer to "how much does prompt design contribute vs. model selection?" — one of the four experiments in the original project plan.

**Why it's deferred:** Phase 3 replication (n=5, production config — see `docs/evaluation-checklist.md` § Phase 3 Replication) showed all three models (2B, 4B, 9B) achieve 100% JSON validity and first-pass validity is ~100%. Reliability headroom is zero, so v2 cannot improve the structural-output dimension that was the phase's primary framing. Category-accuracy headroom is a narrow 2.8pp band between the 4B (80.6%) and 9B (83.4%) — v2 could measure inside that band, but the measurement is less informative than the phase was designed to produce. Time budget redirected to Phase 7 deliverables (deployment docs, cloud-model documentation, cost-analysis completion, demo materials) which produce more visible value. See `docs/decisions/decision-log.md` 2026-04-19 "Phase 6 skipped" entry for the full rationale.

**What was done instead:** E4 runs with v1 only. `run_prompt_comparison.py` already accepts a `prompt_versions: list[str]` parameter and iterates dynamically, so a future v2 can be added without runner changes. The v1 baseline metrics per model are captured in E1 (Experiment 1: Model size comparison).

**Estimated effort to add:** 1-2 days total:

- ~Half a day to author `src/ticket_triage_llm/prompts/triage_v2.py` (a meaningfully different prompt, not a tweak — e.g., restructured system prompt, different taxonomy framing, explicit few-shot examples, or JSON-schema-in-prompt). Register v2 in `src/ticket_triage_llm/services/prompt.py::get_prompt()`.
- ~A few hours to run `uv run python -m ticket_triage_llm.eval.runners.run_prompt_comparison --prompt-versions v1,v2` at n=5 on the 9B.
- ~Half a day to author `docs/prompt-versions.md` documenting what changed between v1 and v2 and why, and to analyze the comparison results with proper stddev reporting per the Phase 3 replication pattern.
- Trigger condition: do this if 9B category accuracy (~83%) becomes a bottleneck in any real-world use of this system, or if a reviewer specifically wants the v1-vs-v2 comparison deliverable.

---

## Eval-runner polish items (PR review carryover)

**What they are:** Six small code-quality items surfaced during Phase 4 PR review that didn't reach the bar of "fix in this branch." Tracked in the cleanup branch's scope review (2026-04-19) and deferred after explicit evaluation of value vs. change surface.

**Why deferred:**

- **I1 — `detected_by="parser"` hardcoded in runner's trace reconstruction.** The field is a reconstruction artifact read only by compliance analysis, not an operational field. Fixing it surgically for a label that never surfaces anywhere practical. Cost: an hour for analysis + tests; value: near zero.
- **I3 — Output filename collision on short tags.** `provider.name.split(":")[-1]` would collide only if two different providers produced the same tag. None of the three Qwen models do; no future provider is planned. Guards against a problem that doesn't exist.
- **I4 — `adversarial_to_ticket_record` fabricates ground truth silently.** The fabrication is intentional (adversarial tickets don't have category/severity ground truth; the compliance checker uses a different signal). Adding a sentinel changes nothing behaviorally. Docstring is sufficient.
- **I6 — Non-atomic JSON writes in runner.** An interrupted write could leave a partial JSON on disk. But the runner already has `--start-run`/`--end-run` resume support — a partial file on disk just gets overwritten on re-run. Paying to fix a problem that resume already handles.
- **I8 — Missing compliance dispatch tests for a-003, a-004, a-009, a-011.** Adding coverage for a module whose dispatch logic is already well-tested on other ticket IDs. Would catch bugs that existing tests miss only if the compliance logic has per-ticket branching — which it doesn't.
- **S9 — `_make_compliance` in test file duck-types instead of importing real `ComplianceCheck`.** Style nit. The duck type works correctly and the test passes. Import-path change only, no behavior.

**What was done instead:** The two real latent bugs (I2 — corrupt trace crashes pass; I5 — unknown ticket_id raises KeyError) and one observability win (I7 — unknown ticket_id silently bucketed) were fixed in the cleanup branch with regression tests. Docstring-staleness items (N1, N3) were also fixed. The net result is 3 real fixes shipped and 6 cosmetic items documented as intentionally-deferred.

**Estimated effort to revisit:** Maybe 2-4 hours for all six combined if a future reviewer specifically requests them. None are blocking anything.

---

## API route dependency injection refactor

**What it would add:** Refactor `src/ticket_triage_llm/api/triage_route.py` from module-level globals (currently `configure(registry, trace_repo, guardrail_max_length)` patches module state) to FastAPI's idiomatic `app.state` / `Depends()` pattern for request-scoped dependency injection.

**Why it's deferred:** This is not cleanup — it's an architectural change to how FastAPI dependency injection flows through the app. The current globals pattern works correctly. Refactoring adds review surface (tests to update, startup-order changes to verify, integration test for the `/docs` Swagger path) without correctness improvement. The change belongs on its own PR with a design note, not bundled into a cleanup branch.

**What was done instead:** The current module-level globals pattern is documented as intentional in `docs/adr/0006-single-app-gradio-architecture.md` and works cleanly for the single-instance-per-process deployment topology. A future multi-app or testability push might motivate the refactor; the current deployment does not.

**Estimated effort to add:** ~4-6 hours. Update `api/triage_route.py` to declare dependencies via `Depends()`, migrate `configure()` callers in `app.py` to set `app.state.registry`, `app.state.trace_repo`, update the route handler to accept dependencies as parameters, update all integration tests that touched `configure()` state, and verify Swagger docs still render.

---

## Pre-repair error in `TriageFailure.message` on repair `ProviderError`

**What it would add:** When the repair-retry call to the provider raises `ProviderError`, the resulting `TriageFailure` currently reports only the `ProviderError` message, losing the original validation error that triggered the repair attempt. The improvement: preserve both error sources in the failure message for better diagnostic signal when examining failed retries in the Traces tab.

**Why it's deferred:** Improves error-message informativeness in a case (repair-retry raises network error) that's rare under production config (retry rate ~0-3%). The failure envelope still returns correctly and the ticket still fails gracefully; the message is just less detailed than it could be. Observability, not correctness.

**What was done instead:** The current `TriageFailure` produces a correct typed failure with the `ProviderError` message. Users debugging rare repair-retry failures can cross-reference the trace's `retry_count > 0` field and the prior `validation_status` to reconstruct what the original validation error was.

**Estimated effort to add:** ~1-2 hours. Modify `services/retry.py` to capture the pre-repair validation error before calling the provider, then include it in the `TriageFailure.message` constructed on `ProviderError`. Add a unit test covering the pre-repair-preserved case.
