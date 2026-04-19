"""Traces tab — request inspection and filtering — Phase 5."""

import gradio as gr

from ticket_triage_llm.storage.trace_repo import TraceRepository


def build_traces_tab_content(trace_repo: TraceRepository) -> None:
    gr.Markdown("## Traces\n\n*Coming soon — Phase 5*")
