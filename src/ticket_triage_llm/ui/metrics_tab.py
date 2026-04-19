"""Metrics tab — benchmark results and live metrics — Phase 5."""

import logging
from pathlib import Path

import gradio as gr

from ticket_triage_llm.eval.datasets import load_dataset
from ticket_triage_llm.eval.runners.summarize_results import summarize_run
from ticket_triage_llm.services.metrics import get_live_summary, list_run_ids
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)

NORMAL_DATASET_PATH = Path("data/normal_set.jsonl")

WINDOW_OPTIONS = {"1 hour": 1, "24 hours": 24, "7 days": 168, "All time": None}


def build_metrics_tab_content(trace_repo: TraceRepository) -> None:
    tickets = []
    if NORMAL_DATASET_PATH.exists():
        try:
            tickets = load_dataset(NORMAL_DATASET_PATH)
        except Exception:
            logger.warning("Could not load normal dataset for benchmark summaries")

    def _get_run_choices():
        runs = list_run_ids(trace_repo)
        if not runs:
            return [], None
        choices = [
            f"{r['run_id']} — {r['model']} ({r['ticket_count']} tickets)" for r in runs
        ]
        return choices, choices[0] if choices else None

    def _extract_run_id(choice: str | None) -> str | None:
        if not choice:
            return None
        return choice.split(" — ")[0]

    def load_benchmark(choice: str | None):
        run_id = _extract_run_id(choice)
        if not run_id or not tickets:
            return "No benchmark data available.", []

        try:
            metrics = summarize_run(run_id, tickets, trace_repo)
        except ValueError:
            return "No traces found for this run.", []

        kpi_text = (
            f"**Category Accuracy:** {metrics.category_accuracy:.1%}  \n"
            f"**JSON Validity:** {metrics.json_valid_rate:.1%}  \n"
            f"**Schema Pass Rate:** {metrics.schema_pass_rate:.1%}  \n"
            f"**p95 Latency:** {metrics.p95_latency_ms:.0f} ms  \n"
            f"**Retry Rate:** {metrics.retry_rate:.1%}  \n"
            f"**Success:** {metrics.successful_tickets}/{metrics.total_tickets}"
        )

        tps = (
            f"{metrics.avg_tokens_per_second:.1f}"
            if metrics.avg_tokens_per_second
            else "N/A"
        )
        table_data = [
            [
                metrics.model,
                f"{metrics.category_accuracy:.1%}",
                f"{metrics.severity_accuracy:.1%}",
                f"{metrics.routing_accuracy:.1%}",
                f"{metrics.json_valid_rate:.1%}",
                f"{metrics.schema_pass_rate:.1%}",
                f"{metrics.retry_rate:.1%}",
                f"{metrics.p50_latency_ms:.0f}",
                f"{metrics.p95_latency_ms:.0f}",
                tps,
                f"{metrics.successful_tickets}/{metrics.total_tickets}",
            ]
        ]

        return kpi_text, table_data

    def refresh_runs():
        choices, default = _get_run_choices()
        return gr.update(choices=choices, value=default)

    def load_live(window_label: str):
        window_hours = WINDOW_OPTIONS.get(window_label)
        summary = get_live_summary(trace_repo, window_hours)

        if summary["total_requests"] == 0:
            return (
                "No live traffic recorded yet. "
                "Submit tickets through the Triage tab to see live metrics."
            )

        return (
            f"**Total Requests:** {summary['total_requests']}  \n"
            f"**Success Rate:** {summary['success_rate']:.1%}  \n"
            f"**Avg Latency:** {summary['avg_latency_ms']:.0f} ms  \n"
            f"**p50 Latency:** {summary['p50_latency_ms']:.0f} ms  \n"
            f"**p95 Latency:** {summary['p95_latency_ms']:.0f} ms  \n"
            f"**Retry Rate:** {summary['retry_rate']:.1%}  \n"
            f"**Error Rate:** {summary['error_rate']:.1%}"
        )

    # --- Benchmark Results section ---
    gr.Markdown("## Benchmark Results")

    initial_choices, initial_default = _get_run_choices()

    with gr.Row():
        run_selector = gr.Dropdown(
            choices=initial_choices,
            value=initial_default,
            label="Select Run",
            scale=4,
        )
        refresh_btn = gr.Button("Refresh", scale=1)

    benchmark_kpi = gr.Markdown(
        value="Select a run to view benchmark results."
        if initial_choices
        else "No benchmark runs found. Run an experiment to see results here."
    )

    benchmark_table = gr.Dataframe(
        headers=[
            "Model",
            "Cat Acc",
            "Sev Acc",
            "Route Acc",
            "JSON Valid %",
            "Schema Pass %",
            "Retry %",
            "p50 ms",
            "p95 ms",
            "Tok/s",
            "Success",
        ],
        interactive=False,
    )

    run_selector.change(
        fn=load_benchmark,
        inputs=[run_selector],
        outputs=[benchmark_kpi, benchmark_table],
    )

    refresh_btn.click(fn=refresh_runs, outputs=[run_selector])

    # --- Live Metrics section ---
    gr.Markdown("---")
    gr.Markdown("## Live Metrics")

    with gr.Row():
        window_selector = gr.Radio(
            choices=list(WINDOW_OPTIONS.keys()),
            value="All time",
            label="Time Window",
        )
        live_refresh_btn = gr.Button("Refresh")

    live_kpi = gr.Markdown(
        value=(
            "No live traffic recorded yet. "
            "Submit tickets through the Triage tab to see live metrics."
        )
    )

    window_selector.change(
        fn=load_live,
        inputs=[window_selector],
        outputs=[live_kpi],
    )

    live_refresh_btn.click(
        fn=load_live,
        inputs=[window_selector],
        outputs=[live_kpi],
    )
