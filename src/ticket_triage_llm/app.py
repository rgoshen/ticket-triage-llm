"""FastAPI + Gradio entry point — Phase 2."""

import os

import gradio as gr
import uvicorn
from fastapi import FastAPI

from ticket_triage_llm.api.triage_route import configure as configure_api
from ticket_triage_llm.api.triage_route import router as api_router
from ticket_triage_llm.config import Settings
from ticket_triage_llm.logging_config import configure_logging
from ticket_triage_llm.providers.ollama_qwen import OllamaQwenProvider
from ticket_triage_llm.services.provider_router import ProviderRegistry
from ticket_triage_llm.services.trace import SqliteTraceRepository
from ticket_triage_llm.storage.db import get_connection, init_schema
from ticket_triage_llm.ui.triage_tab import build_triage_tab


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings.log_level)

    os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)
    conn = get_connection(settings.db_path)
    init_schema(conn)
    trace_repo = SqliteTraceRepository(conn)

    registry = ProviderRegistry()

    model_list = [m.strip() for m in settings.ollama_models.split(",") if m.strip()]

    if not model_list:
        model_list = [settings.ollama_model]

    for model_name in model_list:
        provider = OllamaQwenProvider(
            model=model_name,
            base_url=settings.ollama_base_url,
        )
        registry.register(provider)

    configure_api(registry, trace_repo)

    gradio_app = build_triage_tab(
        registry,
        trace_repo,
        default_provider=f"ollama:{settings.ollama_model}",
    )
    app = FastAPI(title="Ticket Triage LLM", version="0.2.0")
    app.include_router(api_router)
    app = gr.mount_gradio_app(app, gradio_app, path="/")

    return app


if __name__ == "__main__":
    application = create_app()
    uvicorn.run(application, host="0.0.0.0", port=7860)
