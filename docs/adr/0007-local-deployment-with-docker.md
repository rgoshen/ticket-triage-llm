# 0007. Local-only deployment with Docker for app, Ollama on host

## Status

Accepted

## Context

The project needs a deployment strategy that satisfies two requirements:

1. **The rubric explicitly grades deployment.** Environment Setup is worth 15 points, and the "Excellent" tier requires the model to be "successfully deployed in a chosen production environment (local, AWS, etc.)" with the environment "configured correctly and the model accessible via an API endpoint."

2. **The instructor or TA needs to actually run it.** A project that only works on the developer's machine is not deployed — it's just developed. The deployment must be reproducible on other machines without requiring the evaluator to replicate the developer's exact environment.

The project's consumer-hardware thesis constrains the deployment to local infrastructure. Cloud deployment (AWS, GCP, etc.) would contradict the thesis that useful LLM systems can run on standard consumer hardware.

The system has two runtime components: the Gradio application (Python) and the Ollama model server (which serves the Qwen 3.5 models). The deployment strategy must account for both.

## Options Considered

### Option A: Docker for the app, Ollama on the host

The Gradio application runs inside a Docker container. Ollama runs natively on the host machine, outside the container. The container reaches Ollama via `host.docker.internal:11434` (Mac/Windows) or the host network (Linux). The deploying user installs Ollama and pulls the models separately, then starts the container with one command.

### Option B: Everything in Docker (app + Ollama in one container or docker-compose)

Both the Gradio app and Ollama run inside Docker. Models are either baked into the image or pulled on first run. One command starts everything.

### Option C: Native only, no Docker

The deploying user clones the repo, runs `uv sync`, starts Ollama, and runs the app natively. No container involved.

### Option D: Cloud deployment (AWS, GCP, etc.)

Deploy to a cloud VM or managed service. The evaluator accesses the system via a public URL.

## Decision

We chose **Option A: Docker for the app, Ollama on the host**.

The deployment architecture is:

```text
┌─────────────────────────────────┐
│         Host machine            │
│                                 │
│  ┌───────────┐  ┌────────────┐  │
│  │  Ollama   │  │  Docker    │  │
│  │  (native) │◄─┤  container │  │
│  │  :11434   │  │  (Gradio)  │  │
│  │           │  │  :7860     │  │
│  └───────────┘  └────────────┘  │
│                                 │
│  Qwen 3.5 models served by     │
│  Ollama with GPU/MLX access     │
└─────────────────────────────────┘
```

Two deployment paths are documented in `DEPLOYMENT.md`:

**Quick start with Docker:**
1. Install Ollama
2. Pull models: `ollama pull qwen3.5:2b && ollama pull qwen3.5:4b && ollama pull qwen3.5:9b`
3. `docker run` the container (exact command in `DEPLOYMENT.md`)
4. Open `http://localhost:7860`

**Quick start without Docker (native):**
1. Install Ollama
2. Pull models (same as above)
3. `uv sync`
4. `uv run python -m ticket_triage_llm.app`
5. Open `http://localhost:7860`

Both paths require Ollama and the models to be present on the host. The Docker path additionally requires Docker. The native path additionally requires `uv` and Python 3.11+.

## Rationale

1. **Docker on Mac/Windows runs in a Linux VM that has no access to the Apple GPU.** This is the single most important fact driving the decision. If Ollama runs inside a Docker container on Apple Silicon, it cannot use Metal or MLX acceleration. Inference falls back to CPU-only, which is dramatically slower — potentially 5–10x depending on model size. This defeats the project's consumer-hardware thesis and would make the demo painfully slow. Keeping Ollama on the host preserves GPU acceleration.

2. **A split architecture (app in container, model server on host) is how Ollama is typically deployed.** Ollama's documentation and community patterns treat it as a host-level service, not a containerized one. The app connects to it over HTTP like any other service dependency. This is a standard pattern, not an unusual one.

3. **The Docker container makes the *app* reproducible without making the *model server* reproducible.** This is an honest tradeoff. The container guarantees that the Python environment, dependencies, and application code are identical across machines. It does not guarantee that Ollama is installed or that the models are pulled. The remaining manual steps (install Ollama, pull models) are documented and are the same three commands on every platform.

4. **Offering both Docker and native paths gives the evaluator a choice.** If the evaluator has Docker, they get a reproducible environment with no Python setup. If they don't have Docker (or prefer not to use it), they can run natively with `uv`. Either way, the system works. This is more resilient than offering only one path.

5. **Cloud deployment was rejected because it contradicts the project's thesis.** The project argues that useful LLM systems can run on consumer hardware without cloud infrastructure. Deploying to AWS would undermine that argument. Local deployment *is* the point.

## Tradeoffs

- **Upside:** GPU/MLX acceleration is preserved. The container is small (~500MB vs 12GB+ with models). The app environment is fully reproducible via Docker. Both Docker and native paths are supported. The architecture matches standard Ollama deployment patterns.

- **Downside:** The deploying user still has to install Ollama and pull models manually — the deployment is not fully "one command." The Docker container depends on being able to reach Ollama on the host, which requires `host.docker.internal` (Mac/Windows) or `--network=host` (Linux), and these mechanisms work slightly differently across platforms.

- **Why we accept the downside:** The Ollama + model setup is three commands and is documented. The alternative (baking Ollama into the container) would produce a worse system — slower inference, larger image, and a non-standard deployment that doesn't reflect how Ollama is actually used. The cross-platform networking differences are documented in `DEPLOYMENT.md` with platform-specific instructions.

## Consequences

- `Dockerfile` lives at the repo root. It builds the Python app only — no Ollama, no models.

- `.dockerignore` excludes `data/`, `.env`, model files, and other non-app content.

- `DEPLOYMENT.md` lives at the repo root and documents both paths (Docker and native) with platform-specific notes for macOS, Windows, and Linux. It also explains *why* Ollama is outside the container (the GPU acceleration reasoning) so that the architecture choice is transparent to the reader.

- The Ollama endpoint URL is configurable via environment variable (defaulting to `http://localhost:11434`). For Docker on Mac/Windows, the container overrides this to `http://host.docker.internal:11434`. For Docker on Linux with `--network=host`, the default works as-is.

- The `data/` directory (containing the SQLite trace database) should be mounted as a Docker volume so that traces persist across container restarts.

- Cross-platform testing is performed on macOS, Windows, and Linux before the deployment is treated as verified. Tested platforms are documented in `DEPLOYMENT.md`.

- Gradio's built-in server exposes port 7860. The Docker container maps this port to the host. This is the only port the container exposes. Ollama's port (11434) is managed by the host-level Ollama installation, not by the container.

## Alternatives Not Chosen

- **Option B (everything in Docker):** rejected primarily because Docker on Mac/Windows cannot access the Apple GPU. Ollama inside a container on Apple Silicon runs CPU-only, which is 5–10x slower and defeats the consumer-hardware thesis. Secondary reasons: the container image would be enormous (12GB+ with three Qwen models baked in) or require a slow first-run pull, and the architecture would not reflect how Ollama is typically deployed.

- **Option C (native only, no Docker):** rejected because it requires the evaluator to have `uv`, the correct Python version, and a compatible system configuration. Docker removes those variables. Native is offered as a second path for evaluators who prefer it, but it is not the primary documented path because it is less reproducible.

- **Option D (cloud deployment):** rejected because it contradicts the project's consumer-hardware thesis. The thesis is that useful LLM systems can run on standard consumer hardware without cloud infrastructure. Deploying to cloud would undermine the argument the project is making.
