# Presentation Notes

Speaker notes for the 6-slide deck. Target talk length: **~6 minutes** (~1 minute per slide), leaving time for the live demo (~8–10 minutes) and Q&A.

The numbers cited here are from the Phase 3 / Phase 4 replication (n=5) and the E5 reasoning-mode experiment, all under production configuration (`think=false`, `num_ctx=16384`, locked sampling). These are baselines, not point observations.

---

## Slide 1: What and why

**Content:**

- Title: `ticket-triage-llm` — consumer-hardware LLM triage with prompt-injection-aware guardrails
- One-line thesis: *How much of the value in a production LLM system comes from the model itself vs. the surrounding engineering controls, and how well do layered mitigations defend against prompt injection?*
- Constraint: consumer hardware (MacBook Pro M4 Pro, 24 GB unified memory)

**Talking points:**

> *"This is a final project built around a single engineering question, not a chatbot. The question is: when you deploy an LLM in a real system, how much does the model itself actually matter vs. how much comes from validation, retry logic, guardrails, and prompt design? I spent the project answering that with measurements, not opinions."*

> *"The hardware constraint is deliberate. A 24-gigabyte MacBook is what most production systems will actually ship on — or less. The frontier labs get the headlines, but the deployments that run inside companies are on hardware like this."*

**What to cut if time is short:** the hardware constraint framing — leave only the thesis and title.

---

## Slide 2: The system in one picture

**Content:**

- Pipeline diagram (input → guardrail → prompt → provider → LLM → parse → schema → semantic checks → trace)
- Labels: "validator-first," "bounded retry (exactly 1)," "typed failure envelope"
- Provider abstraction callout: "`LlmProvider` Protocol — 3 local models + cloud-capable via Ollama passthrough"

**Talking points:**

> *"Every request flows through a pipeline that treats model output as untrusted until it's validated. Parse the JSON, validate the schema, run semantic checks. On any failure, one retry with a repair prompt that includes the failed output and the specific error. If the retry also fails, the pipeline returns a typed failure — not malformed data, not an exception, just a tagged envelope the caller pattern-matches on."*

> *"The provider layer is a Python Protocol, not an inheritance hierarchy. Three local Ollama models plug in as instances of one class; Ollama's own cloud passthrough adds cloud models via config, no new provider class needed. The stub for a direct-integration cloud path exists but stays a stub unless the project needs a non-Ollama cloud API — which it doesn't."*

**What to cut if time is short:** the repair-prompt mechanism detail.

---

## Slide 3: What I measured — Phase 3 headline numbers

**Content:**

Table (one row per model, numbers at n=5 replications under production config):

| | 2B | 4B | 9B |
|---|---|---|---|
| Category accuracy | 74.9% | 80.6% | **83.4%** |
| JSON validity | 100% | 100% | 100% |
| First-pass validity | ~100% | ~100% | ~100% |
| Mean latency | 2.9 s | 5.1 s | 7.4 s |

**Talking points:**

> *"All three models produce 100% valid JSON under production config. That wasn't true in my first measurement — it took a replication to discover that the original 4096-token context window and reasoning mode were the culprits, not the model size. Once I fixed the configuration and measured five independent runs, reliability saturated."*

> *"With reliability equalized, classification accuracy becomes the differentiator. The 9B wins by about 3 percentage points over the 4B. The size-vs-quality curve is monotonic under this setup — bigger is better by a small margin, which is not what my original single-run measurement said."*

> *"The original plan had a Phase 6 prompt-v1-vs-v2 comparison to measure how much prompting contributes. When JSON validity saturated, that comparison collapsed to a narrow headroom question, so I scoped it out and spent the time on Phase 7 deliverables. That's a scope decision documented in the decision log, not a slipped deliverable."*

**What to cut if time is short:** the Phase 6 scope-out paragraph.

---

## Slide 4: What I measured — adversarial findings

**Content:**

- Per-model adversarial compliance rates from Phase 4 replication (n=5, 14 adversarial tickets):
  - 2B: 5.4 ± 0.49 compromised out of 14 (~39%)
  - 4B: 1.2 ± 0.40
  - 9B: **1.0 ± 0.0** (reproducible at stddev = 0)
- Callout: "The one 9B vulnerability is **a-009** — indirect injection via quoted JSON debug payload. Reproducible 5/5 runs. Documented as a known limitation."
- Counter-narrative callout: "Reasoning mode does **not** fix this (E5 experiment)."

**Talking points:**

> *"The guardrail is heuristic pattern matching — not an LLM classifier — by design. I wanted to measure the baseline before upgrading, because upgrading without the baseline obscures what each layer contributes."*

> *"The baseline catches direct injection cleanly — zero compliance on the 4B and 9B across five runs. It fails on indirect injection, which is the class where adversarial content is embedded in quoted text that looks like legitimate system context. That's where a-009 lives."*

> *"I ran a follow-up experiment asking: does enabling reasoning mode on the 9B close a-009? And it does — but it introduces a new reproducible compliance on a different ticket, plus quadruples the 'needs manual review' count, plus makes per-triage latency 17x worse. Reasoning mode isn't a fix; it redistributes the failure surface. That's a finding I'd have missed if I hadn't written the decision criteria before running the experiment."*

**What to cut if time is short:** either the heuristic-baseline framing OR the E5 finding, not both.

---

## Slide 5: Cost and deployability

**Content:**

- Two bars, side-by-side, at 100 / 1,000 / 10,000 tickets/day:
  - Local amortized: $68/month fixed
  - Cloud (Qwen 3.5 Plus pricing): $1.22 / $12 / $122 per month
- Break-even: **~5,600 tickets/day**
- Deployability: native path (`uv run`), Docker path (GHCR multi-platform image)

**Talking points:**

> *"The honest cost answer: cloud wins at low and medium volume by 5 to 50x. Local inference only becomes cheaper than cloud at about 5,600 tickets a day — which is plausible for a large support organization but not for a small team."*

> *"Where local wins isn't dollars at this scale — it's privacy, latency, and operational simplicity. The tickets contain customer PII; local inference keeps them on the machine. There's no API key, no vendor SLA, no egress fee."*

> *"The Docker image is on GHCR, multi-platform. The system deploys on macOS today with macOS being the tested target. Cross-platform Windows and Linux validation is flagged as pending — I chose to ship a tested one-platform build with documented known-unknowns rather than a three-platform claim with no test evidence."*

**What to cut if time is short:** the deployability sentence.

---

## Slide 6: What this answered, what it didn't, what I'd change

**Content:**

Three columns:

| Answered | Didn't answer | Would change |
|---|---|---|
| Model size affects accuracy, not JSON validity under production config | How much prompt v2 would add | Expand adversarial set beyond 14 tickets |
| Engineering controls matter differently when reliability saturates | Cross-platform Docker behavior | Add an LLM-based classifier and measure delta |
| Reasoning mode is not an adversarial-robustness fix | How the system behaves on cloud-hosted Qwen at scale | Run E4 with a real v2 when accuracy becomes a bottleneck |
| Local inference has a specific dollar break-even | How the findings generalize beyond Qwen 3.5 | Run the system on volume traffic and validate the latency distribution claims |

**Talking points:**

> *"What I can defend with evidence: the three left-column claims are backed by n=5 replication data with measured stddev. What I cannot defend: the middle column. These are honest limitations, not gaps I'm hoping nobody notices."*

> *"The 'would change' column is the learning output. Shipping a known-limited system with documented limitations is more useful than shipping an unmeasured system that claims to be unlimited. Every item in that column is a future-improvements entry with a concrete effort estimate."*

> *"Happy to go deeper on any of this in Q&A, or jump to the live demo now."*

**What to cut if time is short:** the middle-column limitations — collapse to a single "I'm also happy to discuss the limitations in Q&A" line.

---

## Backup slides (not in the 6, use if Q&A goes there)

**If asked about prompt-injection defense specifics:**
- Three-layer model (pre-LLM guardrail, prompt structural separation, post-LLM validation) documented in `docs/threat-model.md`
- ADR 0008 scopes the guardrail as heuristic baseline intentionally; the finding that it fails on indirect injection is the measured deliverable

**If asked about validation-first pipeline details:**
- ADR 0002 captures the design: untrusted-until-validated, exactly-one retry with repair prompt, typed failure envelope
- Retry rate dropped from 43–51% under original config to 0–3% under production config; the retry path is now insurance, not an active correction loop

**If asked about the provider abstraction:**
- ADR 0004 — Python Protocol, not ABC, not callable
- The eval runner iterates `list[LlmProvider]` and runs the same suite against each provider — this is what makes the size comparison experiment composable

**If asked "why Qwen 3.5 specifically":**
- ADR 0001 scopes the project to Qwen 3.5 for model-family consistency across local and (hypothetical) cloud
- Same family means the comparison isn't confounded by architectural differences; the differences measured are size-driven, not family-driven
