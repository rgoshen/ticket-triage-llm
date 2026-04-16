# 0009. Monitoring distinct from benchmarking

## Status

Accepted

## Context

The project produces two fundamentally different kinds of operational data:

1. **Benchmark data** — produced by the eval runner against a labeled dataset. It answers: "how does this model/prompt/configuration perform on a known test set?" It's a snapshot: you run the benchmark, get the numbers, and the numbers don't change until you re-run. Accuracy, JSON validity rate, routing correctness — these are benchmark metrics.

2. **Live operational data** — produced by the Triage tab during normal use (and during demos). It answers: "what's happening right now?" It's a stream: every request adds a new trace, and the picture changes over time. Latency trends, error rate trends, category distribution shifts — these are operational metrics.

Most student LLM projects collapse these into one dashboard labeled "metrics" and don't distinguish between them. This is a problem because they answer different questions, have different data sources, and need different visualization patterns. A benchmark table is a static comparison across configurations. A latency trend is a time-series chart that reveals operational changes. Displaying them in the same undifferentiated view obscures both.

The question is whether the project should treat them as distinct concepts with separate UI sections and separate service-layer queries, or merge them into one dashboard.

## Options Considered

### Option A: Distinct sections in the Metrics tab, with live alerting

The Metrics tab is split into two clearly labeled sections: "Benchmark Results" (static, from eval runs) and "Live Metrics" (rolling, from trace data). Live Metrics includes time-series views and alerting thresholds. Benchmarks show comparison tables and per-experiment results.

### Option B: One merged dashboard

All metrics — benchmark and live — appear in a single view. Charts and tables are mixed. The user infers which data is from benchmarks and which is from live traffic based on context.

### Option C: Separate pages for benchmarks and monitoring

Instead of two sections in one tab, create two separate tabs: a "Benchmarks" tab and a "Monitoring" tab.

### Option D: External monitoring tool (Prometheus + Grafana)

Export metrics to Prometheus, visualize in Grafana. The app handles benchmarking; Grafana handles monitoring.

## Decision

We chose **Option A: distinct sections in the Metrics tab, with live alerting**.

The Metrics tab contains two visually separated sections:

### Benchmark Results section

Populated from traces tagged with a `run_id` (produced by the eval runner). Static until a new eval run is executed.

Contents:
- KPI cards for the latest benchmark run (best model, accuracy, JSON validity rate, p95 latency, retry rate)
- Per-experiment comparison tables (Experiments 1–4)
- Prompt injection sub-evaluation results (block rate, bypass rate, residual risk by attack category)

### Live Metrics section

Populated from all traces (with or without `run_id`) over rolling time windows. Updates every time the tab is viewed or refreshed.

Contents:
- **Latency trends** — p50 and p95 latency over configurable windows (last hour, last day, last week), by provider and prompt version
- **Error rate trends** — validation failure rate and retry rate over the same windows
- **Category distribution** — proportion of triage output categories over time, as a basic drift indicator
- **Alerting status** — current state of each configured threshold, showing whether it's within bounds or breached

### Alerting thresholds

Configured with sensible defaults, tunable after Phase 3 benchmarks provide baseline data:

| Threshold | Default | Rationale |
|---|---|---|
| p95 latency | > 5 seconds | Triage is async-tolerant but >5s indicates degradation |
| Retry rate | > 20% | Above 20% suggests model instability or prompt regression |
| Single category dominance | > 70% of recent traffic | Sustained skew suggests input drift or model behavior change |

When a threshold is crossed, a structured warning is written to the application log:

```
WARN [monitoring] threshold_breached: p95_latency=6200ms > limit=5000ms window=1h provider=qwen3.5:9b
```

Alerts are log-based only. There is no integration with external alerting systems (PagerDuty, Opsgenie, etc.).

## Rationale

1. **Benchmarking and monitoring answer different questions and conflating them loses signal.** "Accuracy was 87% on the labeled set" is a benchmark finding — it tells you about model quality on known inputs. "p95 latency has increased from 3.2s to 5.8s over the last hour" is a monitoring observation — it tells you something has changed in the operational environment. Displaying both in an undifferentiated view makes it hard for the viewer to know which claims are from controlled experiments and which are from live observation. Separating them makes each claim legible on its own terms.

2. **The distinction demonstrates production thinking, which the rubric rewards.** The rubric's "Inference Pipeline" criterion values a pipeline that is "well-documented and optimized for performance." Monitoring — knowing whether the pipeline's performance is degrading in production — is part of what "optimized for performance" means in a real system. Most student projects treat performance as a static number from a benchmark; this project treats it as a dynamic quantity that can change and needs to be watched.

3. **Time-series views over rolling windows reveal trends that point-in-time metrics miss.** A single "average latency" number tells you where you are. A latency chart over the last hour tells you whether you're getting worse. The trend is often more actionable than the current value — it tells you whether to investigate or wait.

4. **Category distribution as a drift indicator is cheap and high-signal.** If the model suddenly starts routing 80% of tickets to "security" when the historical baseline is 15%, something has changed — either the input population has shifted (a real-world event) or the model behavior has changed (a regression, a prompt change, or a successful injection campaign). Tracking category distribution over time catches both of these. It requires no additional data collection beyond what the trace store already captures.

5. **Log-based alerting is honest about the system's scale.** This is a single-instance demo system on consumer hardware, not a production service mesh. Integrating Prometheus, Grafana, PagerDuty, or any real alerting infrastructure would be overengineering for the project's scale and would add dependencies that complicate deployment (ADR 0007). Structured log warnings are sufficient to demonstrate the *concept* of alerting without the infrastructure overhead. The limitation is documented explicitly.

6. **Two sections in one tab is simpler than two separate tabs.** Option C (separate tabs) was considered but rejected because it fragments the metrics story across two views. The instructor demoing the Metrics tab should see the full picture — benchmark results *and* live operational health — in one place. Scrolling is simpler than tab-switching when the two kinds of data are naturally consumed together ("how did this model perform on the benchmark?" immediately followed by "and how is it performing live?").

## Tradeoffs

- **Upside:** Clean conceptual separation between benchmarking and monitoring. Time-series views reveal trends. Category distribution provides a zero-cost drift indicator. Alerting demonstrates production awareness without external infrastructure. The Metrics tab tells a complete story in one view.

- **Downside:** The Live Metrics section requires time-windowed queries against the trace store, which adds complexity to the metrics service. The alerting thresholds need to be tuned to actual baseline performance — before Phase 3 benchmarks, the defaults are educated guesses. Log-based alerting is not actionable in the way a PagerDuty notification is — someone has to be watching the logs.

- **Why we accept the downside:** The time-windowed queries are straightforward SQL against the trace store (ADR 0005). The threshold tuning is expected — the defaults are starting points, documented as such. The log-based alerting limitation is acknowledged in the project's documentation as appropriate for the system's scale, with external alerting listed as a future improvement for production deployment.

## Consequences

- The Metrics tab has two visually distinct sections with clear labels. A viewer can immediately tell whether they're looking at benchmark results or live metrics.

- The metrics service exposes two distinct query patterns: `get_benchmark_results(run_id)` for the benchmark section and `get_live_metrics(window, filters)` for the live section. Both query the same trace store (ADR 0005) but with different grouping and windowing logic.

- Alerting thresholds are defined in the app configuration (environment variables or config file), not hardcoded. This allows tuning after Phase 3 baseline data is available.

- The alert log format is structured (key=value pairs) so it can be parsed programmatically if needed. This is future-proofing for external log aggregation, not a current requirement.

- The monitoring section depends on having enough trace data to be meaningful. On a fresh install with no traces, the Live Metrics section shows empty charts. This is expected and not an error — the section populates as requests are made.

- The separation creates a natural demo flow: "First, here are the benchmark results from my evaluation. Now, here's how the system is performing live. And here's the alerting configuration that would catch operational problems." This three-part narrative is more compelling than a single undifferentiated metrics dump.

## Alternatives Not Chosen

- **Option B (one merged dashboard):** rejected because it conflates two different kinds of claims (controlled experiment results vs live observations) in a way that makes both harder to interpret. The viewer has to mentally separate "which of these numbers are from a benchmark and which are from live traffic" — cognitive overhead that the UI should handle, not the viewer.

- **Option C (separate tabs):** rejected because it fragments the metrics story. The benchmark results and live metrics are naturally consumed together and separating them across tabs adds navigation overhead without adding clarity. Two sections in one tab gives the same separation without the fragmentation.

- **Option D (Prometheus + Grafana):** rejected because it adds external infrastructure dependencies that complicate the deployment (ADR 0007), require the evaluator to install and configure additional tools, and are disproportionate to the project's single-instance scale. The concept of monitoring is demonstrated through the in-app Live Metrics section; the infrastructure of monitoring is acknowledged as a production concern beyond the project's scope.
