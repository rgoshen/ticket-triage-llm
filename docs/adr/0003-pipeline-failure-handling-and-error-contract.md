# 0003. Pipeline failure handling and error contract

## Status

Accepted

## Context

The triage pipeline can fail in multiple distinct ways: the guardrail can block an input as suspected prompt injection, the model server (Ollama) can be unreachable or time out, the model's output can fail JSON parsing even after a repair retry, the parsed output can fail schema validation after retry, or the schema-valid output can fail semantic checks after retry. Each of these failures has different implications for the consumer: a guardrail block is a *correct* defensive behavior, a model timeout is an infrastructure problem, a parse failure after retry is a model-capability signal, and a semantic failure after retry is a model-judgment signal.

The pipeline has at least two distinct consumers: the Triage tab in the Gradio UI (which needs to display something to a human) and the eval runner (which needs to compute accuracy and other metrics across many requests). Both need to know not just *that* something failed but *what* failed and *where* in the pipeline. A future API consumer would need the same.

ADR 0002 establishes that the pipeline does not pass through bad data and does not silently fail. This ADR defines what it does *instead* — the shape of the failure result, the categorization of failures, and the contract consumers can rely on.

## Options Considered

### Option A: Typed two-state contract (success or typed failure)

The pipeline returns a `TriageResult` which is one of two things: a `TriageOutput` (validated success) or a `TriageFailure` (structured failure with category, detected-by layer, error message, and any partial information). The consumer always pattern-matches on which one it received. No exceptions cross the pipeline boundary; internal exceptions are caught and converted to `TriageFailure`.

### Option B: Raise exceptions and let consumers handle them

The pipeline raises typed exceptions (`GuardrailBlockedError`, `ModelUnreachableError`, `ParseFailureError`, etc.) and consumers wrap calls in try/except.

### Option C: Return None on any failure

The pipeline returns either a `TriageOutput` or `None`. Consumers check for `None` and decide what to do.

### Option D: Return partial data with no structured failure indicator

The pipeline always returns a `TriageOutput` shape, but with fields populated as well as possible — empty strings for fields it couldn't fill, `severity = "unknown"` etc. No separate failure type.

### Option E: Pretend failures don't happen, return last-known-good output

On failure, return whatever the previous successful triage was, or a hardcoded default. Log the failure but don't surface it.

## Decision

We chose **Option A: typed two-state contract**.

The pipeline returns a `TriageResult`, defined as a discriminated union:

```python
from typing import Literal, Union
from pydantic import BaseModel
from .triage_output import TriageOutput

class TriageFailure(BaseModel):
    status: Literal["failure"] = "failure"
    category: Literal[
        "guardrail_blocked",
        "model_unreachable",
        "parse_failure",
        "schema_failure",
        "semantic_failure",
    ]
    detected_by: Literal["guardrail", "provider", "parser", "schema", "semantic"]
    message: str  # human-readable description of what went wrong
    raw_model_output: str | None = None  # if the model produced something, even if unusable
    retry_count: int  # 0 or 1 — was retry attempted?

class TriageSuccess(BaseModel):
    status: Literal["success"] = "success"
    output: TriageOutput
    retry_count: int  # 0 if first try succeeded, 1 if retry succeeded

TriageResult = Union[TriageSuccess, TriageFailure]
```

The pipeline guarantees:

1. It always returns a `TriageResult`. It never raises an uncaught exception to its consumer.
2. A `TriageSuccess` carries a fully validated `TriageOutput` — every field is present, every type is correct, every semantic check passed.
3. A `TriageFailure` carries enough information for the consumer to decide what to display, log, or count. It distinguishes the five failure categories explicitly.
4. Internal exceptions (network errors, timeouts, JSON library exceptions) are caught at the pipeline boundary and converted into the appropriate `TriageFailure` category.

## Rationale

1. **Different failure categories mean different things to consumers.** A guardrail block is a *correct* outcome — the system did exactly what it was supposed to do, and the UI should display "this input was blocked as suspicious" rather than "an error occurred." A model-unreachable error is an infrastructure problem and should prompt the user to retry later. A parse-after-retry failure is a model-capability signal that's interesting for evaluation. Collapsing these into one undifferentiated "error" loses signal that consumers actually need.

2. **Pattern-matching on a typed result is more robust than try/except.** Exceptions are easy to forget to catch — a missing `except` clause becomes a runtime crash. A typed result that requires the consumer to handle both branches makes failure handling part of the type contract: the type checker enforces it. This is the same reasoning behind `Result<T, E>` in Rust and `Either` in functional languages.

3. **Returning `None` loses information.** A consumer that gets `None` knows something failed but not what or why. They can't decide whether to retry, escalate, log, or display a specific message. The information cost of `None` is high; the structural cost of a typed failure is low.

4. **Partial data without a failure indicator is the worst option.** Returning `severity = "unknown"` looks valid to downstream code that doesn't know to check for sentinel values. It propagates bad assumptions silently. The eval runner would compute accuracy against ground truth and treat "unknown" as an answer, polluting the metrics.

5. **Last-known-good output is a security and correctness disaster.** Returning previous output on failure means the system actively lies about what just happened. In a triage context, this could route the wrong ticket to the wrong team based on a previous unrelated ticket's category. It is the inverse of the validator-first design from ADR 0002.

6. **A typed two-state contract gives the eval runner clean semantics.** The eval runner can compute success rate (proportion of `TriageSuccess`), error rate by category (proportion of `TriageFailure` by `category`), and accuracy on the successes only. It can also surface failure category distributions in the benchmark report — for example, "Qwen 3.5 2B had 18% parse_failure rate after retry, while 9B had 3%" — which is one of the most interesting findings the project can produce.

## Tradeoffs

- **Upside:** Failure handling is explicit and enforced by types. Consumers get differentiated information and can react appropriately. The eval runner can compute meaningful failure-category metrics. Internal exceptions never leak to consumers.

- **Downside:** Every consumer of the pipeline has to handle both branches of `TriageResult` rather than just calling a function and getting an answer. This adds boilerplate at every call site. The discriminated union also requires consumers to import multiple types (`TriageResult`, `TriageSuccess`, `TriageFailure`) rather than just one.

- **Why we accept the downside:** The boilerplate cost is small (one `match` or `isinstance` check per call site) and pays for itself the first time it prevents a silent failure from propagating. The type imports are a one-line concern. The alternative — exceptions or `None` — moves the same complexity into try/except chains or null checks scattered throughout consumer code, which is harder to reason about and easier to get wrong.

## Consequences

- The Gradio Triage tab must implement display logic for both branches: render the structured fields on success, render an appropriate message on each failure category. The "guardrail blocked" message in particular should be informative and not alarming — it's a feature, not an error.

- The eval runner must aggregate by failure category, not just by success/failure. The benchmark output must include per-category failure rates as first-class metrics.

- The trace store records the `TriageResult` shape, including failure category and retry count, for every request. This enables post-hoc analysis of failure patterns over time and is a key input to the monitoring dashboard's drift indicators (ADR 0010, forthcoming).

- All exception-raising code inside the pipeline (model client calls, JSON parsing, schema validation) must be wrapped at the pipeline boundary. This is enforced by code review and by integration tests that deliberately trigger each failure path.

- A future addition of new failure categories (e.g., `rate_limited` if a cloud provider is integrated, `timeout` as a distinct category from `model_unreachable`) requires updating the `Literal` type and any consumers that exhaustively match on it. This is by design — the type checker will flag every place that needs to be updated.

- The contract makes no promises about *latency* on failure. A failure can take longer than a success because of the retry attempt, and a failure to a slow or unreachable model can take as long as the configured timeout. Consumers that care about responsiveness must impose their own deadlines.

## Alternatives Not Chosen

- **Option B (raise exceptions):** rejected because exception handling is opt-in at every call site, and a missing `except` becomes a runtime crash. Typed results force the consumer to acknowledge failure as part of the type contract, which is more robust under maintenance.

- **Option C (return None):** rejected because it loses the failure category information that consumers actually need. A `None` says something failed; a `TriageFailure` says *what* failed and *where*.

- **Option D (partial data, no failure indicator):** rejected because it propagates bad assumptions silently. Sentinel values like `severity = "unknown"` are easy to forget to check for and pollute downstream computation. The eval runner would treat "unknown" as a real answer and produce meaningless accuracy numbers.

- **Option E (last-known-good output):** rejected because it actively lies about the current request. In a triage context this could cause real operational harm (wrong ticket routed to wrong team). It violates the project's core principle that failures should be visible, not hidden.
