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
├── .gitignore
├── README.md                         # this file
├── docs/
│   ├── adr/                          # Architecture Decision Records (ADRs)
│   │   ├── README.md                 # ADR index / register
│   │   └── 0001-language-and-stack.md
│   ├── archive/
│   │   ├── Final Project Rubric.docx
│   │   └── llm-ticket-triage-plan.md # original plan
│   ├── decisions/                    # non-architecture decisions
│   │   └── decision-log.md           # chronological log of scope and framing decisions
│   └── PLAN.md                       # full project plan
├── src/                              # application code (forthcoming)
└── tests/                            # test suite (forthcoming)
```

## Running the project

> Forthcoming. Setup, install, and run instructions will be added as the project takes shape.

## Documentation

- **[Project plan](docs/llm-ticket-triage-plan.md)** — full plan including architecture, model strategy, evaluation plan, and open decisions
- **[Decision log](docs/decision-log.md)** — chronological log of scope, framing, and strategy decisions
- **[ADR index](docs/decisions/README.md)** — index of all Architecture Decision Records

## Context

This project is the final deliverable for an LLMs-in-Production course based on Brousseau & Sharp, *LLMs in Production* (Manning, 2024). It is intended to demonstrate the engineering judgment, evaluation rigor, and decision-making process that go into selecting and deploying an LLM under real-world constraints — not just the act of building a chatbot.
