# 0008. Heuristic-only guardrail as baseline

## Status

Accepted

## Context

The triage pipeline accepts user-submitted support tickets as input. By definition, this input is untrusted — the pipeline has no control over what a user types into the ticket body. The project's central engineering investigation is prompt injection defense, and the guardrail layer is where the pre-LLM input screening lives.

The guardrail sits between input validation (checking that the ticket body is non-empty and within length bounds) and the prompt builder (which constructs the system prompt + user content). Its job is to examine the ticket body *before* it reaches the model and flag or block inputs that appear to contain injection attempts, PII, or other content that the pipeline should not process blindly.

The design question is how sophisticated this guardrail should be. There is a spectrum from simple pattern matching to a dedicated classification model, and the choice affects build time, accuracy, false positive rate, and — critically — the quality of the findings the project can report.

## Options Considered

### Option A: Heuristic-only (pattern matching)

A single Python function that checks the ticket body against a set of rules: known injection phrases (substring and regex), suspicious structural markers (Base64 blocks, invisible Unicode, unusual character ratios), length extremes, and basic PII patterns (credit card regex, SSN regex). Returns `pass`, `warn`, or `block`.

### Option B: Heuristic + LLM-based second-pass classifier

Option A as the first pass, plus a second pass that sends flagged or all inputs to a small LLM with a prompt like "does this input contain an attempt to override system instructions?" The LLM acts as a semantic classifier that can catch attacks the regex misses.

### Option C: Dedicated injection-detection model

Fine-tune or use a pre-trained classifier specifically designed to detect prompt injection (e.g., a small BERT-style model trained on injection datasets). This replaces or supplements the heuristic layer.

### Option D: No guardrail, rely on output validation only

Skip input screening entirely. Trust the validator-first pipeline (ADR 0002) to catch corrupted output downstream.

## Decision

We chose **Option A: heuristic-only** as the baseline implementation, with **Option B as an optional stretch** if time permits after Phase 6.

The guardrail function takes a ticket body and returns a `GuardrailResult`:

```python
from typing import Literal
from pydantic import BaseModel

class GuardrailResult(BaseModel):
    decision: Literal["pass", "warn", "block"]
    reason: str | None = None  # human-readable explanation when not "pass"
    matched_rules: list[str] = []  # which rules triggered, for trace logging
```

The initial rule set covers four categories:

**1. Known injection phrases (block or warn)**
- Substring matches for common injection patterns: "ignore previous instructions", "ignore all prior", "you are now", "disregard your system prompt", "do not follow", "override your instructions", "forget your rules", and similar variants
- These are checked case-insensitively and with whitespace normalization

**2. Suspicious structural markers (warn)**
- Base64-encoded blocks longer than a configurable threshold (suggests encoded payload)
- Invisible Unicode characters (zero-width spaces, right-to-left override, etc.)
- Unusual character-to-whitespace ratio (a wall of text with no spaces may be an obfuscation attempt)

**3. Length extremes (block or warn)**
- Empty or near-empty input (block — nothing to triage)
- Input exceeding a configurable maximum length (warn — legitimate long tickets exist, but extreme length may indicate payload stuffing)

**4. PII patterns (warn)**
- Credit card number regex (Luhn-plausible 16-digit sequences)
- SSN regex (XXX-XX-XXXX pattern)
- These trigger a warning rather than a block because legitimate tickets may contain PII that the user is reporting as a problem ("someone charged my card ending in 4242")

The `matched_rules` field in the result enables the trace record to capture *which* rules triggered, which is essential for the adversarial evaluation: it lets the project report not just "the guardrail blocked 7 of 12 adversarial inputs" but "the injection-phrase rule caught 5, the structural-marker rule caught 2, and 5 bypassed all rules."

## Rationale

1. **A heuristic guardrail produces the most informative findings for the project's central investigation.** The point is not to build a perfect guardrail — it's to build a *measurable* one, run the adversarial set against it, and report what it caught and what it missed. A simple guardrail with known limitations produces a clearer finding than a sophisticated one whose failure modes are harder to characterize.

2. **The heuristic approach will almost certainly fail on obfuscated attacks, and that failure is itself the finding.** If the guardrail catches direct injection phrases but misses Base64-encoded versions of the same phrases, the writeup can say: "the heuristic approach caught X% of direct injection but only Y% of obfuscated attacks, demonstrating the limits of pattern-matching as a defense against prompt injection." This is an honest, evidence-based conclusion that reflects where the field actually sits. It's more valuable than claiming to have solved the problem.

3. **The implementation cost is minimal.** The heuristic guardrail is roughly 50–80 lines of Python plus tests. A coding agent writes it in under an hour. The valuable work is the *evaluation* of the guardrail against the adversarial set, not the guardrail itself — and that evaluation work is the same regardless of which option is chosen.

4. **Option B (LLM classifier) is a meaningful addition but introduces scope risk.** Using a second LLM call to classify inputs adds latency to every request, requires a separate prompt template, and introduces the question of which model to use for classification (the same triage model? a different, smaller one?). These are real design decisions that take time to get right. As an optional stretch after the core project is complete, Option B is interesting. As a baseline commitment, it's risky.

5. **Option C (dedicated detection model) is out of scope for the build window.** Fine-tuning a classifier requires labeled injection training data, a training pipeline, and evaluation of the classifier itself — effectively a second ML project inside the first one. Using a pre-trained injection detector is more feasible but still introduces a new dependency and a new failure mode to understand and document. This is future work.

6. **Option D (no guardrail) would weaken the project's central argument.** The thesis is that engineering controls matter. Omitting the guardrail layer removes one of the three defensive layers (guardrail → model → output validation) and makes the prompt injection investigation less interesting. Even a simple guardrail adds a measurable layer that the evaluation can probe.

## Tradeoffs

- **Upside:** Fast to build, easy to understand, easy to test, produces clear and defensible findings about the limits of pattern-matching defenses. The evaluation metrics (block rate, bypass rate, per-rule hit rate) are straightforward to compute and present.

- **Downside:** The guardrail is trivially bypassable by anyone who knows what rules are being checked. Obfuscated attacks (Base64, language switching, Unicode tricks) will likely bypass it. Indirect injection via quoted content may bypass it if the injection phrases are embedded in a context that looks like legitimate quoted material. The guardrail provides a false sense of security if taken at face value.

- **Why we accept the downside:** The project does not claim the guardrail stops prompt injection. It claims the guardrail is one layer of a defense-in-depth approach, measures its effectiveness honestly, and documents the residual risk. The downside — that the guardrail is bypassable — is the *expected finding*, not an unexpected failure. Acknowledging it is the intellectually honest position and is itself a contribution to the project's investigation.

## Consequences

- The `guardrail.py` service is called before the prompt builder on every triage request. Its result (`pass`, `warn`, or `block`) is recorded in the trace record.

- On `block`, the pipeline short-circuits and returns a `TriageFailure` with `category = "guardrail_blocked"` (per ADR 0003). The model is never called. This is a correct defensive behavior, not an error.

- On `warn`, the pipeline continues but the warning is logged in the trace. This allows the evaluation to track "inputs that triggered a warning but were processed anyway" as a category — useful for measuring the false positive rate of the guardrail.

- On `pass`, the pipeline continues normally.

- The adversarial evaluation (Phase 4) runs every adversarial ticket through the guardrail and reports per-rule and per-category effectiveness. The output includes: block rate, warn rate, pass rate, bypass rate (adversarial inputs that passed without any flag), and per-rule hit distribution.

- The guardrail rules are *not* hidden from the evaluation. The adversarial set is designed with full knowledge of what the guardrail checks for, because in a real deployment, an attacker can also discover the rules through probing. Testing against an attacker who knows the rules is a more honest security evaluation than testing against a naive attacker.

- **Optional stretch (post-Phase 6):** if time permits, Option B (LLM-based second-pass classifier) can be added as an additional layer. The evaluation framework already exists — adding a second layer means re-running the adversarial set and comparing the results with and without the LLM classifier. This produces a second finding: "adding an LLM classifier improved detection of obfuscated attacks from Y% to Z% at a cost of N ms additional latency per request."

## Alternatives Not Chosen

- **Option B (heuristic + LLM classifier):** not rejected outright — deferred as an optional stretch. The heuristic baseline comes first because it's cheaper and produces a clear finding on its own. The LLM classifier is layered on top only if the core project is otherwise complete.

- **Option C (dedicated detection model):** rejected because it requires training data, a training pipeline, and evaluation of the classifier itself, which is effectively a second ML project. Out of scope for this build.

- **Option D (no guardrail):** rejected because it removes a measurable defensive layer and weakens the project's central investigation. Even a simple guardrail adds signal that the evaluation can probe.
