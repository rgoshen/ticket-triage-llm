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

## Cross-family model comparison

**What it would add:** Comparing Qwen 3.5 against other model families (Llama, Mistral, Gemma, DeepSeek) on the same benchmark suite.

**Why it's deferred:** The project's comparison strategy is deliberately within-family to isolate model *size* as the variable without the confound of model *architecture*. Adding cross-family comparisons would muddy the size analysis and expand the eval matrix significantly.

**What was done instead:** The comparison stays within the Qwen 3.5 family (2B, 4B, 9B). The choice to stay within-family is documented in the decision log and model strategy section of PLAN.md.

**Estimated effort to add:** Half a day per additional family (pull models, verify structured output, run benchmark, add to results). The provider abstraction and eval harness support this with no code changes — just adding new provider instances to the runner's list.
