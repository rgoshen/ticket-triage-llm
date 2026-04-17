"""Triage tab — ticket input, model selection, result display — Phase 1."""

import gradio as gr

from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.storage.trace_repo import TraceRepository


def build_triage_tab(
    provider: LlmProvider, trace_repo: TraceRepository
) -> gr.Blocks:
    with gr.Blocks(title="Ticket Triage LLM") as demo:
        gr.Markdown("# Ticket Triage LLM — Loading...")
    return demo
