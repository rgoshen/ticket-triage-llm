# 0010. Non-actionable and ambiguous input handling

## Status

Accepted

## Context

The ticket triage pipeline is designed around the assumption that incoming tickets describe real support issues. Production support forms routinely receive submissions that violate this assumption in two ways:

1. **Non-actionable input** — submissions that are not real tickets at all: gibberish, form tests, irrelevant prose, or positive feedback with no issue described. These are not malicious (and therefore not prompt injection), but they have no meaningful triage answer.

2. **Ambiguous severity** — submissions that describe a real observation but provide no indication of urgency, business impact, or scope. The triage schema requires a `severity` value, so the model must select one even when the input provides no signal.

Both scenarios need a defined pipeline behavior. Without one, the model will silently produce a confident-looking triage result for junk input, and the pipeline will route it to a real team — wasting human attention and eroding trust in the system.

The existing architectural components that could handle this are:

- **The pre-LLM guardrail** (ADR 0008) — currently scoped to injection defense (heuristic pattern matching for override instructions, PII, encoding tricks)
- **The model itself** — could be prompted to recognize and flag these cases
- **The post-LLM semantic validation layer** (ADR 0002) — currently performs cross-field consistency checks on schema-valid output

The question is where in the pipeline this detection belongs.

## Options Considered

### Option A: Guardrail-level filtering (pre-LLM)

Expand the guardrail (ADR 0008) to detect non-actionable input before it reaches the model. This could use content-length thresholds, keyword absence heuristics ("no problem-indicating words found"), or a lightweight text classifier.

### Option B: Model classifies, semantic validation flags (post-LLM)

Let non-actionable input pass through the guardrail and reach the model. The model classifies as `category: "other"` with low confidence. The semantic validation layer (ADR 0002) adds a new check: if the output combines `category: "other"`, low confidence (below a configurable threshold), and a summary that does not describe an actionable issue, the output is flagged as non-actionable. The pipeline returns a valid `TriageSuccess` with a non-actionable flag rather than a `TriageFailure`.

For ambiguous severity, the model defaults to `severity: "low"` and the confidence score is the signal that the assignment was uncertain. No special validation behavior — the output is valid, just less certain.

### Option C: Dedicated classifier model (pre-LLM)

Add a second, smaller model as a content-quality gate before the triage model. This model would classify input as "real ticket" vs "not a ticket" and reject non-actionable submissions before they consume triage model resources.

## Decision

We chose **Option B: Model classifies, semantic validation flags**.

The pipeline handles non-actionable and ambiguous input as follows:

- **Non-actionable input** bypasses the guardrail (no injection patterns), reaches the model, and is classified as `category: "other"` with low confidence. The semantic validation layer detects the combination and flags the output as non-actionable. The result is a valid `TriageSuccess` with a flag the UI can surface — not a `TriageFailure`.

- **Ambiguous severity** is handled by the model defaulting to `severity: "low"` with a lower confidence score. No special validation behavior is triggered — the output is valid but uncertain, and the confidence score communicates that uncertainty.

- **Confidence is the unified signal for "the model had to guess."** Both scenarios use the same mechanism. This keeps the pipeline simple — one field, one interpretation, two use cases.

## Rationale

1. **The guardrail's scope should remain narrow.** ADR 0008 deliberately scoped the guardrail to injection defense with heuristic pattern matching. Expanding it to detect "not a real ticket" would require either natural-language understanding (which is the model's job) or brittle keyword heuristics that would misclassify terse but legitimate tickets. A guardrail that blocks real tickets is worse than one that lets junk through — false negatives are annoying, false positives lose customer trust.

2. **The model is already doing the work.** A model that can classify a ticket into six categories can also recognize that input doesn't fit any of them. Asking it to express that recognition via `category: "other"` and low confidence requires no new infrastructure — just clear prompting (already present in `triage_v1.py`, rule 3: "The confidence score should reflect how clearly the ticket maps to a single category and severity").

3. **Semantic validation is the right layer for post-classification quality checks.** ADR 0002 established that the validator-first pipeline performs cross-field consistency checks on schema-valid output. "Is this output actually describing a real issue?" is a cross-field check — it looks at category, confidence, and summary together. It belongs in the same layer as the other semantic checks, not in a separate system.

4. **A dedicated classifier model (Option C) adds complexity without proportional value.** Running a second model doubles inference latency for every request, requires its own evaluation, its own failure modes, its own retry logic, and its own trace records. For a system processing support tickets on consumer hardware, the resource cost is not justified when the primary model can handle the classification itself.

5. **Returning a flagged success rather than a failure preserves the pipeline contract.** A non-actionable ticket is not a pipeline failure — the pipeline did its job (classified the input) and arrived at the correct conclusion (this isn't actionable). The `TriageFailure` union member (ADR 0003) is reserved for actual failures: parse errors, schema violations, model unreachable. Treating "not a real ticket" as a failure would conflate content quality with system reliability.

## Tradeoffs

- **Upside:** No new infrastructure. No second model. No guardrail complexity creep. Confidence as a unified signal is simple to implement, simple to test, and simple to explain in the presentation. The semantic validation check is a small addition to an existing layer.

- **Downside:** The model consumes full inference resources on junk input before the system can flag it. In a high-volume production system, this would be a cost concern — every garbage submission costs the same tokens as a real ticket. On consumer hardware with local inference, the cost is latency (seconds per junk ticket), not money.

- **Why we accept the downside:** The project's hardware context is a single-user demo system on consumer hardware, not a high-throughput production endpoint. The volume of non-actionable input in a demo is near zero. If this were a real production system at scale, Option C (dedicated classifier) would be worth revisiting — and that's documented in `docs/future-improvements.md`.

## Consequences

- The guardrail (ADR 0008) is **not modified**. Its scope remains injection defense only.
- The semantic validation layer (ADR 0002) gains a new check: non-actionable ticket detection based on the combination of `category: "other"`, confidence below a configurable threshold, and summary content analysis.
- The `TriageSuccess` schema may need a `non_actionable` flag (or equivalent) so the UI can surface the distinction between "triaged normally" and "triaged but flagged as non-actionable." This is a schema decision to be finalized during implementation.
- The triage prompt (`triage_v1.py`) already instructs the model to use confidence to express uncertainty (rule 3). No prompt changes are required.
- The evaluation dataset includes 3 non-actionable tickets (n-031 through n-033) and 2 ambiguous-severity tickets (n-034, n-035) to test this behavior. These are in the normal set, not the adversarial set, because they are edge cases of legitimate usage, not attack vectors.
- Confidence becomes a load-bearing pipeline signal, not just a display field. Any future changes to how confidence is computed or thresholded should be treated as pipeline-affecting changes and documented accordingly.

## Alternatives Not Chosen

- **Guardrail-level filtering (Option A):** Rejected because detecting "not a real ticket" requires natural-language understanding that the guardrail is not designed to provide. Expanding the guardrail's scope from injection defense to content quality filtering would blur its architectural purpose, increase its false-positive risk, and create a maintenance burden for a problem the model already solves. The guardrail should stay narrow and testable.

- **Dedicated classifier model (Option C):** Rejected because it doubles inference cost per request, adds a second model to evaluate and maintain, and introduces new failure modes — all for a problem that the primary model handles adequately via confidence scoring. Appropriate for high-volume production systems but disproportionate for a single-user demo on consumer hardware. Documented as a potential future improvement.
