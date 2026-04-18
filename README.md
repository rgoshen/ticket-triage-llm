# ticket-triage-llm

A production-style support ticket triage system built on local LLMs, with a focus on prompt injection defense and structured-output reliability under realistic adversarial conditions.

> **Status:** Phase 3 complete — eval harness built with four experiment runners and summarizer. Phase 4 (adversarial evaluation) is next.

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

Ollama must be **installed and running** on the host before the app will work. Pull at least one model:

```bash
ollama pull qwen3.5:4b          # recommended starting point
ollama pull qwen3.5:2b          # lighter alternative
ollama pull qwen3.5:9b          # higher quality, slower
```

#### Option A: run natively

```bash
# Set the models via env var (comma-separated list)
OLLAMA_MODELS=qwen3.5:2b,qwen3.5:4b,qwen3.5:9b uv run python -m ticket_triage_llm.app

# Or copy .env.example → .env and set OLLAMA_MODELS there
cp .env.example .env             # then edit OLLAMA_MODELS=qwen3.5:4b,qwen3.5:9b
uv run python -m ticket_triage_llm.app
```

**Configuration note:** `OLLAMA_MODELS` is a comma-separated list of model names. All models in the list will appear in the Triage tab dropdown. The first model in the list is the default selection.

#### Option B: run in Docker (app container only — Ollama stays on host)

```bash
docker build -t ticket-triage-llm .
docker run --rm -p 7860:7860 -v "$PWD/data:/app/data" ticket-triage-llm
```

The container reaches Ollama via `host.docker.internal:11434` (Mac/Windows). On Linux, use `--network=host` instead.

#### Verify it's working

Open the Gradio UI at **http://localhost:7860**.

Or test the REST API directly:

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

# E4: Prompt comparison — runs v1 (and v2 after Phase 6) on one model.
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
│           ├── run_prompt_comparison.py# E4: prompt v1 vs v2
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

- **[Project plan](PLAN.md)** — full plan including architecture, model strategy, evaluation plan, and open decisions
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
