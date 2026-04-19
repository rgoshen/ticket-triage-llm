"""Experiment 3: validation on/off impact — Phase 3."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from ticket_triage_llm.eval.datasets import TicketRecord, load_dataset
from ticket_triage_llm.eval.results import ExperimentSummary, ModelMetrics
from ticket_triage_llm.eval.runners.common import run_experiment_pass
from ticket_triage_llm.eval.runners.summarize_results import compose_e2, summarize_run
from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)


def _model_tag(provider: LlmProvider) -> str:
    name = provider.name
    return name.split(":")[-1] if ":" in name else name


def run_validation_impact(
    providers: list[LlmProvider],
    tickets: list[TicketRecord],
    trace_repo: TraceRepository,
    run_suffix: str = "",
) -> tuple[ExperimentSummary, str]:
    """Run E3 (validation impact) for all providers and E2 data point.

    Each provider gets a validated and a skipped (no-validation) pass.
    The largest model's skipped run doubles as the E2 data point.

    Args:
        providers: All LLM providers to test
        tickets: Normal dataset tickets
        trace_repo: Trace repository for storing results
        run_suffix: Optional suffix appended to run_ids for replication tracking

    Returns:
        Tuple of (E3 ExperimentSummary, E2 largest-model no-validation run_id)
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M")
    suffix = f"-{run_suffix}" if run_suffix else ""
    metrics = []
    skipped_run_ids: list[tuple[str, str]] = []

    for provider in providers:
        tag = _model_tag(provider)

        run_id_validated = f"e3-{tag}-validated-{timestamp}{suffix}"
        logger.info("E3: %s validated — run_id=%s", tag, run_id_validated)
        run_experiment_pass(
            tickets=tickets,
            provider=provider,
            prompt_version="v1",
            trace_repo=trace_repo,
            run_id=run_id_validated,
            skip_validation=False,
        )

        run_id_skipped = f"e3-{tag}-skipped-{timestamp}{suffix}"
        logger.info("E3: %s no-validation — run_id=%s", tag, run_id_skipped)
        run_experiment_pass(
            tickets=tickets,
            provider=provider,
            prompt_version="v1",
            trace_repo=trace_repo,
            run_id=run_id_skipped,
            skip_validation=True,
        )

        validated_m = summarize_run(run_id_validated, tickets, trace_repo)
        skipped_m = summarize_run(run_id_skipped, tickets, trace_repo)
        metrics.extend([validated_m, skipped_m])
        skipped_run_ids.append((tag, run_id_skipped))

    e2_run_id = _pick_largest_skipped_run_id(skipped_run_ids)

    summary = ExperimentSummary(
        experiment_id="E3",
        experiment_name="Validation impact",
        date=datetime.now(UTC).strftime("%Y-%m-%d"),
        dataset_size=len(tickets),
        prompt_version="v1",
        model_metrics=metrics,
    )
    return summary, e2_run_id


def _pick_largest_skipped_run_id(
    skipped_run_ids: list[tuple[str, str]],
) -> str:
    """Return the skipped run_id for the largest model by parameter count."""
    import re

    def _size(tag: str) -> float:
        match = re.search(r"(\d+(?:\.\d+)?)", tag)
        return float(match.group(1)) if match else 0.0

    return max(skipped_run_ids, key=lambda pair: _size(pair[0]))[1]


def load_e1_summary(e1_path: Path) -> ExperimentSummary | None:
    if not e1_path.exists():
        return None
    e1_data = json.loads(e1_path.read_text())
    return ExperimentSummary(
        experiment_id=e1_data["experiment_id"],
        experiment_name=e1_data["experiment_name"],
        date=e1_data["date"],
        dataset_size=e1_data["dataset_size"],
        prompt_version=e1_data["prompt_version"],
        model_metrics=[ModelMetrics(**m) for m in e1_data["model_metrics"]],
    )


def compose_and_write_e2(
    e1_path: Path,
    e2_run_id: str,
    tickets: list[TicketRecord],
    trace_repo: TraceRepository,
    output_dir: Path,
) -> ExperimentSummary | None:
    e1_summary = load_e1_summary(e1_path)
    if e1_summary is None:
        logger.info(
            "E1 results not found at %s — run E1 first, then re-run E3"
            " to generate E2, or use summarize_results --run-id %s",
            e1_path,
            e2_run_id,
        )
        return None
    e2_summary = compose_e2(e1_summary, e2_run_id, tickets, trace_repo)
    e2_path = output_dir / "e2-size-vs-controls.json"
    e2_path.write_text(json.dumps(e2_summary.to_dict(), indent=2))
    logger.info("E2 results written to %s", e2_path)
    return e2_summary


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
    models = [m.strip() for m in settings.ollama_models.split(",") if m.strip()]
    if not models:
        models = [settings.ollama_model]
    providers = [
        OllamaQwenProvider(model=m, base_url=settings.ollama_base_url) for m in models
    ]

    conn = get_connection(args.db_path)
    init_schema(conn)
    repo = SqliteTraceRepository(conn)
    tickets = load_dataset(Path(args.dataset_path))

    summary, e2_run_id = run_validation_impact(providers, tickets, repo)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "e3-validation-impact.json"
    out_path.write_text(json.dumps(summary.to_dict(), indent=2))
    logger.info("E3 results written to %s", out_path)

    compose_and_write_e2(
        e1_path=out_dir / "e1-local-comparison.json",
        e2_run_id=e2_run_id,
        tickets=tickets,
        trace_repo=repo,
        output_dir=out_dir,
    )
