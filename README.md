# ticket-triage-llm

A production-style support ticket triage system built on local LLMs, with a focus on prompt injection defense and structured-output reliability under realistic adversarial conditions.

> **Status:** Phase 5 complete — four-tab Gradio dashboard (Triage, Metrics, Traces, Experiments) with benchmark results, live metrics, trace inspection, and experiment comparison. Docker images published to GHCR on push to main.

## Key findings

These are the most material results to date, drawn from the Phase 3 replication (5 independent runs of E1/E2/E3 under the current production configuration `think=false`, `num_ctx=16384`, 35-ticket normal set). Each bullet links to the supporting detail in [`docs/evaluation-checklist.md`](docs/evaluation-checklist.md).

- **All three Qwen 3.5 sizes (2B/4B/9B) achieve 100% first-pass JSON validity** under production config. The original n=1 claim that "the 2B is unusable for structured output" measured thinking-mode + 4096-token-context brokenness, not model capability. ([§ Phase 3 Replication — Finding 2](docs/evaluation-checklist.md#phase-3-replication-n5-thinkfalse-num_ctx16384))
- **The 9B is the accuracy leader**, not the 4B. Category accuracy: 9B 83.4% > 4B 80.6% > 2B 74.9%. With reliability equalized at 100% JSON validity, classification accuracy becomes the differentiator and the quality-size curve is monotonic. ([§ Phase 3 Replication — Finding 3](docs/evaluation-checklist.md#phase-3-replication-n5-thinkfalse-num_ctx16384))
- **First-pass validity ~100% reduces retry to a safety net.** Retry rate is ~0–3% under production config, down from 43–51% under the original configuration. The validator-first pipeline still holds as defense-in-depth and observability — its operational role has shifted from "active correction loop" to "insurance." ([§ Phase 3 Replication — Finding 5](docs/evaluation-checklist.md#phase-3-replication-n5-thinkfalse-num_ctx16384), [`docs/tradeoffs.md` § Post-implementation observations](docs/tradeoffs.md#post-implementation-observations))
- **Reproducibility is high.** Across 5 runs, accuracy metrics have stddev ≤ 5% and latency stddev ≤ 3%. The numbers in this README are baselines, not point observations. ([§ Phase 3 Replication — Finding 4](docs/evaluation-checklist.md#phase-3-replication-n5-thinkfalse-num_ctx16384))
- **The ground-truth dataset had a 14% label-error rate.** Model consensus against a label (all three models, all 5 runs = 0/5 on the same field) surfaced 5 incorrect labels in the 35-ticket normal set, corrected in this PR. Model disagreement with ground truth is a more reliable audit signal than manual review. ([§ Ground Truth Audit](docs/evaluation-checklist.md#ground-truth-audit))

Phase 4 adversarial findings were collected at n=1 under the original configuration and have **not** been replicated under the current config — they should be read as single-run observations pending Phase 4 replication.

## Production configuration

These values are pinned in code so the app produces reproducible results regardless of Ollama server defaults or environmental state. Every value here is the single source of truth for its concern — changing it requires either a decision-log entry or a new ADR.

| Concern | Value | Where it lives |
| --- | --- | --- |
| Context window (`num_ctx`) | `16384` | `src/ticket_triage_llm/providers/ollama_qwen.py` — module constant `NUM_CTX`, applied via the `num_ctx` option on every `chat()` call |
| Thinking mode | disabled | `src/ticket_triage_llm/providers/ollama_qwen.py` — `think=False` passed as a top-level kwarg to `self._client.chat(...)`. Not a prompt suffix (`/no_think` does not work through the OpenAI-compatible endpoint and is not used here) |
| Temperature | `0.2` | `src/ticket_triage_llm/config.py` — module constant `TEMPERATURE`, passed via the `temperature` option |
| Top-p | `0.9` | `src/ticket_triage_llm/config.py` — module constant `TOP_P`, passed via the `top_p` option |
| Top-k | `40` | `src/ticket_triage_llm/config.py` — module constant `TOP_K`, passed via the `top_k` option |
| Repetition penalty | `1.0` (disabled) | `src/ticket_triage_llm/config.py` — module constant `REPETITION_PENALTY`, passed via the `repeat_penalty` option |
| Max output tokens (`num_predict`) | `2048` | `src/ticket_triage_llm/providers/ollama_qwen.py` — module constant `MAX_TOKENS` |
| Default demo model | `qwen3.5:9b` | `.env.example` (`OLLAMA_MODEL`) — drives the Triage tab dropdown's default selection via `app.py` |

The sampling parameters (temperature, top-p, top-k, repetition penalty) are deliberately **not** environment-configurable. They are module-level constants because drifting sampling values silently invalidates every prior experiment result. Any change requires a decision-log entry per the project's reproducibility rules.

See `docs/decisions/decision-log.md` for the rationale behind each pinned value — in particular the 2026-04-16 entries that locked the sampling parameters and established `think=false` as the production configuration.

## What this project is

`ticket-triage-llm` takes a raw support ticket and returns a validated triage object: category, severity, routing team, summary, draft reply, escalation flag, and a confidence score. The system is built around a validator-first inference pipeline with bounded retry, a provider abstraction that supports both local (Ollama) and cloud-hosted Qwen models, and a built-in observability dashboard for runtime metrics and benchmark results.

**Key features:**
- **Multi-model support** — switchable Qwen 3.5 models (2B/4B/9B) via dropdown in the Triage tab or `OLLAMA_MODELS` env var
- **Heuristic guardrail** — injection phrase detection, structural marker screening, PII pattern matching, and length checks per ADR 0008
- **Bounded retry with repair prompt** — on validation failure, sends the failed output plus specific error back to the model for self-correction (exactly one retry per ADR 0002)
- **Config-driven provider registry** — add models via environment variables, no code changes required

The project is deliberately constrained to consumer hardware (Apple Silicon, ≤24GB unified memory) for the local execution path. That constraint is a feature, not a workaround — it reflects the deployment context most production LLM systems will actually face outside of well-funded AI labs.

## Project goals

This project is structured around a single engineering question:

> **In a production LLM system, how much of the value comes from the model itself versus from the surrounding engineering controls — and how well can layered mitigations defend against prompt injection in user-submitted content?**

To answer that, the system supports four planned experiments:

1. **Model size comparison** — how task quality, latency, and reliability scale across small, medium, and larger Qwen 3.5 variants on the same hardware
2. **Local vs cloud comparison** — what the cloud premium actually buys on this task, within the same model family
3. **Validation impact** — how much the validator-first pipeline (parse + schema + bounded retry) contributes to overall reliability vs. the model alone
4. **Prompt comparison** — how much careful prompt design contributes vs. model selection

The findings from these experiments will be reported as part of the project deliverable, along with a documented decision matrix showing what factors were weighed and why.

## Tech stack

- **Language:** Python (≥3.11)
- **UI:** Gradio (`gr.Blocks` with tabs for triage, metrics, traces, and experiments)
- **API:** FastAPI with Gradio mounted as sub-application
- **Local inference:** Ollama, with Qwen 3.5 model variants (2B, 4B, 9B)
- **Schema validation:** Pydantic 2.x
- **Storage:** SQLite (stdlib `sqlite3`, no ORM) with repository pattern
- **Dependency management:** `uv`
- **Testing:** `pytest` with 80% coverage minimum
- **Linting / formatting:** `ruff`
- **Architecture decisions:** ADRs in `docs/adr/` (managed via `adr-tools`)

## Quick start

### Prerequisites

- Python ≥3.11
- [uv](https://docs.astral.sh/uv/) package manager
- [Ollama](https://ollama.com/) running on localhost (for Phase 1+)

### Install and verify

```bash
# Install dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=ticket_triage_llm --cov-fail-under=80

# Lint and format check
uv run ruff check .
uv run ruff format --check .
```

### Run the app

#### Prerequisites

Ollama must be **installed and running** on the host before the app will work. The app container does not include Ollama — it runs natively on your machine to use the GPU (see ADR 0007).

```bash
# Install Ollama: https://ollama.com/
# Start it (runs in background)
ollama serve

# Pull at least the default model
ollama pull qwen3.5:9b

# Optional: pull all three for the model comparison dropdown
ollama pull qwen3.5:2b
ollama pull qwen3.5:4b
```

#### Option A: run natively

```bash
# 1. Create your .env file (one-time setup)
cp .env.example .env

# 2. Start the app
uv run python -m ticket_triage_llm.app
```

Open **http://localhost:7860** in your browser. Select a model from the dropdown, paste a ticket, and click Triage.

### Managing models

Two env vars control the Triage tab's model dropdown. They are **distinct** — a common source of confusion:

| Env var | Purpose | Accepts | Example |
| --- | --- | --- | --- |
| `OLLAMA_MODELS` | Which models appear in the dropdown | Comma-separated list of Ollama model names | `qwen3.5:2b,qwen3.5:4b,qwen3.5:9b` |
| `OLLAMA_MODEL` | Which model is selected by default when the Triage tab opens | A single Ollama model name (must also be in `OLLAMA_MODELS`) | `qwen3.5:9b` |

The default model is **not** "the first entry in `OLLAMA_MODELS`." It is whatever `OLLAMA_MODEL` is set to. If `OLLAMA_MODEL` is unset or not present in the registry, the app falls back to the first entry in `OLLAMA_MODELS`.

#### Add a model

1. Pull it with Ollama:

    ```bash
    ollama pull <model-name>
    ```

2. Add its name to `OLLAMA_MODELS` in `.env`:

    ```
    OLLAMA_MODELS=qwen3.5:2b,qwen3.5:4b,qwen3.5:9b,<model-name>
    ```

3. Restart the app.

#### Remove a model

Remove its name from `OLLAMA_MODELS` in `.env` and restart the app. The model weights remain pulled on disk — if you want to reclaim that disk space, run `ollama rm <model-name>`.

#### Change the default model

Set `OLLAMA_MODEL` in `.env` to the model name you want pre-selected:

```
OLLAMA_MODEL=qwen3.5:4b
```

The name must also appear in `OLLAMA_MODELS`, otherwise the registry can't find it and the app falls back to `OLLAMA_MODELS`'s first entry.

#### Using cloud models via Ollama's passthrough

If your local Ollama server has cloud models available (you've signed in with `ollama signin` and `ollama list` shows entries with a `:cloud` suffix), you can add them to `OLLAMA_MODELS` just like local models:

```
OLLAMA_MODELS=qwen3.5:9b,qwen3.5:397b-cloud
```

No code changes required. Ollama transparently proxies the request from your local `:11434` endpoint to `ollama.com`, and the app doesn't need to know whether a given model is running locally or in the cloud.

**Caveat (unverified):** The app sends a specific request configuration on every triage — `num_ctx=16384`, `think=false`, `temperature=0.2`, `top_p=0.9`, `top_k=40`, `repeat_penalty=1.0`. Whether Ollama Cloud honors all of these parameters end-to-end has not been verified in this project. Cloud runs should therefore **not** be compared directly against the Phase 3/4 benchmark numbers until a smoke test confirms the parameters round-trip. See [`docs/future-improvements.md`](docs/future-improvements.md) for the cloud-provider integration status.

#### Docker caveat

The Dockerfile sets its own `ENV OLLAMA_MODEL=qwen3.5:9b` and `ENV OLLAMA_MODELS=qwen3.5:2b,qwen3.5:4b,qwen3.5:9b` defaults that apply to the containerized runtime. These override `.env` on the host because the container has its own environment. To use different values in Docker:

- With `docker compose`: add the envs under the `app` service's `environment:` key, or set them in a `.env` file next to `docker-compose.yml`.
- With `docker run`: pass `-e OLLAMA_MODEL=<name>` and/or `-e OLLAMA_MODELS=<list>`.

#### Container image

A multi-platform Docker image (amd64 + arm64) is published to GHCR on every push to `main`:

```bash
docker pull ghcr.io/rgoshen/ticket-triage-llm:latest

# macOS / Windows (host.docker.internal resolves automatically)
docker run --rm -p 7860:7860 -v "$PWD/data:/app/data" ghcr.io/rgoshen/ticket-triage-llm:latest

# Linux (host.docker.internal is not available by default)
docker run --rm --network=host -v "$PWD/data:/app/data" \
  -e OLLAMA_BASE_URL=http://localhost:11434/v1 ghcr.io/rgoshen/ticket-triage-llm:latest
```

Ollama must still be running on the host (see prerequisites above).

#### Option B: run in Docker

The Docker container runs the app only — Ollama stays on the host for GPU access.

```bash
# Build and run (recommended)
docker compose up --build

# Or without docker compose
docker build -t ticket-triage-llm .
docker run --rm -p 7860:7860 -v "$PWD/data:/app/data" ticket-triage-llm
```

Open **http://localhost:7860** in your browser.

The container reaches Ollama at `host.docker.internal:11434` (Mac/Windows). On Linux, add `--network=host` to the `docker run` command, or add `network_mode: host` to `docker-compose.yml`.

#### Verify it's working

The Gradio UI should show a Triage tab with a model dropdown, subject/body fields, and Triage/Cancel/New Ticket buttons.

You can also test the REST API directly:

```bash
curl -X POST http://localhost:7860/api/v1/triage \
  -H "Content-Type: application/json" \
  -d '{"ticket_body": "My printer is offline and I cannot print any documents.", "ticket_subject": "Printer not working"}'
```

### Run evaluation experiments

The eval harness runs four experiments against the triage pipeline using the normal dataset (`data/normal_set.jsonl`, 35 tickets). All runners require Ollama running with models pulled.

```bash
# E1: Model size comparison — runs each model in OLLAMA_MODELS through the full
# normal set with prompt v1 and full validation. One run_id per model.
OLLAMA_MODELS=qwen3.5:2b,qwen3.5:4b,qwen3.5:9b \
  uv run python -m ticket_triage_llm.eval.runners.run_local_comparison

# E3: Validation impact — runs 4B with and without validation, plus 9B without
# validation (the E2 data point). Three passes total.
uv run python -m ticket_triage_llm.eval.runners.run_validation_impact

# E4: Prompt comparison — v1 only (Phase 6 scoped out; see decision log).
uv run python -m ticket_triage_llm.eval.runners.run_prompt_comparison

# Summarize any run by its run_id (printed by the runners during execution)
uv run python -m ticket_triage_llm.eval.runners.summarize_results --run-id <RUN_ID>
```

All runners accept `--db-path`, `--dataset-path`, and `--output-dir` flags (defaults: `data/traces.db`, `data/normal_set.jsonl`, `data/phase3/`). Results are written as JSON to `data/phase3/` and as tagged traces in the SQLite database.

**E2 (Model size vs engineering controls)** is not a separate runner — it's composed by `summarize_results.py` from the 2B row of E1 and the 9B-no-validation row produced by E3.

## Repository structure

```text
ticket-triage-llm/
├── .github/
│   ├── workflows/ci.yml              # GitHub Actions: lint, format, test
│   ├── workflows/docker-publish.yml  # GHCR: build + push on main
│   └── PULL_REQUEST_TEMPLATE.md
├── docs/
│   ├── adr/                           # Architecture Decision Records
│   │   ├── README.md                  # ADR index
│   │   ├── 0001-language-and-stack.md
│   │   ├── 0002-validator-first-pipeline-with-bounded-retry.md
│   │   ├── 0003-pipeline-failure-handling-and-error-contract.md
│   │   ├── 0004-provider-abstraction-via-python-protocol.md
│   │   ├── 0005-sqlite-trace-storage-with-repository-pattern.md
│   │   ├── 0006-single-app-gradio-architecture.md
│   │   ├── 0007-local-deployment-with-docker.md
│   │   ├── 0008-heuristic-only-guardrail-baseline.md
│   │   ├── 0009-monitoring-distinct-from-benchmarking.md
│   │   └── 0010-non-actionable-and-ambiguous-input-handling.md
│   ├── decisions/decision-log.md      # Scope/framing decisions
│   ├── architecture.md
│   ├── evaluation-plan.md
│   ├── evaluation-checklist.md
│   ├── threat-model.md
│   ├── tradeoffs.md
│   ├── cost-analysis.md
│   ├── future-improvements.md
│   └── archive/                       # Original plan and rubric (read-only)
├── src/ticket_triage_llm/
│   ├── __init__.py
│   ├── app.py                         # FastAPI + Gradio entry point
│   ├── config.py                      # Settings via pydantic-settings
│   ├── logging_config.py              # Structured logging
│   ├── schemas/                       # Pydantic models (all implemented)
│   │   ├── triage_input.py            # TriageInput
│   │   ├── triage_output.py           # TriageOutput + enums
│   │   ├── model_result.py            # ModelResult
│   │   ├── trace.py                   # TraceRecord, TriageSuccess/Failure, FailureReason
│   │   └── errors.py                  # assert_never helper
│   ├── providers/                     # LLM provider abstraction
│   │   ├── base.py                    # LlmProvider Protocol
│   │   ├── errors.py                  # ProviderError exception
│   │   ├── ollama_qwen.py             # OllamaQwenProvider (implemented)
│   │   └── cloud_qwen.py              # CloudQwenProvider (stub — future work)
│   ├── storage/                       # SQLite + repository pattern
│   │   ├── db.py                      # Connection + schema init
│   │   └── trace_repo.py              # TraceRepository Protocol
│   ├── services/                      # Business logic
│   │   ├── triage.py                  # Pipeline orchestrator (run_triage)
│   │   ├── prompt.py                  # Prompt version dispatch
│   │   ├── validation.py              # JSON parse + schema validation
│   │   └── trace.py                   # SqliteTraceRepository
│   ├── ui/                            # Gradio tabs
│   │   └── triage_tab.py              # Triage tab (implemented)
│   ├── api/                           # FastAPI routes
│   │   └── triage_route.py            # POST /api/v1/triage
│   ├── prompts/                       # Prompt templates
│   └── eval/                          # Evaluation harness
│       ├── datasets.py                # Dataset loader (GroundTruth, TicketRecord)
│       ├── results.py                 # ModelMetrics, ExperimentSummary
│       └── runners/                   # Experiment runners + summarizer
│           ├── common.py              # run_experiment_pass() shared loop
│           ├── run_local_comparison.py # E1: model size comparison
│           ├── run_validation_impact.py# E3: validation on/off + E2 data
│           ├── run_prompt_comparison.py# E4: prompt comparison (v1 only)
│           └── summarize_results.py   # summarize_run(), compose_e2(), CLI
├── Dockerfile                         # Multi-stage app container build
├── tests/
│   ├── unit/                          # 210+ unit tests
│   ├── integration/                   # API route smoke tests
│   └── eval/                          # Eval harness tests
├── data/
│   ├── normal_set.jsonl               # 35 normal tickets
│   └── adversarial_set.jsonl          # Adversarial test set
├── scripts/
│   └── phase0_smoke_test.py           # Phase 0 smoke-test runner
├── pyproject.toml                     # uv-managed, source of truth for deps
├── uv.lock
├── ruff.toml
├── .env.example
├── .dockerignore
├── TODO.md                            # Phased build plan with checkboxes
├── SUMMARY.md                         # Historical log across all phases
├── CLAUDE.md                          # AI assistant instructions
└── LICENSE                            # MIT
```

## Documentation

- **[Project plan](docs/PLAN.md)** — full plan including architecture, model strategy, evaluation plan, and open decisions
- **[Architecture](docs/architecture.md)** — system overview, pipeline diagram, key components
- **[ADR index](docs/adr/README.md)** — all Architecture Decision Records
- **[Decision log](docs/decisions/decision-log.md)** — chronological scope/framing/strategy decisions
- **[Evaluation plan](docs/evaluation-plan.md)** — experiment design and methodology
- **[Threat model](docs/threat-model.md)** — prompt injection defense layers
- **[Tradeoffs](docs/tradeoffs.md)** — design tradeoff analysis
- **[Cost analysis](docs/cost-analysis.md)** — three-component cost analysis
- **[TODO](TODO.md)** — phased build plan with progress checkboxes
- **[SUMMARY](SUMMARY.md)** — what was done, how, and what went wrong

## Context

This project is the final deliverable for an LLMs-in-Production course based on Brousseau & Sharp, *LLMs in Production* (Manning, 2024). It is intended to demonstrate the engineering judgment, evaluation rigor, and decision-making process that go into selecting and deploying an LLM under real-world constraints — not just the act of building a chatbot.

## License

This project is licensed under the [MIT License](LICENSE).
