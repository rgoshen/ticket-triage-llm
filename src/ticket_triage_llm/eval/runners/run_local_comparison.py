"""Experiment 1: local model size comparison — Phase 3."""

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


def run_local_comparison(
    providers: list[LlmProvider],
    tickets: list[TicketRecord],
    trace_repo: TraceRepository,
) -> ExperimentSummary:
    """Run all local model sizes through the normal set with prompt v1."""
    timestamp = datetime.now().strftime("%Y%m%dT%H%M")
    metrics = []

    for provider in providers:
        tag = provider.name.split(":")[-1] if ":" in provider.name else provider.name
        run_id = f"e1-{tag}-{timestamp}"
        logger.info("E1: running %s — run_id=%s", provider.name, run_id)
        run_experiment_pass(
            tickets=tickets,
            provider=provider,
            prompt_version="v1",
            trace_repo=trace_repo,
            run_id=run_id,
        )
        model_metrics = summarize_run(run_id, tickets, trace_repo)
        metrics.append(model_metrics)

    return ExperimentSummary(
        experiment_id="E1",
        experiment_name="Model size comparison",
        date=datetime.now().strftime("%Y-%m-%d"),
        dataset_size=len(tickets),
        prompt_version="v1",
        model_metrics=metrics,
    )


if __name__ == "__main__":
    import argparse

    from ticket_triage_llm.config import Settings
    from ticket_triage_llm.providers.ollama_qwen import OllamaQwenProvider
    from ticket_triage_llm.services.trace import SqliteTraceRepository
    from ticket_triage_llm.storage.db import get_connection, init_schema

    parser = argparse.ArgumentParser(description="E1: local model size comparison")
    parser.add_argument("--db-path", default="data/traces.db")
    parser.add_argument("--dataset-path", default="data/normal_set.jsonl")
    parser.add_argument("--output-dir", default="data/phase3")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    settings = Settings()
    models = [m.strip() for m in settings.ollama_models.split(",") if m.strip()]
    if not models:
        models = [settings.ollama_model]

    providers = [
        OllamaQwenProvider(model=m, base_url=settings.ollama_base_url)
        for m in models
    ]

    conn = get_connection(args.db_path)
    init_schema(conn)
    repo = SqliteTraceRepository(conn)
    tickets = load_dataset(Path(args.dataset_path))

    summary = run_local_comparison(providers, tickets, repo)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "e1-local-comparison.json"
    out_path.write_text(json.dumps(summary.to_dict(), indent=2))
    logger.info("E1 results written to %s", out_path)
