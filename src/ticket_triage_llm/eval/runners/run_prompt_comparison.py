"""Experiment 4: prompt v1 vs v2 comparison — Phase 6.

Phase 3 runs v1 only. Re-run after Phase 6 adds triage_v2.py.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from ticket_triage_llm.eval.datasets import TicketRecord, load_dataset
from ticket_triage_llm.eval.results import ExperimentSummary
from ticket_triage_llm.eval.runners.common import run_experiment_pass
from ticket_triage_llm.eval.runners.summarize_results import summarize_run
from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)


def run_prompt_comparison(
    provider: LlmProvider,
    tickets: list[TicketRecord],
    trace_repo: TraceRepository,
    prompt_versions: list[str] | None = None,
) -> ExperimentSummary:
    """Execute prompt comparison experiment.

    Runs the normal set through one model with different prompt versions.
    Phase 3 runs v1 only (v2 doesn't exist yet — that's Phase 6).

    Args:
        provider: LLM provider instance (single model)
        tickets: List of tickets with ground truth
        trace_repo: Trace repository for persistence
        prompt_versions: List of prompt versions to compare (default: ["v1"])

    Returns:
        ExperimentSummary with metrics for each prompt version
    """
    if prompt_versions is None:
        prompt_versions = ["v1"]

    timestamp = datetime.now().strftime("%Y%m%dT%H%M")
    metrics = []

    for version in prompt_versions:
        run_id = f"e4-{version}-{timestamp}"
        logger.info("E4: prompt %s — run_id=%s", version, run_id)
        run_experiment_pass(
            tickets=tickets,
            provider=provider,
            prompt_version=version,
            trace_repo=trace_repo,
            run_id=run_id,
        )
        model_metrics = summarize_run(run_id, tickets, trace_repo)
        metrics.append(model_metrics)

    return ExperimentSummary(
        experiment_id="E4",
        experiment_name="Prompt comparison",
        date=datetime.now().strftime("%Y-%m-%d"),
        dataset_size=len(tickets),
        prompt_version=",".join(prompt_versions),
        model_metrics=metrics,
    )


if __name__ == "__main__":
    import argparse

    from ticket_triage_llm.config import Settings
    from ticket_triage_llm.providers.ollama_qwen import OllamaQwenProvider
    from ticket_triage_llm.services.trace import SqliteTraceRepository
    from ticket_triage_llm.storage.db import get_connection, init_schema

    parser = argparse.ArgumentParser(description="E4: prompt comparison")
    parser.add_argument("--db-path", default="data/traces.db")
    parser.add_argument("--dataset-path", default="data/normal_set.jsonl")
    parser.add_argument("--output-dir", default="data/phase3")
    parser.add_argument(
        "--prompt-versions", default="v1",
        help="Comma-separated prompt versions (e.g., 'v1,v2')",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    settings = Settings()
    provider = OllamaQwenProvider(
        model=settings.ollama_model, base_url=settings.ollama_base_url
    )

    conn = get_connection(args.db_path)
    init_schema(conn)
    repo = SqliteTraceRepository(conn)
    tickets = load_dataset(Path(args.dataset_path))
    versions = [v.strip() for v in args.prompt_versions.split(",")]

    summary = run_prompt_comparison(provider, tickets, repo, prompt_versions=versions)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "e4-prompt-comparison.json"
    out_path.write_text(json.dumps(summary.to_dict(), indent=2))
    logger.info("E4 results written to %s", out_path)
