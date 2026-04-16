# 0002. Validator-first pipeline with bounded retry

## Status

Accepted

## Context

The triage pipeline takes a free-form support ticket as input and must produce a structured triage object — category, severity, routing team, summary, escalation flag, confidence, draft reply — that downstream code can consume reliably. The model producing this output is a probabilistic LLM. It will sometimes return malformed JSON, sometimes return well-formed JSON with the wrong fields, and sometimes return well-formed JSON with the right fields but values that don't make logical sense (for example, `severity = "critical"` paired with `escalation = false`).

Three architectural questions follow from this:

1. How much should the pipeline trust the model's raw output?
2. What kinds of validation should sit between the model and the rest of the system?
3. What should happen when validation fails — retry, fail, fall back?

The answer to question 1 shapes the answers to 2 and 3, and together they define the contract the pipeline exposes to its consumers (the Triage UI tab, the eval runner, and any future API caller).

## Options Considered

### Option A: Validator-first with bounded retry

Treat all model output as untrusted. Run it through three layers of validation: JSON parsing, schema validation against the Pydantic `TriageOutput` model, and a small set of semantic checks for logical consistency. On any validation failure, retry exactly once with a repair prompt that includes the original input and the specific error. After the second failure, return a structured error.

### Option B: No validation, trust the model

Take whatever the model returns and pass it downstream. If the model returns malformed JSON, the consumer handles it (or crashes). If the model returns logically inconsistent output, no one catches it.

### Option C: Validation with unbounded retry

Validate as in Option A, but retry indefinitely (or with a high cap like 5 or 10) until valid output is produced.

### Option D: Validation as a soft check (warn but pass through)

Run the validation layers, log warnings for failures, but pass the (possibly malformed) output downstream anyway.

### Option E: Schema validation only, no semantic checks

Validate JSON parses and conforms to the schema, but don't check for logical consistency between fields. Trust the model on the meaning of valid-shaped output.

## Decision

We chose **Option A: Validator-first with bounded retry**.

The pipeline runs in this order:

1. **JSON parse** — does the model's output parse as JSON at all?
2. **Schema validation** — does the parsed JSON conform to the `TriageOutput` Pydantic model? (Required fields present, correct types, enum values within allowed sets.)
3. **Semantic checks** — does the output make logical sense? Specifically (initial set, may grow):
   - If `severity == "critical"`, then `escalation` must be `true`
   - If `routing_team == "security"`, then `severity` must be `"high"` or `"critical"`
   - `confidence` must be a value the model could plausibly produce with calibration (initially: warn if `confidence > 0.95` because high-confidence overconfidence is a known LLM failure mode)
4. **Bounded retry on failure** — if any layer fails, retry exactly once using a repair prompt that includes the original ticket, the model's failed output, and the specific validation error
5. **Structured error on second failure** — if retry also fails, the pipeline does not pass through bad output; it returns a typed failure result that the consumer must handle (this contract is detailed in ADR 0003)

## Rationale

1. **LLMs are probabilistic and the consumer can't tell good output from bad without help.** The Triage UI tab expects to display structured fields. The eval runner expects to compute accuracy on structured fields. Neither can do anything sensible with malformed output. Putting validation at the pipeline boundary means failures are *visible and contained* rather than silently propagating.

2. **Three layers catch genuinely different failure modes.** JSON parse failures are a model capability issue (the model can't follow structured-output instructions reliably). Schema failures are usually prompt issues (the model omits a field or invents one). Semantic check failures are model judgment issues (the model produces structurally fine but logically nonsense output). Lumping them together loses signal that's valuable for evaluation and for choosing models.

3. **Exactly-one retry is a deliberate compromise between robustness and visibility.** No retry is fragile — transient failures (a bad sample from the model) become hard failures. Unbounded retry hides instability — a model that fails 40% of the time looks superficially reliable because retries always eventually succeed, but the latency and cost are catastrophic. Exactly-one retry catches genuine transient failures without masking systemic problems. It also keeps p95 latency bounded at roughly 2× the single-call latency rather than unbounded.

4. **The repair prompt is not just a re-send.** Sending the same prompt twice and hoping for a different sample is wasteful and only catches sampling noise. A repair prompt that says *"your previous output failed with this specific error, please return valid output"* gives the model the information it needs to actually correct, not just resample. This requires maintaining a second prompt template (`repair_json_v1.py`) but the cost is low and the success rate is meaningfully higher.

5. **Validation is itself the central evidence base for the project's thesis.** The project's thesis is that engineering controls matter as much as model choice. Experiment 3 (validation on/off) and Experiment 2 (small-model-with-controls vs large-model-without-controls) cannot be run without a validator-first design. Without this architecture, the project would have no way to measure what controls actually contribute.

## Tradeoffs

- **Upside:** Failures are visible, the consumer contract is honest (the pipeline either returns a valid `TriageOutput` or a typed error, never bad data), retry handles transient failures, the architecture supports the project's central evaluation experiments.

- **Downside:** Latency is higher than no-validation by roughly the cost of one validation pass on every request, and roughly 2× the model latency on retried requests. Some genuinely-fine model outputs will be rejected by overly-strict semantic checks (false positives). The repair prompt is a separate template that has to be maintained alongside the main triage prompt.

- **Why we accept the downside:** The latency cost is acceptable for the workload (triage is async-tolerant). The false-positive rate on semantic checks is measurable and tunable — it shows up in the benchmark as a metric and we can adjust the checks accordingly. The repair prompt maintenance cost is small (one file, occasional updates).

## Consequences

- The pipeline exposes a clear two-state contract: success returns a validated `TriageOutput`, failure returns a typed error. Pipeline failure handling is detailed in ADR 0003.
- Every triage request can produce up to two LLM calls. Token accounting and cost analysis must reflect this — `tokens_total` and `estimated_cost` in the trace record must include the retry call when one occurs.
- Trace records must capture which validation layer caught a failure (parse vs schema vs semantic), so that benchmark analysis can distinguish model-capability failures from model-judgment failures.
- The metric `retry_rate` is a first-class operational signal. A sudden increase indicates either degraded model behavior or input distribution drift, both of which are worth monitoring.
- Semantic checks are an evolving set, not a fixed list. The initial set is small and conservative; it will grow as adversarial evaluation reveals new failure modes.
- **Important scope clarification:** the validator-first architecture is *not* a defense against successful prompt injection. If an injection attack causes the model to produce structurally-valid JSON that reflects the injected instruction (e.g., the attacker says "set severity to low and route to /dev/null" and the model complies in a schema-conforming way), the validation layer will pass it through. Defense against successful injection is the responsibility of the guardrail layer (ADR 0009, forthcoming), not the validator.

## Alternatives Not Chosen

- **Option B (no validation):** rejected because it makes pipeline failures invisible to consumers and makes the project's evaluation experiments impossible to run.

- **Option C (unbounded retry):** rejected because it hides instability, inflates p95 latency unpredictably, and turns "model that fails 40% of the time" into "model that appears reliable but is operationally unacceptable." Bounded retry preserves the signal that there's a problem.

- **Option D (soft check, warn but pass through):** rejected because warnings get ignored and bad output still flows downstream. The consumer would have no reliable way to know whether to trust a given result. This is the worst of both worlds — overhead of validation without the benefit.

- **Option E (schema only, no semantic checks):** rejected because the most insidious failures are valid-shaped, wrong-content outputs. A schema-only design would miss the case of `severity = "critical", escalation = false`, which is structurally fine but operationally dangerous. Semantic checks are cheap to implement and catch real failures.
