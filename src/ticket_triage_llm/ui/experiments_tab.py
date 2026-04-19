"""Experiments tab — side-by-side experiment comparison — Phase 5."""

import gradio as gr

from ticket_triage_llm.storage.trace_repo import TraceRepository


def build_experiments_tab_content(trace_repo: TraceRepository) -> None:
    gr.Markdown("## Experiments\n\n*Coming soon — Phase 5*")
