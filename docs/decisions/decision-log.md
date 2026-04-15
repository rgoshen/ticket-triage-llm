# Decision Log

A chronological log of scope, framing, and strategy decisions for `ticket-triage-llm`.

This is not the place for architectural decisions — those belong in [ADRs](decisions/). This is the place for *what the project is, isn't, and why*: scope boundaries, things considered and rejected, framing choices, and the reasoning trail behind them.

Newest entries at the top.

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
- Qwen 3.5 27B and larger (consumer-hardware constraint)
- TypeScript / Node / React stack (see [ADR 0001](decisions/0001-language-and-stack.md))
- Two-tickets-in-one adversarial category (see above)

### Documentation strategy

Documentation will be split across three distinct artifact types, each with a clear purpose:

1. **The project plan** (`docs/llm-ticket-triage-plan.md`) — the working document describing what is being built, how, and why. Updated as the project evolves.
2. **Architecture Decision Records** (`docs/decisions/`) — formal, structured records of *architectural* decisions only, in `adr-tools` format. Each ADR is one decision, one file, immutable once accepted (superseded by later ADRs if needed).
3. **The decision log** (this file) — chronological, informal, captures scope, framing, and strategy decisions that are not architectural. Newest entries at the top.

The instructor's emphasis on "factors weighing" in decision-making means that the *process* of decision-making is itself a graded artifact, not just the final answers. The decision log and the ADRs together form the trail of that process.
