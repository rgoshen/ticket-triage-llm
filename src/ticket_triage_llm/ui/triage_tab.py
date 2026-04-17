"""Triage tab — ticket input, model selection, result display — Phase 1."""

import gradio as gr

from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.schemas.trace import TriageFailure, TriageSuccess
from ticket_triage_llm.services.triage import run_triage
from ticket_triage_llm.storage.trace_repo import TraceRepository


def build_triage_tab(provider: LlmProvider, trace_repo: TraceRepository) -> gr.Blocks:
    def handle_triage(ticket_subject: str, ticket_body: str):
        if not ticket_body.strip():
            return "Error: ticket body is required", ""

        result, trace = run_triage(
            ticket_body=ticket_body,
            ticket_subject=ticket_subject,
            provider=provider,
            prompt_version="v1",
            trace_repo=trace_repo,
        )

        trace_text = (
            f"Request ID: {trace.request_id}\n"
            f"Model: {trace.model}\n"
            f"Latency: {trace.latency_ms:.0f} ms\n"
            f"Tokens: {trace.tokens_total} "
            f"(in={trace.tokens_input}, out={trace.tokens_output})\n"
            f"Validation: {trace.validation_status}\n"
            f"Retry Count: {trace.retry_count}"
        )

        if isinstance(result, TriageSuccess):
            output = result.output
            result_text = (
                f"**Category:** {output.category}\n"
                f"**Severity:** {output.severity}\n"
                f"**Routing Team:** {output.routing_team}\n"
                f"**Escalation:** {output.escalation}\n"
                f"**Confidence:** {output.confidence:.0%}\n\n"
                f"**Summary:** {output.summary}\n\n"
                f"**Business Impact:** {output.business_impact}\n\n"
                f"**Draft Reply:** {output.draft_reply}"
            )
            return result_text, trace_text

        if isinstance(result, TriageFailure):
            result_text = (
                f"**Triage Failed**\n\n"
                f"**Failure:** {result.category}\n"
                f"**Detected By:** {result.detected_by}\n"
                f"**Message:** {result.message}"
            )
            if result.raw_model_output:
                result_text += (
                    f"\n\n**Raw Output:**\n```\n{result.raw_model_output[:500]}\n```"
                )
            return result_text, trace_text

        return "Unexpected result type", ""

    with gr.Blocks(title="Ticket Triage LLM") as demo:
        gr.Markdown("# Ticket Triage LLM")
        gr.Markdown(f"Using model: **{provider.name}** | Prompt: **v1**")

        with gr.Row():
            with gr.Column(scale=1):
                subject_input = gr.Textbox(
                    label="Subject (optional)",
                    placeholder="e.g., Cannot login to account",
                    lines=1,
                )
                body_input = gr.Textbox(
                    label="Ticket Body",
                    placeholder="Paste the support ticket text here...",
                    lines=10,
                )
                submit_btn = gr.Button("Triage", variant="primary")

            with gr.Column(scale=1):
                result_output = gr.Markdown(label="Triage Result")
                trace_output = gr.Textbox(
                    label="Trace Summary",
                    lines=6,
                    interactive=False,
                )

        submit_btn.click(
            fn=handle_triage,
            inputs=[subject_input, body_input],
            outputs=[result_output, trace_output],
        )

    return demo
