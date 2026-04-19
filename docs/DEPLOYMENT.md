# Deployment

Practical guide to running `ticket-triage-llm` on your own hardware. This document covers the native path (`uv run`), the Docker path (image published to GHCR), architecture context that explains *why* the split is the way it is, and a troubleshooting section for the failure modes we've actually hit during development.

**Tested platforms:** macOS (Apple Silicon M4 Pro, 24 GB unified memory) is the primary development and demo target. **Cross-platform validation (Windows, Linux) is pending** — see the "Tested platforms" section at the bottom for what this means in practice.

---

## Before anything else: install and start Ollama

The app does not include Ollama. Ollama runs natively on your host machine so that local inference can use the machine's GPU — see [ADR 0007](adr/0007-local-deployment-with-docker.md) for why this split exists. Docker Desktop on macOS and Windows does not have Apple GPU access, so containerizing Ollama would force CPU-only inference and defeat the consumer-hardware thesis.

```bash
# 1. Install Ollama (https://ollama.com/)
# 2. Start the Ollama server in the background
ollama serve

# 3. Pull at least the default model (9B per OD-4 resolution)
ollama pull qwen3.5:9b

# 4. Optional: pull the smaller models so the dropdown has all three
ollama pull qwen3.5:2b
ollama pull qwen3.5:4b
```

Confirm Ollama is running: `curl http://localhost:11434/api/tags` should return a JSON list of pulled models.

---

## Option A: Native (`uv run`)

Use this path when you have the repo cloned and want the fastest turnaround between code changes and runtime. This is the primary development path.

```bash
# 1. Install dependencies
uv sync --all-extras

# 2. Copy the env template
cp .env.example .env

# 3. (Optional) edit .env to customize model selection — see README's
#    "Managing models" section for add/remove/change-default guidance
#    and the cloud-model passthrough caveat

# 4. Start the app
uv run python -m ticket_triage_llm.app
```

Open **http://localhost:7860** in your browser.

### Verification

- The Gradio UI should show a Triage tab with a model dropdown pre-selected to `ollama:qwen3.5:9b`.
- Paste a test ticket (e.g., `"My printer is offline and I cannot print any documents."`) and click Triage. A result should return in roughly 3–10 seconds on an M4 Pro 24GB.
- The REST API is available at `/api/v1/triage`:

    ```bash
    curl -X POST http://localhost:7860/api/v1/triage \
      -H "Content-Type: application/json" \
      -d '{"ticket_body": "My printer is offline.", "ticket_subject": "Printer"}'
    ```

- Swagger UI is at **http://localhost:7860/docs**.

---

## Option B: Docker

Use this path when you want an isolated runtime, when you're deploying on a shared machine, or when you're rehearsing the containerized release path. A multi-platform image (linux/amd64 + linux/arm64) is published to GHCR on every push to `main` — see [`.github/workflows/docker-publish.yml`](../.github/workflows/docker-publish.yml).

### Quick-start: pre-built image from GHCR

```bash
docker pull ghcr.io/rgoshen/ticket-triage-llm:latest

# macOS / Windows — host.docker.internal resolves automatically
docker run --rm -p 7860:7860 \
  -v "$PWD/data:/app/data" \
  ghcr.io/rgoshen/ticket-triage-llm:latest
```

### Quick-start: build locally

```bash
# With docker compose (recommended)
docker compose up --build

# Or build + run manually
docker build -t ticket-triage-llm .
docker run --rm -p 7860:7860 -v "$PWD/data:/app/data" ticket-triage-llm
```

Either way, open **http://localhost:7860**.

### Linux addendum

`host.docker.internal` is not available by default on Linux. Pass `--network=host` instead:

```bash
docker run --rm --network=host \
  -v "$PWD/data:/app/data" \
  -e OLLAMA_BASE_URL=http://localhost:11434/v1 \
  ghcr.io/rgoshen/ticket-triage-llm:latest
```

Or add `network_mode: host` to `docker-compose.yml`'s `app` service.

### Customizing the container at runtime

The Dockerfile sets its own `ENV OLLAMA_MODEL=qwen3.5:9b` and `ENV OLLAMA_MODELS=qwen3.5:2b,qwen3.5:4b,qwen3.5:9b` defaults. These **override** `.env` on the host because the container has its own environment. To customize:

- `docker run -e OLLAMA_MODEL=qwen3.5:4b -e OLLAMA_MODELS=qwen3.5:4b,qwen3.5:9b ...`
- With `docker compose`: add an `environment:` block to the `app` service in `docker-compose.yml`, or put the values in a `.env` file that sits next to the compose file.

---

## Architecture: why Ollama runs on the host

In one sentence: **the container is the app; the model server is the host.**

- **GPU access.** Docker Desktop on macOS and Windows has no Apple GPU (Metal) passthrough. Running Ollama inside the container would force CPU-only inference, which is 10–30x slower and invalidates the consumer-hardware thesis of the project.
- **Model weights.** The 9B weighs ~6.6 GB. Bundling that in the image would make every pull painful and every update costly.
- **Model management.** `ollama pull` works out-of-the-box on the host with no extra configuration. Exposing it through a container would require bind-mounts and permission juggling without any real benefit.

See [ADR 0007](adr/0007-local-deployment-with-docker.md) for the full rationale and the options that were considered and rejected.

---

## Managing models

Adding, removing, and changing the default model is configured via two environment variables (`OLLAMA_MODELS` and `OLLAMA_MODEL`) with a specific distinction between them. Using cloud models via Ollama's built-in passthrough is also supported through the same mechanism, with a caveat about parameter forwarding.

See the **Managing models** section in the main [`README.md`](../README.md) for the authoritative guide. Don't duplicate it here — the README is where a new user lands first, and splitting the model-management docs between two files is how they rot.

---

## Troubleshooting

### "Only one model appears in the dropdown"

`OLLAMA_MODELS` is not set (or is set to a single-entry list). Check your `.env` file (for native) or the container's env (for Docker). In Docker, remember that the Dockerfile's `ENV OLLAMA_MODELS=...` default applies unless you override with `-e OLLAMA_MODELS=...` or a compose `environment:` block.

### "The default model isn't the one I expect"

`OLLAMA_MODEL` drives the default. It's a *separate* env var from `OLLAMA_MODELS`. The dropdown's default is not "the first entry in `OLLAMA_MODELS`" — it's whatever `OLLAMA_MODEL` is set to, provided that value also appears in `OLLAMA_MODELS`. If `OLLAMA_MODEL` is unset or points to a model not in the registry, the app falls back to the first entry in `OLLAMA_MODELS`.

### "Connection refused" or "Cannot reach Ollama"

- Confirm `ollama serve` is running: `curl http://localhost:11434/api/tags`.
- On Linux, add `--network=host` to `docker run` (the `host.docker.internal` DNS entry is macOS/Windows-only).
- On macOS/Windows, confirm Docker Desktop is running (it provides the `host.docker.internal` DNS entry).
- If Ollama was started with a non-default bind address, update `OLLAMA_BASE_URL` accordingly.

### "Model not found"

The model name in `OLLAMA_MODELS` (or `OLLAMA_MODEL`) must be pulled first. Run `ollama pull <model-name>` on the host and restart the app. Confirm with `ollama list`.

### "App starts but triage is very slow"

Baseline latency per model on an M4 Pro 24GB under production config (`think=false`, `num_ctx=16384`, prompt v1) from Phase 3 replication (n=5):

| Model | Mean latency | p95 latency |
| --- | --- | --- |
| Qwen 3.5 2B | ~3–4 s | ~8 s |
| Qwen 3.5 4B | ~3–5 s | ~10 s |
| Qwen 3.5 9B | ~7–10 s | ~15–20 s |

If you're seeing dramatically slower numbers:

- Confirm `think=false` is still in effect — check that the local Ollama server hasn't been upgraded to a version where the `think` kwarg is ignored (the expected output-token count should be ~150–300, not thousands).
- Confirm `num_ctx=16384` — a larger context on a memory-constrained machine can page to disk.
- Check whether Ollama has unloaded your model (`ollama ps`). The first request after an unload pays a warm-up cost of 5–10 seconds.
- If running on a machine smaller than 24 GB RAM, the 9B may not fit and swap into Q8_0 or spill to CPU — use the 4B or 2B instead.

### "Container starts but the UI is blank"

Confirm Gradio is mounted at the FastAPI root (`/`) and Swagger is at `/docs`. The container logs should show `Uvicorn running on http://0.0.0.0:7860` plus a Gradio initialization banner. If the browser shows a blank page, check that the port mapping (`-p 7860:7860`) matches and that no other service is already bound to `:7860`.

### "Triage returns a failure: parse_failure / schema_failure / model_unreachable"

The pipeline's typed failure envelope tells you the category. Quick map:

- `model_unreachable` — Ollama is down or unreachable. See "Connection refused" above.
- `guardrail_blocked` — The heuristic guardrail decided the input looks like an injection attempt. Normal for adversarial inputs; unexpected for benign tickets means the guardrail needs tuning (see [ADR 0008](adr/0008-heuristic-only-guardrail-baseline.md)).
- `parse_failure` — The model produced output that isn't valid JSON even after one repair retry. Rare under production config (~0–3%); common symptoms are exhausted token budget or the model producing prose instead of JSON.
- `schema_failure` / `semantic_failure` — The output parsed as JSON but didn't match `TriageOutput` shape or violated a semantic check. Same retry/recovery path as parse_failure.

The Traces tab in the UI shows full failure detail including the failed output, matched rules, and the repair prompt history.

---

## Tested platforms

| Platform | Status | Notes |
| --- | --- | --- |
| macOS (Apple Silicon, 24 GB) | **Primary target — tested** | M4 Pro 24GB unified memory. All demos, all evaluation runs. Docker via Docker Desktop with `host.docker.internal`. |
| macOS (Intel) | Not tested | Should work; GPU acceleration via Metal only available on Apple Silicon. |
| Windows 11 | **Not tested — pending** | Docker Desktop with WSL2 expected to work via `host.docker.internal`. Native path requires Python ≥3.11 + `uv`. |
| Linux (Ubuntu/Debian) | **Not tested — pending** | Docker requires `--network=host` for Ollama connectivity. Native path works identically to macOS. |

Cross-platform validation is deferred to a follow-up branch. If you run this on Windows or Linux, please open an issue with the result — working or not — so this table can be updated. A working macOS build, a published multi-platform image, and documented known-unknowns is a defensible deliverable for the course project; a claim of "works on every platform" without the test evidence is not.

---

## References

- [`README.md`](../README.md) — top-level setup and "Managing models" section
- [`docs/adr/0007-local-deployment-with-docker.md`](adr/0007-local-deployment-with-docker.md) — why Ollama runs on host
- [`docs/adr/0011-default-model-selection.md`](adr/0011-default-model-selection.md) — original 4B-as-default decision (superseded by 2026-04-19 OD-4 re-resolution)
- [`docs/decisions/decision-log.md`](decisions/decision-log.md) — all scope and framing decisions including the OD-4 re-resolution to 9B
- [`docs/threat-model.md`](threat-model.md) — what the guardrail does and does not defend against
