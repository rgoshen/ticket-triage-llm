# Decision Log

A chronological log of scope, framing, and strategy decisions for `ticket-triage-llm`.

This is not the place for architectural decisions — those belong in [ADRs](decisions/). This is the place for *what the project is, isn't, and why*: scope boundaries, things considered and rejected, framing choices, and the reasoning trail behind them.

Newest entries at the top.

---

## 2026-04-15 — API endpoint: FastAPI alongside Gradio for rubric compliance

The rubric's Environment Setup criterion requires the model to be "accessible via an API endpoint." The original single-app Gradio architecture (ADR 0006) did not explicitly address this. Gradio auto-generates internal API endpoints, but these are framework-determined, not project-designed, and lack Swagger/OpenAPI documentation.

Resolution: add a minimal FastAPI layer alongside Gradio in the same process. FastAPI is the outer app; Gradio is mounted inside it as a sub-application. One new route (`POST /api/v1/triage`) calls the same `triage_service.run_triage()` that the Gradio Triage tab calls. Swagger UI is auto-generated at `/api/v1/docs` from the existing pydantic request/response models.

This does not create a client/server split — it's one process, one codebase, one Docker container. The service layer is unchanged. The instructor can open `/api/v1/docs` in a browser, submit a triage request via Swagger, and see the structured result without using the Gradio UI.

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

| Category | Target count | What it tests |
|---|---:|---|
| Direct prompt injection | 3–4 | Explicit attempts to override model behavior |
| Direct injection with obfuscation | 2 | Base64, language switching, invisible Unicode — tests whether guardrails are semantic or pattern-matching |
| Indirect injection via quoted content | 2–3 | Malicious instructions inside quoted emails, error messages, or log excerpts |
| PII / data leak triggers | 1–2 | Fake credit card numbers or other PII that should trigger a guardrail |
| Hostile / abusive language | 1 | Emotionally charged but legitimate tickets |
| Length extremes | 1 | Very short and/or very long input |
| Multilingual | 1 | Non-English ticket |

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
- TypeScript / Node / React stack (see [ADR 0001](decisions/0001-language-and-stack.md))
- Two-tickets-in-one adversarial category (see above)

### Documentation strategy

Documentation will be split across three distinct artifact types, each with a clear purpose:

1. **The project plan** (`docs/llm-ticket-triage-plan.md`) — the working document describing what is being built, how, and why. Updated as the project evolves.
2. **Architecture Decision Records** (`docs/decisions/`) — formal, structured records of *architectural* decisions only, in `adr-tools` format. Each ADR is one decision, one file, immutable once accepted (superseded by later ADRs if needed).
3. **The decision log** (this file) — chronological, informal, captures scope, framing, and strategy decisions that are not architectural. Newest entries at the top.

The instructor's emphasis on "factors weighing" in decision-making means that the *process* of decision-making is itself a graded artifact, not just the final answers. The decision log and the ADRs together form the trail of that process.
