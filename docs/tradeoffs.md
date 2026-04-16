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
