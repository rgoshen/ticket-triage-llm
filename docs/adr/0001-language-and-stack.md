# 0001. Language and stack choice

## Status

Accepted

## Context

`ticket-triage-llm` needs a language and stack chosen before any pipeline, validation, or evaluation work can begin. The choice has to support:

- a validator-first inference pipeline with bounded retry
- a provider abstraction supporting both local (Ollama) and cloud-hosted Qwen models
- structured-output handling against a fixed schema
- a multi-tab GUI for triage submission, metrics dashboard, traces, and experiments
- an evaluation harness for running labeled benchmarks across model variants
- standard developer hygiene: tests, linting, dependency management, reproducible builds

The relevant constraints are:

- the build window is constrained, so familiarity with the toolchain matters
- the project is being built solo
- the developer's prior coursework and established repo conventions are in Python (`uv`, `pytest`, `ruff`, `src/` and `tests/` layout, 80% coverage minimum)
- a previous course assignment built a Gradio chat frontend connected to Ollama, so the patterns for that integration are already known

## Options Considered

### Option A: Python + Gradio (single-app architecture)

A single Python application using Gradio's `gr.Blocks` to host multiple tabs (triage, metrics, traces, experiments). Backend logic — provider abstraction, validation, retry, trace storage, evaluation — lives in the same Python codebase as the UI, organized into service modules. Ollama is reached via the `ollama` Python client for model discovery and the `openai` client (pointed at Ollama's OpenAI-compatible endpoint) for chat completions, mirroring the hybrid pattern from the prior course assignment.

### Option B: TypeScript / Node + React (split client/server architecture)

A Node/Express (or similar) backend exposing a REST API, with a separate React frontend for the UI. Provider abstraction and validation logic in TypeScript on the backend. UI built with React components for the triage form, dashboard, traces page, and experiments page.

### Option C: Python + Streamlit (single-app architecture)

Same shape as Option A, but with Streamlit instead of Gradio for the UI layer.

## Decision

We chose **Option A: Python + Gradio**.

The full stack is:

- **Language:** Python
- **UI framework:** Gradio (`gr.Blocks` with multiple tabs)
- **Local inference client:** `ollama` Python library for model discovery, `openai` client pointed at Ollama's OpenAI-compatible endpoint for chat completions
- **Dependency management:** `uv`
- **Testing:** `pytest` with 80% coverage minimum
- **Linting / formatting:** `ruff`
- **Repository layout:** `src/` for application code, `tests/` for the test suite, `docs/` for documentation

## Rationale

1. **Toolchain familiarity reduces execution risk.** Every prior course assignment was Python, and the developer's established repo conventions (`uv`, `pytest`, `ruff`, `src/` / `tests/` layout) are all Python-native. Putting unfamiliar tooling on a constrained build path is exactly the failure mode to avoid when the goal is rigorous evaluation, not framework exploration.

2. **The Python LLM ecosystem is where the relevant tools live.** `pydantic` maps cleanly onto the validator-first architecture and is effectively the canonical tool for structured-output validation in Python. The `ollama` and `openai` Python clients are mature and well-documented. Equivalents exist in TypeScript but are less mature and less battle-tested.

3. **Single-app architecture eliminates an entire category of work.** A split client/server architecture means two codebases, two dependency trees, two deployments, CORS handling, API versioning, and "is the backend up" debugging. A single Gradio app collapses all of that into one process and one `uv run` command. Time saved on integration glue is time available for evaluation, documentation, and the prompt-injection investigation that is the project's central engineering question.

4. **Gradio specifically is already known.** A prior course assignment built a Gradio frontend over `gr.Blocks` and `gr.ChatInterface` connected to Ollama, including streaming, dynamic model discovery, and conversation history management. The patterns for the new project's UI tabs are direct extensions of patterns already in the developer's working memory, not new ground.

5. **The grading rubric values pipeline rigor, evaluation depth, and documentation, not frontend craft.** Every hour spent on a polished React UI is an hour not spent on the eval set, the prompt injection investigation, the cost analysis, or the ADRs. The visible quality difference between a Gradio dashboard and a React dashboard does not translate into rubric points; the visible quality difference between a thoughtful evaluation and a thin one does.

## Tradeoffs

- **Upside:** Lower execution risk, faster iteration, full stack in one language, all tooling already familiar, one process to deploy and demo, more time available for the work the rubric actually rewards.

- **Downside:** Gradio's visual customization is more limited than a hand-built React UI. Dashboards built in Gradio look like Gradio dashboards — clean and functional, but not as polished as a custom-designed product UI. Charts will use `gr.Plot` with matplotlib or plotly rather than custom-styled components. The aesthetic is closer to "internal tool" than "consumer product."

- **Why we accept the downside:** The project is being graded on engineering judgment, evaluation rigor, and the quality of the central investigation. Visual polish is not a graded dimension. The downside affects how the project *looks* in screenshots; the upside affects whether the project *works* and *says something interesting*. The latter matters more for both the grade and the long-term portfolio value of the project.

## Consequences

- All code lives in a single Python repository with the layout `src/ticket_triage_llm/` for application code and `tests/` for the test suite.
- Dependency management is via `uv`, with `pyproject.toml` as the source of truth.
- The provider abstraction will be implemented as a Python `Protocol` or abstract base class with concrete implementations for the local Ollama provider and the cloud Qwen provider.
- Schema validation will use `pydantic` models for the triage input, the triage output, and the trace record format.
- The Gradio UI will be structured as a `gr.Blocks` app with one tab per major view (triage, metrics, traces, experiments), all backed by the same in-process service layer.
- No separate frontend build step, no API server, no CORS configuration, no client/server contract management.

## Alternatives Not Chosen

- **TypeScript + Node + React (Option B):** Rejected because it requires building two codebases in a language the developer has not used for the rest of the course, while solving problems (CORS, API contracts, separate deployments) that bring no rubric points. The visible UI quality gain is real but does not justify the execution risk and the time cost.

- **Python + Streamlit (Option C):** Rejected because the developer has not used Streamlit before. While Streamlit is well-suited to dashboard-heavy applications and would likely work fine for this project, learning a new framework on a constrained build path is exactly the failure mode that motivated rejecting Option B. Gradio is already known and the patterns from the prior course assignment carry directly over.
