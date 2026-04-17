# --- Builder stage ---
FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

COPY src/ src/

# --- Runtime stage ---
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH"
ENV OLLAMA_BASE_URL="http://host.docker.internal:11434/v1"
ENV OLLAMA_MODEL="qwen3.5:4b"
ENV DB_PATH="/app/data/traces.db"

EXPOSE 7860

CMD ["python", "-m", "ticket_triage_llm.app"]
