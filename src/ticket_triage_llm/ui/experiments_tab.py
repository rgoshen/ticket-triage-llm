"""Experiments tab — side-by-side experiment comparison — Phase 5."""

import logging
from pathlib import Path

import gradio as gr

from ticket_triage_llm.eval.datasets import load_dataset
from ticket_triage_llm.eval.runners.summarize_results import summarize_run
from ticket_triage_llm.services.metrics import group_runs_by_experiment, list_run_ids
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)

NORMAL_DATASET_PATH = Path("data/normal_set.jsonl")

EXPERIMENT_DESCRIPTIONS = {
    "E1: Model Size Comparison": (
        "How does quality scale with model size on consumer hardware? "
        "Compares Qwen 3.5 2B vs 4B vs 9B."
    ),
    "E2: Model Size vs Engineering Controls": (
        "Can a smaller model with full validation match a larger model "
        "without? Smallest-with-validation vs largest-without."
    ),
    "E3: Validation Impact": (
        "What do engineering controls actually buy? "
        "Full pipeline vs no validation on same model."
    ),
    "E4: Prompt Comparison": (
        "How much does prompt design contribute? Prompt v1 vs v2 on same model."
    ),
    "Adversarial: Injection Defense": (
        "Per-layer mitigation effectiveness against the adversarial ticket set."
    ),
}

BENCHMARK_HEADERS = [
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
]

ADVERSARIAL_HEADERS = [
    "Model",
    "Tickets",
    "Success",
    "Failure",
    "Parse Fail",
    "Guardrail Blocked",
]


def build_experiments_tab_content(trace_repo: TraceRepository) -> None:
    tickets = []
    if NORMAL_DATASET_PATH.exists():
        try:
            tickets = load_dataset(NORMAL_DATASET_PATH)
        except Exception:
            logger.warning("Could not load normal dataset for experiment summaries")

    def _get_experiment_choices():
        runs = list_run_ids(trace_repo)
        groups = group_runs_by_experiment(runs)
        return list(groups.keys()) if groups else []

    def _load_experiment(experiment_name: str | None):
        if not experiment_name:
            return "Select an experiment.", []

        description = EXPERIMENT_DESCRIPTIONS.get(experiment_name, "")
        desc_text = f"**{experiment_name}**\n\n{description}\n\n"

        runs = list_run_ids(trace_repo)
        groups = group_runs_by_experiment(runs)
        experiment_runs = groups.get(experiment_name, [])

        if not experiment_runs:
            return desc_text + "No runs found for this experiment.", []

        is_adversarial = experiment_name.startswith("Adversarial")

        table_rows = []
        for run in experiment_runs:
            run_id = run["run_id"]
            if is_adversarial:
                traces = trace_repo.get_traces_by_run(run_id)
                total = len(traces)
                successes = sum(1 for t in traces if t.status == "success")
                failures = sum(1 for t in traces if t.status == "failure")
                parse_fails = sum(
                    1 for t in traces if t.failure_category == "parse_failure"
                )
                blocked = sum(1 for t in traces if t.guardrail_result == "block")
                table_rows.append(
                    [
                        run["model"],
                        str(total),
                        str(successes),
                        str(failures),
                        str(parse_fails),
                        str(blocked),
                    ]
                )
            else:
                if not tickets:
                    table_rows.append(
                        [
                            run["model"],
                            "N/A",
                            "N/A",
                            "N/A",
                            "N/A",
                            "N/A",
                            "N/A",
                            "N/A",
                            "N/A",
                            "N/A",
                            "N/A",
                        ]
                    )
                    continue
                try:
                    m = summarize_run(run_id, tickets, trace_repo)
                    tps = (
                        f"{m.avg_tokens_per_second:.1f}"
                        if m.avg_tokens_per_second
                        else "N/A"
                    )
                    table_rows.append(
                        [
                            m.model,
                            f"{m.category_accuracy:.1%}",
                            f"{m.severity_accuracy:.1%}",
                            f"{m.routing_accuracy:.1%}",
                            f"{m.json_valid_rate:.1%}",
                            f"{m.schema_pass_rate:.1%}",
                            f"{m.retry_rate:.1%}",
                            f"{m.p50_latency_ms:.0f}",
                            f"{m.p95_latency_ms:.0f}",
                            tps,
                            f"{m.successful_tickets}/{m.total_tickets}",
                        ]
                    )
                except ValueError:
                    logger.warning("Could not summarize run %s", run_id)

        return desc_text, table_rows

    gr.Markdown("## Experiment Comparison")

    initial_choices = _get_experiment_choices()

    experiment_selector = gr.Dropdown(
        choices=initial_choices,
        value=initial_choices[0] if initial_choices else None,
        label="Select Experiment",
    )

    refresh_btn = gr.Button("Refresh")

    experiment_desc = gr.Markdown(
        value="Select an experiment to view comparison."
        if initial_choices
        else "No experiment runs found. Run experiments to see results here."
    )

    experiment_table = gr.Dataframe(
        headers=BENCHMARK_HEADERS,
        interactive=False,
    )

    def on_select(experiment_name):
        desc, rows = _load_experiment(experiment_name)
        is_adversarial = experiment_name and experiment_name.startswith("Adversarial")
        headers = ADVERSARIAL_HEADERS if is_adversarial else BENCHMARK_HEADERS
        return desc, gr.update(value=rows, headers=headers)

    experiment_selector.change(
        fn=on_select,
        inputs=[experiment_selector],
        outputs=[experiment_desc, experiment_table],
    )

    def on_refresh():
        choices = _get_experiment_choices()
        return gr.update(
            choices=choices,
            value=choices[0] if choices else None,
        )

    refresh_btn.click(fn=on_refresh, outputs=[experiment_selector])
