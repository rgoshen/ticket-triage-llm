# ticket-triage-llm

A production-style support ticket triage system built on local LLMs, with a focus on prompt injection defense and structured-output reliability under realistic adversarial conditions.

> **Status:** In active development. Not yet ready for use.

## What this project is

`ticket-triage-llm` takes a raw support ticket and returns a validated triage object: category, severity, routing team, summary, draft reply, escalation flag, and a confidence score. The system is built around a validator-first inference pipeline with bounded retry, a provider abstraction that supports both local (Ollama) and cloud-hosted Qwen models, and a built-in observability dashboard for runtime metrics and benchmark results.

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

- **Language:** Python
- **UI:** Gradio (`gr.Blocks` with multiple tabs for triage, metrics, traces, and experiments)
- **Local inference:** Ollama, with Qwen 3.5 model variants
- **Cloud inference:** Within the Qwen family (provider TBD — see project plan)
- **Dependency management:** `uv`
- **Testing:** `pytest` with 80% coverage minimum
- **Linting / formatting:** `ruff`
- **Architecture decisions:** ADRs in `docs/decisions/` (managed via `adr-tools`)

## Repository structure

```text
ticket-triage-llm/
├── .github/
├── .remember/
├── .adr-dir                          # adr tools config
├── README.md
├── DEPLOYMENT.md                   # forthcoming — native and Docker quick-start
├── Dockerfile                      # forthcoming — Phase 1
├── .dockerignore                   # forthcoming — Phase 1
├── pyproject.toml                  # uv-managed, source of truth for deps
├── uv.lock
├── .env
├── .env.example
├── .gitignore
├── ruff.toml
├── data
│   ├── adversarial_set.jsonl
│   └── normal_set.jsonl
├── docs/
│   ├── PLAN.md                     # this document
│   ├── cost-analysis.md            # three-component cost analysis
│   ├── adr/                        # ADRs (adr-tools format)
│   │   ├── README.md
│   │   └── 0001-language-and-stack.md
│   ├── decisions/                  # scope/framing decisions (non-architectural)
│   │   └── decision-log.md         # chronological decision log
│   ├── archive/                    # original plan and rubric (reference)
│   ├── architecture.md             # forthcoming
│   ├── evaluation-plan.md          # forthcoming
│   ├── tradeoffs.md                # forthcoming
│   ├── prompt-versions.md          # forthcoming
│   ├── threat-model.md             # forthcoming — prompt injection threat model
│   ├── demo-script.md              # forthcoming
│   └── presentation-notes.md       # forthcoming
│
├── src/
│   └── ticket_triage_llm/
│       ├── __init__.py
│       ├── app.py                  # FastAPI + Gradio entry point
│       ├── config.py               # env loading, settings
│       │
│       ├── api/                    # FastAPI route(s)
│       │   ├── __init__.py
│       │   └── triage_route.py     # POST /api/v1/triage
│       │
│       ├── ui/                     # Gradio tab definitions
│       │   ├── __init__.py
│       │   ├── triage_tab.py       # ticket input + result display
│       │   ├── metrics_tab.py      # benchmark dashboard
│       │   ├── traces_tab.py       # trace explorer
│       │   └── experiments_tab.py  # experiment comparison
│       │
│       ├── services/               # business logic
│       │   ├── __init__.py
│       │   ├── triage.py           # orchestrates the full pipeline
│       │   ├── prompt.py           # prompt building / versioning
│       │   ├── guardrail.py        # pre-LLM input screening
│       │   ├── validation.py       # parse + schema + semantic checks
│       │   ├── retry.py            # bounded retry policy
│       │   ├── trace.py            # trace recording
│       │   ├── metrics.py          # metrics aggregation
│       │   └── provider_router.py  # selects active provider
│       │
│       ├── providers/              # LLM provider implementations
│       │   ├── __init__.py
│       │   ├── base.py             # LlmProvider Protocol
│       │   ├── ollama_qwen.py      # local Ollama provider
│       │   └── cloud_qwen.py       # cloud Qwen provider (provider TBD)
│       │
│       ├── prompts/                # prompt templates by version
│       │   ├── __init__.py
│       │   ├── triage_v1.py
│       │   ├── triage_v2.py
│       │   └── repair_json_v1.py
│       │
│       ├── schemas/                # pydantic models
│       │   ├── __init__.py
│       │   ├── triage_input.py
│       │   ├── triage_output.py
│       │   └── trace.py
│       │
│       ├── storage/                # SQLite + repository pattern
│       │   ├── __init__.py
│       │   ├── db.py               # connection / schema setup
│       │   └── trace_repo.py       # single repository — traces are the source of truth
│       │
│       └── eval/                   # evaluation harness
│           ├── __init__.py
│           ├── datasets/
│           │   ├── gold_tickets.json
│           │   └── adversarial_tickets.json
│           ├── runners/
│           │   ├── __init__.py
│           │   ├── run_local_comparison.py
│           │   ├── run_local_vs_cloud.py
│           │   ├── run_validation_impact.py
│           │   ├── run_prompt_comparison.py
│           │   └── summarize_results.py
│           └── reports/
│               └── (generated benchmark output)
│
└── tests/
    ├── __init__.py
    ├── unit/
    │   ├── test_validation.py
    │   ├── test_guardrail.py
    │   ├── test_retry.py
    │   └── test_prompts.py
    ├── integration/
    │   ├── test_triage_pipeline.py
    │   └── test_providers.py
    └── eval/
        └── test_eval_runners.py
```

## Running the project

> Forthcoming. Setup, install, and run instructions will be added as the project takes shape.

## Documentation

- **[Project plan](docs/llm-ticket-triage-plan.md)** — full plan including architecture, model strategy, evaluation plan, and open decisions
- **[Decision log](docs/decision-log.md)** — chronological log of scope, framing, and strategy decisions
- **[ADR index](docs/decisions/README.md)** — index of all Architecture Decision Records

## Context

This project is the final deliverable for an LLMs-in-Production course based on Brousseau & Sharp, *LLMs in Production* (Manning, 2024). It is intended to demonstrate the engineering judgment, evaluation rigor, and decision-making process that go into selecting and deploying an LLM under real-world constraints — not just the act of building a chatbot.
