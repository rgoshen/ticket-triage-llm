# 0011. Default model selection: Qwen 3.5 4B

## Status

Accepted

## Context

The triage pipeline supports multiple models via the `LlmProvider` Protocol and the `ProviderRegistry` (ADR 0004). Three local models are available: Qwen 3.5 2B, 4B, and 9B. The Triage tab's model dropdown and the API endpoint both need a default — the model that is loaded when the user first opens the app or sends a request without specifying a model.

The choice of default was left open as OD-4 in the decision log, explicitly gated on Phase 3 evaluation results. Phase 3 is now complete. All four experiments have run on the full 35-ticket normal set with prompt v1 and locked sampling parameters (temperature=0.2, top_p=0.9, top_k=40).

The decision is not "which model is best in the abstract" but "which model should be the default for this system, on this hardware, for this task, given the evidence we have."

## Options Considered

### Option A: Qwen 3.5 9B (largest model)

The conventional choice — more parameters should mean better quality. The 9B has the deepest reasoning capacity and highest per-token confidence scores from Phase 0.

### Option B: Qwen 3.5 4B (mid-size model)

The best empirical performer from Phase 3. Wins on every measured metric against both the 2B and 9B.

### Option C: Qwen 3.5 2B (smallest model)

The fastest and lightest option. Would maximize responsiveness in the demo.

## Decision

We chose **Option B: Qwen 3.5 4B** as the default model.

The default is configured via the `OLLAMA_MODELS` environment variable. The first model in the comma-separated list is the default. The recommended configuration is:

```
OLLAMA_MODELS=qwen3.5:4b,qwen3.5:9b,qwen3.5:2b
```

This places the 4B first (default), followed by the 9B (available for comparison), followed by the 2B (available for the size-comparison story). All three remain in the dropdown — the choice of default does not remove models from the registry.

## Rationale

The 4B wins on every metric that matters for the default model decision:

| Metric | 2B | 4B | 9B |
| --- | --- | --- | --- |
| Successful tickets | 1/35 (2.9%) | 29/35 (82.9%) | 26/35 (74.3%) |
| Category accuracy | 2.9% | 57.1% | 54.3% |
| Severity accuracy | 0.0% | 51.4% | 48.6% |
| Escalation accuracy | 2.9% | 74.3% | 65.7% |
| JSON validity rate | 2.9% | 82.9% | 74.3% |
| Retry recovery rate | 0.0% | 57.1% | 50.0% |
| Avg latency | 69,077ms | 73,886ms | 107,012ms |
| Tokens/request | 4,951 | 3,098 | 3,378 |

**Why the 4B beats the 9B despite fewer parameters:**

1. **Structured output reliability.** The 9B's longer reasoning chains have more opportunities to produce structurally invalid JSON. It generates more tokens per request but converts fewer of them into valid output. The 4B's shorter reasoning is more likely to stay within the output format.

2. **Retry effectiveness.** The 4B recovers 57% of failures on the repair prompt vs 50% for the 9B. A model that fails less often AND recovers more reliably is strictly better for a validator-first pipeline.

3. **Latency.** 74s vs 107s average. In a live demo, 30+ seconds of additional wait time per request is noticeable. The 4B is fast enough to demo comfortably; the 9B tests patience.

4. **Token efficiency.** 3,098 total tokens vs 3,378. The 4B is 8% cheaper per request in token terms. At scale, this compounds.

**Why the 2B is excluded as a default candidate:** 1/35 success rate. The 2B cannot produce structured JSON reliably enough to be a usable default. It stays in the dropdown because showing its failure mode is itself a project finding.

**Why this supports the project thesis:** The 4B-with-validation outperforms the 9B-without-validation (E2/E3 cross-comparison: 29/35 vs 17/35). The default model choice is itself evidence for the thesis that engineering controls compensate for model size.

## Tradeoffs

- **Upside:** Best overall quality, best reliability, good latency, lowest token cost. The default gives users the best experience out of the box.

- **Downside:** The 4B is not the most capable model available. On tasks where raw reasoning depth matters more than structured-output reliability, the 9B might be preferable. However, the triage task requires structured JSON, and on that criterion the 4B is empirically superior.

- **Confound acknowledged:** The 2B uses Q8_0 quantization while the 4B and 9B use Q4_K_M. The 2B's failure cannot be attributed solely to parameter count — the different quantization is a variable. This confound does not affect the 4B vs 9B comparison (both use Q4_K_M).

## Consequences

- The `ProviderRegistry.default` property returns the first provider in the list. The recommended `OLLAMA_MODELS` value places `qwen3.5:4b` first.

- The Triage tab's dropdown pre-selects the default provider. Users can switch to any other registered model.

- The API endpoint uses the default provider when no `model` field is specified in the request body.

- The demo script (Phase 7) will use the 4B for the happy-path walkthrough, then switch to the 9B or 2B to show the size comparison.

- OD-4 in the decision log is now resolved. No further model selection decisions are needed unless Phase 6 (prompt v2) or Phase 4 (adversarial eval) produces findings that change the ranking.

## Alternatives Not Chosen

- **Option A (9B as default):** Rejected because the 9B is slower, less reliable, and less accurate than the 4B on the structured-output triage task. The naive assumption that "bigger is better" is contradicted by the Phase 3 evidence. The 9B remains available for comparison but is not the default.

- **Option C (2B as default):** Rejected because the 2B is not viable for the task (2.9% success rate). It remains in the dropdown for demonstration purposes only.
