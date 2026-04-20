# 12. ADR framing retrospective

Date: 2026-04-19

## Status

Accepted

## Context

This project was built as a course deliverable, and the early ADRs were written under time pressure with the rubric as a visible constraint. Reviewing the full ADR set after the build revealed a pattern: several ADRs justify decisions partly or primarily by citing rubric criteria, grading tiers, instructor expectations, or demo scenarios rather than standing on independent engineering reasoning.

The affected ADRs are:

| ADR | Rubric-framing examples | What the real engineering driver was |
|-----|------------------------|--------------------------------------|
| **0001** (Language and Stack) | "the rubric explicitly grades the quality of the system (Inference Pipeline worth 15 points)"; "choosing a stack that scores well on the rubric's implementation criteria" | Python + Gradio is the fastest path to a working end-to-end system under a fixed time budget. The ecosystem (Pydantic, OpenAI client, LLM tooling) is mature. Opportunity cost of unfamiliar tooling on the critical path was the real risk. |
| **0002** (Validator-First Pipeline) | "Maximizing success rate is a grading criterion"; "The grading rubric rewards engineering controls" | Validation before inference catches malformed input and prevents wasted LLM calls. Bounded retry prevents pathological infinite loops on systematically bad prompts. This is standard defensive design for any system consuming untrusted model output. |
| **0003** (Error Contract) | "The eval runner needs to measure success rates for grading purposes"; "Grading depends on this distinction" | A discriminated union forces callers to handle both success and failure explicitly. It prevents silent data loss and makes the error contract machine-readable and testable. This is sound type design independent of evaluation. |
| **0005** (SQLite Traces) | "The instructor or TA will look at individual traces"; "the demo scenario requires the instructor to be able to inspect a ticket's full journey" | SQLite + repository pattern is the correct choice for local structured data at modest scale. Traces serve operational debugging (why did this request fail?) and historical analysis (what patterns are emerging?). Both purposes exist independent of any demo. |
| **0006** (Gradio Architecture, addendum) | "After reviewing the rubric's Environment Setup criterion ('the model is accessible via an API endpoint')" | A REST API is standard practice for any system that might have multiple consumers. The initial ADR dismissed the API as "ceremony" because the only client was Gradio in the same process — but an API provides programmatic access, documentation via OpenAPI, and testability. The rubric was the trigger; the engineering justification stands alone. |
| **0007** (Docker Deployment) | "Environment Setup is worth 15 points"; "the 'Excellent' tier requires the model to be 'successfully deployed'"; "The instructor or TA needs to actually run it" | Keeping Ollama on the host preserves GPU/MLX acceleration on Apple Silicon — Docker on Mac/Windows cannot access Metal. That architectural constraint is real and hardware-specific. Reproducible deployment is an engineering requirement for any system intended to run on more than the developer's machine. |
| **0009** (Monitoring vs Benchmarking) | "The rubric's 'Inference Pipeline' criterion explicitly asks for 'monitoring and metrics display'" | Monitoring and benchmarking serve different purposes and should be visually and conceptually separated. Conflating them produces bad telemetry — benchmark runs flood live dashboards and obscure operational health. This is standard observability practice. |
| **0010** (Non-Actionable Input) | "The demo scenario and eval dataset need handling rules"; "Grading depends on the system handling edge cases gracefully" | Every input-handling system needs rules for ambiguous or non-actionable inputs. Typed failure categories (`non_actionable`, `ambiguous_severity`) let callers understand what happened. This is fundamental error handling. |

**ADRs that do not exhibit this pattern:** 0004 (Provider Protocol), 0008 (Heuristic Guardrail), 0011 (Default Model Selection). These stand on independent engineering or empirical reasoning throughout.

## Decision

We are not rewriting the affected ADRs. ADRs are historical records of decisions as they were made, and the rubric-framing reflects where the project's thinking was at the time.

Instead, we document the pattern here as a process retrospective:

1. **The framing was the problem, not the decisions.** In every case above, the underlying engineering reasoning is sound and would justify the decision even without a rubric. The rubric accelerated documentation of those reasons but also introduced framing that obscures the real drivers.

2. **The pattern improved over time.** ADRs 0001-0007 (written during Phases 0-2) lean on rubric language. ADRs 0008-0011 (written during Phases 3-7) shift toward empirical evidence and engineering reasoning. The team moved from "what does the rubric require?" to "what does the evidence show?" as the project matured.

3. **Principle for future ADRs:** Justify decisions on engineering merit — opportunity cost, execution risk, empirical evidence, operational requirements. External constraints (rubrics, deadlines, stakeholder requests) may *trigger* a decision, but they are not *reasons* for it. If the only justification for a choice is "the rubric says so," the choice needs better reasoning or a different approach.

## Consequences

- Future ADRs in this project (if any) will follow the framing principle above.
- Readers of ADRs 0001-0003, 0005-0007, 0009, and 0010 should look past the rubric language to the engineering reasoning underneath. The decisions are sound; the articulation would be sharper today.
- This ADR itself serves as evidence that the project's decision discipline improved over the build — which is arguably the kind of learning the course was designed to produce.
