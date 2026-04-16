# 0006. Single-app Gradio architecture

## Status

Accepted

## Context

The project requires a web UI with four distinct views: a triage submission form with result display, a metrics dashboard with benchmark results and live monitoring, a trace explorer for inspecting individual requests, and an experiments comparison view. Additionally, the UI needs interactive controls: a model/provider selector dropdown, sample ticket loaders, and filtering on the traces and experiments views.

The UI must coexist with the backend pipeline (validation, retry, provider routing, trace storage, metrics computation) in a way that is straightforward to develop, test, demo, and deploy.

ADR 0001 established Python as the language and Gradio as the UI framework. This ADR addresses the *architecture* of the Gradio app: how the four views are organized, how the UI relates to the backend services, and why the entire system runs as a single process rather than as separate frontend and backend applications.

## Options Considered

### Option A: Single-process Gradio app with `gr.Blocks` and tabbed layout

One Python process runs a `gr.Blocks` app with four `gr.Tab` components. Each tab is defined in its own module (`ui/triage_tab.py`, `ui/metrics_tab.py`, etc.) for code organization, but they all share the same in-process service layer. The app entry point (`app.py`) wires the tabs together and starts Gradio. There is no HTTP API between the UI and the backend — all calls are Python function calls within the same process.

### Option B: Gradio frontend + FastAPI backend (two processes)

Gradio serves the UI and calls a separate FastAPI backend via HTTP. The backend exposes REST endpoints (`POST /triage`, `GET /metrics`, etc.) and the Gradio app is a thin client that renders the responses. Two processes, two dependency configurations, communication over HTTP.

### Option C: Gradio frontend + FastAPI backend (one process, mounted)

FastAPI serves as the main app and Gradio is mounted as a sub-application at a route prefix (e.g., `/ui`). The backend exposes both the REST API and the Gradio UI. One process, but two frameworks with their own routing, middleware, and lifecycle concerns.

## Decision

We chose **Option A: single-process Gradio app with `gr.Blocks` and tabbed layout**.

The architecture is:

```
app.py (entry point)
  └── gr.Blocks
        ├── gr.Tab("Triage")     → ui/triage_tab.py
        ├── gr.Tab("Metrics")    → ui/metrics_tab.py
        ├── gr.Tab("Traces")     → ui/traces_tab.py
        └── gr.Tab("Experiments") → ui/experiments_tab.py

Each tab calls into:
  services/triage.py
  services/metrics.py
  services/trace.py
  services/guardrail.py
  services/validation.py
  services/retry.py
  services/prompt.py
  services/provider_router.py

Services call into:
  providers/ollama_qwen.py
  storage/trace_repo.py
```

All of this runs in one Python process. There is no HTTP between layers — only Python function calls. Gradio's built-in server handles the browser-to-server communication; everything behind Gradio is in-process.

### Tab module structure

Each tab module exports a function that takes a `gr.Blocks` context and builds its UI components and event handlers within it. This keeps tab definitions self-contained and independently readable while sharing the service layer:

```python
# ui/triage_tab.py
def build_triage_tab(services: ServiceContainer) -> None:
    with gr.Tab("Triage"):
        # Gradio components and event wiring here
        ...
```

The `ServiceContainer` (or equivalent) is a simple object that holds references to the shared service instances, avoiding the need for global state or module-level singletons.

## Rationale

1. **A single process eliminates an entire category of work.** A split frontend/backend architecture requires: defining an API contract, serializing/deserializing across the HTTP boundary, handling CORS, managing two sets of dependencies, debugging "is the backend up" issues, potentially two Docker containers, and version-coordinating the API between frontend and backend deployments. None of this work produces rubric points. All of it consumes build time.

2. **The project has no use case for a separate API.** A REST API is valuable when multiple clients need to consume the same backend (a mobile app, a CLI tool, a third-party integration). This project has one consumer: the Gradio UI. Building an API that only one client ever calls is architecture for architecture's sake. If a future iteration needs an API (e.g., for integration with a real ticketing system), FastAPI can be added at that point — the service layer is already structured to be callable from any consumer, not just Gradio.

3. **Gradio's `gr.Blocks` with tabs maps directly to the four views.** Each tab is a self-contained view with its own layout and event handlers, but they share the same process memory and the same service instances. This means the Triage tab can submit a ticket, the trace is stored, and the Traces tab immediately sees it without any polling, webhooks, or cache invalidation — because they're reading from the same in-process `TraceRepository` instance.

4. **The service layer is decoupled from Gradio despite sharing a process.** Services are pure Python modules with no Gradio imports. They accept typed inputs and return typed outputs. This means they can be called from the eval runner (which has no UI), from tests (which have no UI), or from a future FastAPI layer — without modification. The single-process architecture does not create coupling; it just removes the HTTP hop.

5. **This pattern was proven in Assignment 11.** The developer built a Gradio chat frontend with `gr.Blocks` wrapping `gr.ChatInterface`, connected to Ollama, with streaming and dynamic model discovery, in the same course. The patterns for event wiring, component layout, and Ollama integration are already in working memory. This is the lowest-risk path for a constrained build.

## Tradeoffs

- **Upside:** One codebase, one process, one `uv run` command, one Docker container. No API contract to maintain. No serialization overhead. Shared in-process state means instant data visibility across tabs. The service layer is still cleanly separated and independently testable. Faster to build, faster to debug, faster to demo.

- **Downside:** Gradio's component library is less flexible than a custom React UI. Complex interactive features (drag-and-drop, real-time WebSocket updates, custom chart interactions) are harder or impossible in Gradio. The UI will look like a Gradio app, not like a custom product. There is no standalone API endpoint for external consumers.

- **Why we accept the downside:** The rubric grades engineering judgment, evaluation rigor, and documentation — not frontend polish. The visual difference between Gradio and React does not translate into rubric points. The missing API endpoint is not needed today and can be added later without changing the service layer. The interactive limitations of Gradio do not affect any of the four planned views, all of which are well within what `gr.Blocks` supports (forms, tables, charts, dropdowns, filtered lists).

## Consequences

- The app is started with a single command (`uv run python -m ticket_triage_llm.app` or equivalent). There is no separate backend to start.

- For Docker deployment, there is one container running one process. The `Dockerfile` is a straightforward Python application container.

- Gradio exposes its own HTTP server (default port 7860) which serves both the UI and Gradio's internal API for component updates. This is the only network surface of the application. Ollama's port (11434) is a separate service on the host.

- Tab modules are independent of each other. Adding a fifth tab (e.g., a "Cost Analysis" tab) is a matter of creating a new module and adding one `gr.Tab` block to `app.py`. No routing changes, no API endpoints, no contract updates.

- The eval runner does *not* go through Gradio. It imports the service layer directly and calls `triage_service.run_triage()` in a loop. This is possible precisely because the service layer has no Gradio dependency — it's pure Python. The eval runner and the Gradio app are two different entry points into the same service layer.

- If the project ever needs a REST API (for integration with a real ticketing system, for example), FastAPI can be added alongside Gradio in the same process, calling the same service layer. This is a common pattern (FastAPI + Gradio mounted together) and does not require rearchitecting the service layer. The single-app decision does not foreclose this option.

## Alternatives Not Chosen

- **Option B (Gradio + FastAPI, two processes):** rejected because it doubles the operational surface (two processes, two dependency sets, HTTP between them, CORS, "is the backend up" debugging) without adding any capability the project actually needs. The only benefit — a standalone API — has no consumer today. The cost in build time is real; the benefit is speculative.

- **Option C (Gradio mounted on FastAPI, one process):** rejected because it adds FastAPI's routing, middleware, and lifecycle management to a project that doesn't need them. If the only consumer of the API is Gradio running in the same process, the API is ceremony. This option makes sense when you genuinely need both a REST API for external consumers *and* a Gradio UI for humans — but this project only needs the latter.
