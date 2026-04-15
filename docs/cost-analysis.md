# Cost Analysis

This document captures the full cost picture for running the ticket triage pipeline on consumer hardware, and compares it against hypothetical cloud deployment using published Qwen API pricing.

The analysis has three components:
1. Local compute resource cost per model (measured)
2. Hardware acquisition cost amortized (calculated)
3. Hypothetical cloud comparison with break-even analysis (projected)

Components 1 and 3 depend on real token counts and latency data from the Phase 3 benchmark runs. Placeholders are marked with **TBD** and will be filled in after Phase 3.

---

## 1. Local Compute Resource Cost Per Model

What each model "costs the machine" per triage request, measured during benchmark runs.

### Resource usage per model

| Metric | Qwen 3.5 2B | Qwen 3.5 4B | Qwen 3.5 9B |
|---|---|---|---|
| Model weight size on disk | ~2.7 GB | ~3.3 GB | ~6.6 GB |
| RAM footprint at runtime | TBD | TBD | TBD |
| Avg tokens in per request | TBD | TBD | TBD |
| Avg tokens out per request | TBD | TBD | TBD |
| Avg total tokens per request | TBD | TBD | TBD |
| Tokens/sec (decode) | TBD | TBD | TBD |
| Avg latency (ms) | TBD | TBD | TBD |
| p95 latency (ms) | TBD | TBD | TBD |
| GPU utilization (if measurable) | TBD | TBD | TBD |
| MLX acceleration engaged? | TBD | TBD | TBD |

### Observations

> TBD — to be written after Phase 3 benchmark runs. Expected observations:
> - How RAM footprint scales with model size
> - Whether any model causes memory pressure on the 24GB target hardware under realistic conditions (Gradio app + Ollama + dev environment running concurrently)
> - Whether the 2B's speed advantage is meaningful enough to justify its expected quality tradeoff
> - Whether MLX acceleration is engaged and what effect it has on latency

---

## 2. Hardware Acquisition Cost Amortized

Local inference is not free — the hardware has a purchase price that should be amortized over its expected useful life to compute a daily fixed cost.

### Target hardware

- **Machine:** MacBook Pro M4 Pro, 24GB unified memory
- **Purchase price:** TBD (insert actual or approximate price)
- **Expected useful life:** 3 years (reasonable assumption for a professional development machine)

### Amortized cost calculation

| Metric | Value |
|---|---|
| Purchase price | $TBD |
| Useful life (years) | 3 |
| Useful life (days) | 1,095 |
| **Daily fixed cost** | **$TBD** |
| **Monthly fixed cost** | **$TBD** |

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

| Metric | Value |
|---|---|
| Avg input tokens per request | TBD |
| Avg output tokens per request | TBD |
| Input cost per request | TBD |
| Output cost per request | TBD |
| **Total cost per request** | **$TBD** |

Formula: `(input_tokens / 1,000,000 × $0.26) + (output_tokens / 1,000,000 × $1.56)`

### Projected cloud cost at daily volumes

| Daily volume | Requests/month | Cloud cost/month | Local cost/month | Cheaper option |
|---|---|---|---|---|
| 100 tickets/day | 3,000 | $TBD | $TBD | TBD |
| 1,000 tickets/day | 30,000 | $TBD | $TBD | TBD |
| 10,000 tickets/day | 300,000 | $TBD | $TBD | TBD |

### Break-even analysis

> TBD — to be calculated after Phase 3 benchmark runs.
>
> The break-even point is the daily ticket volume at which the amortized local hardware cost equals the cloud per-request cost. Below this volume, cloud is cheaper (you're paying for hardware you're not fully utilizing). Above this volume, local is cheaper (the fixed hardware cost is spread across more inferences).
>
> Expected formula: `break_even_daily_volume = daily_hardware_cost / cost_per_cloud_request`

### Cost factors not captured in this comparison

This analysis compares direct costs only. In a real production deployment, additional cost factors would influence the decision:

- **Cloud operational overhead:** API key management, rate limit handling, vendor SLA monitoring, version-update tracking, egress fees on high-volume output
- **Local operational overhead:** Ollama version management, model update labor, hardware maintenance, the 2 AM page when the inference process crashes, developer time to debug local-only issues
- **Data privacy cost:** for a support ticket system, tickets contain customer PII. Cloud inference means ticket content leaves the local infrastructure. Depending on the industry and jurisdiction, this may require additional compliance work (data processing agreements, encryption in transit, audit logging) that has its own cost. Local inference avoids this entirely.
- **Availability and reliability:** cloud providers offer SLAs; a local Mac does not. The cost of downtime depends on the business context.

These factors are acknowledged but not quantified. A full TCO analysis would require assumptions about team size, incident frequency, and compliance requirements that are outside the scope of this project.

---

## Summary

> TBD — to be written after all sections are populated with real data. Expected structure:
>
> 1. State the per-request cost for each local model ($0, but with the resource costs above for context)
> 2. State the amortized daily hardware cost
> 3. State the per-request cloud cost from the projection
> 4. State the break-even volume
> 5. One paragraph on what this means for the project's deployment context: a small-to-medium support operation on consumer hardware
> 6. One paragraph on how this analysis would change under different constraints (higher volume, stricter privacy requirements, enterprise hardware budget)
