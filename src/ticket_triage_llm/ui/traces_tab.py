"""Traces tab — request inspection and filtering — Phase 5."""

import json
import logging

import gradio as gr

from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)

VALIDATION_OPTIONS = ["All", "valid", "valid_after_retry", "invalid", "skipped"]
STATUS_OPTIONS = ["All", "success", "failure"]
LIMIT_OPTIONS = [25, 50, 100]

TABLE_HEADERS = [
    "Timestamp",
    "Model",
    "Status",
    "Validation",
    "Latency (ms)",
    "Tokens",
    "Retry",
    "Guardrail",
]


def build_traces_tab_content(trace_repo: TraceRepository) -> None:
    def _load_traces(provider_filter, validation_filter, status_filter, limit):
        limit = int(limit)
        traces = trace_repo.get_recent_traces(limit=500)

        if provider_filter and provider_filter != "All":
            traces = [t for t in traces if t.provider == provider_filter]
        if validation_filter and validation_filter != "All":
            traces = [t for t in traces if t.validation_status == validation_filter]
        if status_filter and status_filter != "All":
            traces = [t for t in traces if t.status == status_filter]

        traces = traces[:limit]

        rows = []
        for t in traces:
            rows.append(
                [
                    t.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    t.model,
                    t.status,
                    t.validation_status,
                    f"{t.latency_ms:.0f}",
                    str(t.tokens_total),
                    str(t.retry_count),
                    t.guardrail_result,
                ]
            )
        return rows

    def _get_providers():
        traces = trace_repo.get_recent_traces(limit=500)
        providers = sorted({t.provider for t in traces})
        return ["All"] + providers

    def _format_detail(evt: gr.SelectData, table_data):
        if evt.index is None or not table_data:
            return "Select a row to view trace details."

        row_idx = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
        if row_idx >= len(table_data):
            return "Select a row to view trace details."

        row = table_data[row_idx]
        timestamp_str = row[0]

        traces = trace_repo.get_recent_traces(limit=500)
        trace = None
        for t in traces:
            if (
                t.timestamp.strftime("%Y-%m-%d %H:%M:%S") == timestamp_str
                and t.model == row[1]
            ):
                trace = t
                break

        if not trace:
            return "Could not find trace details."

        triage_json = ""
        if trace.triage_output_json:
            try:
                parsed = json.loads(trace.triage_output_json)
                triage_json = json.dumps(parsed, indent=2)
            except json.JSONDecodeError:
                triage_json = trace.triage_output_json

        tps = f"{trace.tokens_per_second:.1f}" if trace.tokens_per_second else "N/A"

        detail = (
            f"### Trace Details\n\n"
            f"**Metadata**  \n"
            f"Request ID: `{trace.request_id}`  \n"
            f"Run ID: `{trace.run_id or 'live'}`  \n"
            f"Ticket ID: `{trace.ticket_id or 'N/A'}`  \n"
            f"Model: {trace.model}  \n"
            f"Provider: {trace.provider}  \n"
            f"Prompt Version: {trace.prompt_version}\n\n"
            f"**Timing**  \n"
            f"Latency: {trace.latency_ms:.0f} ms  \n"
            f"Tokens: {trace.tokens_total} "
            f"(in={trace.tokens_input}, out={trace.tokens_output})  \n"
            f"Tokens/sec: {tps}  \n"
            f"Estimated Cost: ${trace.estimated_cost:.4f}\n\n"
            f"**Pipeline**  \n"
            f"Guardrail: {trace.guardrail_result}  \n"
        )
        if trace.guardrail_matched_rules:
            detail += f"Matched Rules: {', '.join(trace.guardrail_matched_rules)}  \n"
        detail += (
            f"Validation: {trace.validation_status}  \n"
            f"Retry Count: {trace.retry_count}  \n"
            f"Failure Category: {trace.failure_category or 'N/A'}\n\n"
        )

        if trace.ticket_body:
            body_preview = trace.ticket_body[:500]
            if len(trace.ticket_body) > 500:
                body_preview += "..."
            detail += f"**Ticket Body**  \n```\n{body_preview}\n```\n\n"

        if trace.raw_model_output:
            raw_preview = trace.raw_model_output[:1000]
            if len(trace.raw_model_output) > 1000:
                raw_preview += "..."
            detail += f"**Raw Model Output**  \n```\n{raw_preview}\n```\n\n"

        if triage_json:
            detail += f"**Triage Output**  \n```json\n{triage_json}\n```"

        return detail

    gr.Markdown("## Trace Explorer")

    initial_providers = _get_providers()

    with gr.Row():
        provider_filter = gr.Dropdown(
            choices=initial_providers,
            value="All",
            label="Provider",
        )
        validation_filter = gr.Dropdown(
            choices=VALIDATION_OPTIONS,
            value="All",
            label="Validation Status",
        )
        status_filter = gr.Dropdown(
            choices=STATUS_OPTIONS,
            value="All",
            label="Status",
        )
        limit_selector = gr.Dropdown(
            choices=[str(x) for x in LIMIT_OPTIONS],
            value="50",
            label="Limit",
        )
        refresh_btn = gr.Button("Refresh")

    initial_data = _load_traces("All", "All", "All", 50)

    trace_table = gr.Dataframe(
        value=initial_data,
        headers=TABLE_HEADERS,
        interactive=False,
    )

    trace_detail = gr.Markdown(
        value="Select a row to view trace details.",
    )

    def refresh_traces(provider, validation, status, limit):
        rows = _load_traces(provider, validation, status, limit)
        providers = _get_providers()
        return rows, gr.update(choices=providers)

    refresh_btn.click(
        fn=refresh_traces,
        inputs=[provider_filter, validation_filter, status_filter, limit_selector],
        outputs=[trace_table, provider_filter],
    )

    for filt in [provider_filter, validation_filter, status_filter, limit_selector]:
        filt.change(
            fn=_load_traces,
            inputs=[
                provider_filter,
                validation_filter,
                status_filter,
                limit_selector,
            ],
            outputs=[trace_table],
        )

    trace_table.select(
        fn=_format_detail,
        inputs=[trace_table],
        outputs=[trace_detail],
    )
