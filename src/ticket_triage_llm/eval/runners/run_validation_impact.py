"""Experiment 3: validation on/off impact — Phase 3."""

import json
import logging
from datetime import datetime
from pathlib import Path

from ticket_triage_llm.eval.datasets import TicketRecord, load_dataset
from ticket_triage_llm.eval.results import ExperimentSummary
from ticket_triage_llm.eval.runners.common import run_experiment_pass
from ticket_triage_llm.eval.runners.summarize_results import compose_e2, summarize_run
from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)


def run_validation_impact(
    provider_4b: LlmProvider,
    provider_9b: LlmProvider,
    tickets: list[TicketRecord],
    trace_repo: TraceRepository,
) -> tuple[ExperimentSummary, str]:
    """Run E3 (validation impact) and E2 data point (9B no-validation).

    Args:
        provider_4b: 4B model provider
        provider_9b: 9B model provider
        tickets: Normal dataset tickets
        trace_repo: Trace repository for storing results

    Returns:
        Tuple of (E3 ExperimentSummary, E2 9B no-validation run_id)
    """
    timestamp = datetime.now().strftime("%Y%m%dT%H%M")

    run_id_validated = f"e3-4b-validated-{timestamp}"
    logger.info("E3: 4B validated — run_id=%s", run_id_validated)
    run_experiment_pass(
        tickets=tickets,
        provider=provider_4b,
        prompt_version="v1",
        trace_repo=trace_repo,
        run_id=run_id_validated,
        skip_validation=False,
    )

    run_id_skipped = f"e3-4b-skipped-{timestamp}"
    logger.info("E3: 4B no-validation — run_id=%s", run_id_skipped)
    run_experiment_pass(
        tickets=tickets,
        provider=provider_4b,
        prompt_version="v1",
        trace_repo=trace_repo,
        run_id=run_id_skipped,
        skip_validation=True,
    )

    e2_run_id = f"e2-9b-noval-{timestamp}"
    logger.info("E2 data point: 9B no-validation — run_id=%s", e2_run_id)
    run_experiment_pass(
        tickets=tickets,
        provider=provider_9b,
        prompt_version="v1",
        trace_repo=trace_repo,
        run_id=e2_run_id,
        skip_validation=True,
    )

    validated_metrics = summarize_run(run_id_validated, tickets, trace_repo)
    skipped_metrics = summarize_run(run_id_skipped, tickets, trace_repo)

    summary = ExperimentSummary(
        experiment_id="E3",
        experiment_name="Validation impact",
        date=datetime.now().strftime("%Y-%m-%d"),
        dataset_size=len(tickets),
        prompt_version="v1",
        model_metrics=[validated_metrics, skipped_metrics],
    )
    return summary, e2_run_id


if __name__ == "__main__":
    import argparse

    from ticket_triage_llm.config import Settings
    from ticket_triage_llm.providers.ollama_qwen import OllamaQwenProvider
    from ticket_triage_llm.services.trace import SqliteTraceRepository
    from ticket_triage_llm.storage.db import get_connection, init_schema

    parser = argparse.ArgumentParser(description="E3: validation impact")
    parser.add_argument("--db-path", default="data/traces.db")
    parser.add_argument("--dataset-path", default="data/normal_set.jsonl")
    parser.add_argument("--output-dir", default="data/phase3")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    settings = Settings()
    provider_4b = OllamaQwenProvider(
        model="qwen3.5:4b", base_url=settings.ollama_base_url
    )
    provider_9b = OllamaQwenProvider(
        model="qwen3.5:9b", base_url=settings.ollama_base_url
    )

    conn = get_connection(args.db_path)
    init_schema(conn)
    repo = SqliteTraceRepository(conn)
    tickets = load_dataset(Path(args.dataset_path))

    summary, e2_run_id = run_validation_impact(provider_4b, provider_9b, tickets, repo)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "e3-validation-impact.json"
    out_path.write_text(json.dumps(summary.to_dict(), indent=2))
    logger.info("E3 results written to %s", out_path)

    e1_path = out_dir / "e1-local-comparison.json"
    if e1_path.exists():
        from ticket_triage_llm.eval.results import ExperimentSummary, ModelMetrics

        e1_data = json.loads(e1_path.read_text())
        e1_summary = ExperimentSummary(
            experiment_id=e1_data["experiment_id"],
            experiment_name=e1_data["experiment_name"],
            date=e1_data["date"],
            dataset_size=e1_data["dataset_size"],
            prompt_version=e1_data["prompt_version"],
            model_metrics=[ModelMetrics(**m) for m in e1_data["model_metrics"]],
        )
        e2_summary = compose_e2(e1_summary, e2_run_id, tickets, repo)
        e2_path = out_dir / "e2-size-vs-controls.json"
        e2_path.write_text(json.dumps(e2_summary.to_dict(), indent=2))
        logger.info("E2 results written to %s", e2_path)
    else:
        logger.info(
            "E1 results not found at %s — run E1 first, then re-run E3"
            " to generate E2, or use summarize_results --run-id %s",
            e1_path,
            e2_run_id,
        )
