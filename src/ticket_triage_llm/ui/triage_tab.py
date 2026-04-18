"""Triage tab — ticket input, model selection, result display — Phase 2."""

import gradio as gr

from ticket_triage_llm.schemas.trace import TriageFailure, TriageSuccess
from ticket_triage_llm.services.provider_router import ProviderRegistry
from ticket_triage_llm.services.triage import run_triage
from ticket_triage_llm.storage.trace_repo import TraceRepository


def build_triage_tab(
    registry: ProviderRegistry,
    trace_repo: TraceRepository,
    default_provider: str | None = None,
    guardrail_max_length: int = 10_000,
) -> gr.Blocks:
    provider_names = registry.list_names()
    default_value = (
        default_provider if default_provider in provider_names else provider_names[0]
    )

    def handle_triage(provider_name: str, ticket_subject: str, ticket_body: str):
        if not ticket_body.strip():
            return "Error: ticket body is required", ""

        provider = registry.get(provider_name)
        result, trace = run_triage(
            ticket_body=ticket_body,
            ticket_subject=ticket_subject,
            provider=provider,
            prompt_version="v1",
            trace_repo=trace_repo,
            guardrail_max_length=guardrail_max_length,
        )

        trace_text = (
            f"Request ID: {trace.request_id}\n"
            f"Model: {trace.model}\n"
            f"Latency: {trace.latency_ms:.0f} ms\n"
            f"Tokens: {trace.tokens_total} "
            f"(in={trace.tokens_input}, out={trace.tokens_output})\n"
            f"Validation: {trace.validation_status}\n"
            f"Retry Count: {trace.retry_count}\n"
            f"Guardrail: {trace.guardrail_result}"
        )
        if trace.guardrail_matched_rules:
            trace_text += f"\nMatched Rules: {', '.join(trace.guardrail_matched_rules)}"

        if isinstance(result, TriageSuccess):
            output = result.output
            esc = "Yes" if output.escalation else "No"
            cat = output.category.replace("_", " ").title()
            sev = output.severity.title()
            team = output.routing_team.title()
            result_text = (
                f"### Triage Result\n\n"
                f"**Category:** {cat}  \n"
                f"**Severity:** {sev}  \n"
                f"**Routing Team:** {team}  \n"
                f"**Escalation:** {esc}\n\n"
                f"---\n\n"
                f"**Summary**  \n{output.summary}\n\n"
                f"**Business Impact**  \n"
                f"{output.business_impact}\n\n"
                f"**Draft Reply**  \n{output.draft_reply}"
            )
            return result_text, trace_text

        if isinstance(result, TriageFailure):
            if result.category == "guardrail_blocked":
                result_text = (
                    "**Ticket Blocked**\n\n"
                    "This ticket was flagged by the safety guardrail "
                    "and was not sent to the model."
                )
            elif result.category == "parse_failure":
                result_text = (
                    "**Triage Unavailable**\n\n"
                    "The model could not produce a structured response "
                    "for this ticket. Try again or select a different "
                    "model from the dropdown."
                )
            else:
                result_text = (
                    "**Triage Failed**\n\n"
                    f"The model response did not pass validation "
                    f"({result.category}). Try again or select a "
                    f"different model."
                )
            return result_text, trace_text

        return "Unexpected result type", ""

    with gr.Blocks(title="Ticket Triage LLM") as demo:
        gr.Markdown("# Ticket Triage LLM")

        with gr.Row():
            with gr.Column(scale=1):
                provider_dropdown = gr.Dropdown(
                    choices=provider_names,
                    value=default_value,
                    label="Model",
                )
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
                with gr.Row():
                    submit_btn = gr.Button("Triage", variant="primary", scale=2)
                    cancel_btn = gr.Button("Cancel", variant="stop", scale=1)
                    clear_btn = gr.Button("New Ticket", scale=1)

            with gr.Column(scale=1):
                status_output = gr.Markdown(value="", label="Status")
                result_output = gr.Markdown(label="Triage Result")
                with gr.Accordion("Trace Details", open=False):
                    trace_output = gr.Textbox(
                        label="Trace Summary",
                        lines=8,
                        interactive=False,
                    )

        def run_triage_with_status(
            provider_name, ticket_subject, ticket_body
        ):
            result_text, trace_text = handle_triage(
                provider_name, ticket_subject, ticket_body
            )
            return "", result_text, trace_text

        triage_event = submit_btn.click(
            fn=lambda: ("*Processing ticket...*", "", ""),
            inputs=None,
            outputs=[status_output, result_output, trace_output],
        ).then(
            fn=run_triage_with_status,
            inputs=[provider_dropdown, subject_input, body_input],
            outputs=[status_output, result_output, trace_output],
        )

        cancel_btn.click(
            fn=lambda: ("*Ticket submission cancelled.*", "", ""),
            inputs=None,
            outputs=[status_output, result_output, trace_output],
            cancels=[triage_event],
        )

        clear_btn.click(
            fn=lambda: ("", "", "", "", ""),
            inputs=None,
            outputs=[
                subject_input,
                body_input,
                status_output,
                result_output,
                trace_output,
            ],
        )

    return demo
