# Cost Analysis

This document captures the full cost picture for running the ticket triage pipeline on consumer hardware, and compares it against hypothetical cloud deployment using published Qwen API pricing.

The analysis has three components:
1. Local compute resource cost per model (measured)
2. Hardware acquisition cost amortized (calculated)
3. Hypothetical cloud comparison with break-even analysis (projected)

Components 1 and 3 are populated from the Phase 3 replication data (n=5 runs per model on the 35-ticket normal set under production config: `think=false`, `num_ctx=16384`, locked sampling params, prompt v1). Source artifacts: `data/phase3-1/run-{1..5}/e1-local-comparison.json`. All values are mean ± stddev across the 5 runs.

---

## 1. Local Compute Resource Cost Per Model

What each model "costs the machine" per triage request, measured during benchmark runs.

### Resource usage per model

| Metric | Qwen 3.5 2B | Qwen 3.5 4B | Qwen 3.5 9B |
|---|---|---|---|
| Model weight size on disk | ~2.7 GB | ~3.3 GB | ~6.6 GB |
| RAM footprint at runtime | Not precisely measured — use disk size as a lower bound. Ollama with Metal keeps the weights resident in unified memory during inference. | Same caveat. | Same caveat. On 24 GB unified memory, running the 9B plus Gradio + dev tools stays well under pressure; `ollama ps` is the source-of-truth for "is the model loaded." |
| Avg tokens in per request | 593.9 ± 0.2 | 593.8 ± 0.0 | 577.4 ± 0.0 |
| Avg tokens out per request | 154.1 ± 0.7 | 153.8 ± 1.1 | 165.2 ± 0.9 |
| Avg total tokens per request | 748.0 ± 0.7 | 747.6 ± 1.0 | 742.7 ± 0.9 |
| Tokens/sec (decode) | 53.5 ± 4.1 | 31.0 ± 2.7 | 22.9 ± 1.2 |
| Avg latency (ms) | 2,930 ± 225 | 5,067 ± 434 | 7,360 ± 390 |
| p95 latency (ms) | 3,851 ± 366 | 6,728 ± 791 | 8,318 ± 610 |
| GPU utilization | Engaged via Metal on Apple Silicon; exact utilization percentage not measured (out of scope for this iteration — would require Activity Monitor sampling during benchmark runs). | Engaged via Metal. | Engaged via Metal. |
| MLX acceleration engaged? | Via Ollama's Metal backend (Ollama does not use MLX directly; it uses Metal through llama.cpp). | Same. | Same. |

### Observations

**1. Token-count inversion is real and persistent across runs.** The 2B uses nearly the same total tokens per request as the 4B and 9B under production config (748 / 748 / 743) — there is no material token saving from picking a smaller model. The prompt input is bounded by the schema and examples (~577-594 tokens in) and the structured JSON output is bounded by the response size (~154-165 tokens out). Per-request token cost is fundamentally a function of the task shape, not the model size.

**2. The 2B's speed advantage is real but doesn't translate to a quality-aware win.** The 2B is ~2.5x faster than the 9B on latency (2.9 s vs 7.4 s) and ~2.3x higher on decode tokens/sec (53.5 vs 22.9). But the 2B's category accuracy (74.9%) is ~8.5pp lower than the 9B (83.4%) and its adversarial residual risk is ~5.4x worse (5.4 vs 1.0 across 5 Phase 4 replication runs). For any use case where correctness matters, the 2B's speed is not a durable advantage.

**3. Latency variance across runs is low (stddev ≤ 15% of mean).** The Phase 3 replication's stddev on mean latency is 225 ms (2B) / 434 ms (4B) / 390 ms (9B) — roughly 7-8% of the mean in each case. This matches the ≤5% accuracy stddev pattern from the replication: production config produces stable, reproducible runtime behavior. Quoted single-digit-second latencies are not point observations; they are medians of a tight distribution.

**4. p95 sits within 15-32% above mean across the three sizes.** Not a heavy-tailed distribution on this workload. For a live system, latency budgeting against p95 is safe; there are no pathological outliers pulling the tail out.

**5. 24 GB unified memory is comfortable for the 9B under production config.** No out-of-memory events across the 1,575 total Phase 3 triages (n=5 × 3 models × 3 experiments × 35 tickets). The 24 GB machine spec is appropriate for this 9B deployment path; smaller machines would either need to fall back to the 4B or tolerate CPU-spill penalty.

---

## 2. Hardware Acquisition Cost Amortized

Local inference is not free — the hardware has a purchase price that should be amortized over its expected useful life to compute a daily fixed cost.

### Target hardware

- **Machine:** MacBook Pro M4 Pro, 24GB unified memory
- **Purchase price:** $2,499 (14" M4 Pro base config with 24 GB unified memory at Apple's US retail pricing as of April 2026 — used as a round-number reference; the specific developer's purchase price may differ)
- **Expected useful life:** 3 years (reasonable assumption for a professional development machine)

### Amortized cost calculation

| Metric | Value |
|---|---|
| Purchase price | $2,499 |
| Useful life (years) | 3 |
| Useful life (days) | 1,095 |
| **Daily fixed cost** | **$2.28** |
| **Monthly fixed cost** | **$68.47** |

This daily fixed cost applies regardless of how many inferences are run. Whether the machine processes 0 tickets or 10,000 tickets in a day, the hardware cost is the same. This is the fundamental difference between local and cloud cost models: local cost is fixed, cloud cost is variable.

### What this number does and doesn't include

**Includes:** the purchase price of the hardware, amortized linearly.

**Does not include:** electricity cost (negligible for a laptop — roughly $0.05–0.10/day under moderate load), the developer's time to maintain the local stack, opportunity cost of the machine being used for inference instead of other work, or any cooling/space costs (not applicable for a laptop deployment).

---

## 3. Hypothetical Cloud Comparison

This section uses published Qwen API pricing to project what the same workload would cost on cloud infrastructure, then computes the break-even point where local becomes cheaper.

### Published Qwen pricing (as of April 2026)

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Source |
|---|---|---|---|
| Qwen 3.5 Plus | $0.26 | $1.56 | OpenRouter |
| Qwen Plus | $0.26 | $0.78 | pricepertoken.com |
| Qwen3 Max | $0.78 | $3.90 | pricepertoken.com |

For this comparison, **Qwen 3.5 Plus** is the most appropriate reference — it is the same model family (3.5) at a cloud-hosted scale, making the comparison as apples-to-apples as possible without actually running the cloud model.

### Per-request cloud cost estimate

Using actual token counts from the benchmark runs:

Using measured token counts from the Phase 3 replication for the **9B** (the default demo model per OD-4 resolution):

| Metric | Value |
|---|---|
| Avg input tokens per request | 577.4 |
| Avg output tokens per request | 165.2 |
| Input cost per request | $0.000150 |
| Output cost per request | $0.000258 |
| **Total cost per request (9B)** | **$0.000408** |

For the 4B and 2B, the per-request totals are nearly identical because input/output token counts are almost constant across model sizes (see § 1 Observation 1):

| Model | Total cost per request |
|---|---|
| Qwen 3.5 9B | $0.000408 |
| Qwen 3.5 4B | $0.000394 |
| Qwen 3.5 2B | $0.000395 |

Formula: `(input_tokens / 1,000,000 × $0.26) + (output_tokens / 1,000,000 × $1.56)`

### Projected cloud cost at daily volumes

Using 9B pricing (primary production model):

| Daily volume | Requests/month | Cloud cost/month | Local cost/month | Cheaper option |
|---|---|---|---|---|
| 100 tickets/day | 3,000 | $1.22 | $68.47 | **Cloud** (by ~56x) |
| 1,000 tickets/day | 30,000 | $12.24 | $68.47 | **Cloud** (by ~5.6x) |
| 10,000 tickets/day | 300,000 | $122.35 | $68.47 | **Local** (by ~1.8x) |

### Break-even analysis

Break-even daily volume: **~5,596 requests/day** on the 9B.

Below this threshold, cloud is cheaper because you are paying the full amortized hardware cost whether the machine is idle or saturated. Above this threshold, local is cheaper because the fixed hardware cost spreads across a larger number of inferences.

Formula: `break_even_daily_volume = daily_hardware_cost / cost_per_cloud_request = $2.28 / $0.000408 ≈ 5,596`

For reference, a 9-hour workday at break-even volume averages **~622 requests per hour** or **~1 request every 5.8 seconds** — plausible for a medium-to-large support organization but well above a single support team's typical load. The 4B break-even is nearly identical (~5,788 requests/day) because per-request tokens are nearly constant across model sizes.

**What this number means in practice:** for a small support team (50–500 tickets/day), cloud inference is economically dominant by 5–50x. Local inference's cost advantage only appears at enterprise-scale volume, and at that point the non-cost factors (privacy, latency, operational simplicity) carry more weight in the decision than the raw dollar difference.

### Cost factors not captured in this comparison

This analysis compares direct costs only. In a real production deployment, additional cost factors would influence the decision:

- **Cloud operational overhead:** API key management, rate limit handling, vendor SLA monitoring, version-update tracking, egress fees on high-volume output
- **Local operational overhead:** Ollama version management, model update labor, hardware maintenance, the 2 AM page when the inference process crashes, developer time to debug local-only issues
- **Data privacy cost:** for a support ticket system, tickets contain customer PII. Cloud inference means ticket content leaves the local infrastructure. Depending on the industry and jurisdiction, this may require additional compliance work (data processing agreements, encryption in transit, audit logging) that has its own cost. Local inference avoids this entirely.
- **Availability and reliability:** cloud providers offer SLAs; a local Mac does not. The cost of downtime depends on the business context.

These factors are acknowledged but not quantified. A full TCO analysis would require assumptions about team size, incident frequency, and compliance requirements that are outside the scope of this project.

---

## Summary

**Per-request marginal cost (local inference):** effectively $0. The machine is already running; one more triage request is indistinguishable from the cost side. The real cost is the hardware that makes it possible.

**Per-request cloud cost (Qwen 3.5 Plus):** $0.000408 on the 9B. The 4B and 2B are within 4% of the 9B number because per-request tokens are nearly constant across model sizes — token cost does not scale with parameter count.

**Amortized daily hardware cost:** $2.28/day ($68.47/month) for a $2,499 MacBook Pro M4 Pro over a 3-year useful life.

**Break-even daily volume:** ~5,596 requests per day at 9B pricing. Below that, cloud is cheaper per dollar; above that, local is cheaper per dollar.

### What this means for this project's deployment context

This project is positioned as a demo of what consumer-hardware local inference can deliver for a small-to-medium support operation. At the project's plausible operational scale — anywhere from a solo developer doing experimental triage to a small support team handling a few hundred tickets a day — **cloud inference is the economically dominant choice by 5-50x**. The strict dollar comparison does not favor local.

The local path wins on factors this analysis acknowledges but does not quantify: data privacy (tickets contain customer PII, and local inference keeps that content on the developer's machine), operational simplicity (no API key management, no vendor SLA dependency, no egress fees), and the educational value of understanding what's actually happening on your own hardware. The cost number above is the honest dollar answer; the deployment decision is multi-factor.

### How this analysis would change under different constraints

- **Higher volume (10k+ tickets/day sustained).** Local becomes the dollar winner at 10k+ tickets/day. At enterprise volume, the hardware cost amortizes across enough requests that cloud's per-request markup starts to accumulate. A dedicated inference workstation with more VRAM (e.g., Mac Studio Ultra) would shift break-even further down because the hardware handles higher throughput per dollar.

- **Stricter privacy requirements.** PHI/PCI/regulated-data contexts bias strongly toward local regardless of volume. The unquantified "cloud operational overhead" line (data processing agreements, audit logging, compliance review) can easily dwarf the dollar savings cloud provides at low volume. Healthcare, legal, and financial services workloads often land here.

- **Enterprise hardware budget.** A $10,000+ inference workstation (Mac Studio, NVIDIA workstation, dedicated inference server) changes the amortization math. Daily hardware cost rises proportionally but per-request throughput rises faster (larger VRAM lets bigger models stay resident; better sustained decode rates). Break-even volume drops substantially. This is the model behind on-prem enterprise AI deployments.

- **Token-heavy workloads.** This project's workload is token-light (~750 tokens/request). Workloads with longer contexts (multi-turn conversation, large document summarization, retrieval-augmented generation with many retrieved chunks) would multiply the cloud per-request cost and lower the break-even volume. Local inference is more cost-advantaged for token-heavy work than for this triage workload.

- **Cloud model is more expensive than Qwen 3.5 Plus.** This analysis uses Qwen 3.5 Plus as the reference ($0.26 input / $1.56 output per 1M tokens). A frontier model like GPT-5 or Claude Opus 4.6 would be 5-20x more expensive per token and break-even drops to hundreds of requests per day. For the *same* model family (Qwen 3.5), the reference is appropriate; for cross-family cost comparisons, the numbers above must be re-computed with the target model's pricing.
