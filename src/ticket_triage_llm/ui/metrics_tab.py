"""Metrics tab — benchmark results and live metrics — Phase 5."""

import gradio as gr

from ticket_triage_llm.storage.trace_repo import TraceRepository


def build_metrics_tab_content(trace_repo: TraceRepository) -> None:
    gr.Markdown("## Metrics\n\n*Coming soon — Phase 5*")
