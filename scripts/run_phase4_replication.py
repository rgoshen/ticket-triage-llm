"""Phase 4 replication: run adversarial evaluation five times for reproducibility.

Configuration:
    - Sampling: temperature=0.2, top_p=0.9, top_k=40, rep_penalty=1.0, think=false
    - Models: qwen3.5:2b, qwen3.5:4b, qwen3.5:9b
    - Dataset: data/adversarial_set.jsonl + data/normal_set.jsonl (FP baseline)
    - Output: data/phase4-1/run-N/ (N=1..5), one JSON per model per run

Per-run triage counts:
    Adversarial pass: 3 models x N_adv tickets
    FP baseline: computed in-process against normal_set (no triage calls)
    Estimated time at ~10s/ticket (think=false, typical adversarial set ~15-25 tickets):
        roughly 45-75 minutes per run, 4-6 hours total.

Mirrors the structure/conventions of scripts/run_phase3_replication.py so that
Phase 4 replication artifacts line up with Phase 3 for cross-phase analysis.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from ticket_triage_llm.config import Settings
from ticket_triage_llm.eval.datasets import (
    load_adversarial_dataset,
    load_dataset,
)
from ticket_triage_llm.eval.runners.run_adversarial_eval import run_adversarial_eval
from ticket_triage_llm.providers.ollama_qwen import OllamaQwenProvider
from ticket_triage_llm.services.trace import SqliteTraceRepository
from ticket_triage_llm.storage.db import get_connection, init_schema

logger = logging.getLogger(__name__)

N_RUNS = 5


def run_single_iteration(
    run_number: int,
    end_run: int,
    providers: list[OllamaQwenProvider],
    adv_tickets: list,
    normal_tickets: list,
    repo: SqliteTraceRepository,
    output_base: Path,
) -> dict:
    """Execute one complete adversarial evaluation pass across all providers."""
    run_dir = output_base / f"run-{run_number}"
    run_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"r{run_number}"
    anomalies: list[str] = []

    logger.info("=" * 60)
    logger.info(
        "RUN %d/%d - suffix=%s, output=%s",
        run_number,
        end_run,
        suffix,
        run_dir,
    )
    logger.info("=" * 60)

    run_start = time.perf_counter()
    logger.info(
        "Adversarial: %d models x %d adversarial tickets (FP baseline on %d normal)",
        len(providers),
        len(adv_tickets),
        len(normal_tickets),
    )

    try:
        summaries = run_adversarial_eval(
            providers=providers,
            adv_tickets=adv_tickets,
            normal_tickets=normal_tickets,
            trace_repo=repo,
            run_suffix=suffix,
        )
    except Exception:
        logger.exception("Adversarial run FAILED on run %d", run_number)
        anomalies.append(f"Adversarial run failed on run {run_number}")
        return {
            "run_number": run_number,
            "elapsed_seconds": round(time.perf_counter() - run_start, 1),
            "anomalies": anomalies,
        }

    for s in summaries:
        tag = s.model.split(":")[-1] if ":" in s.model else s.model
        out_path = run_dir / f"adversarial-{tag}.json"
        out_path.write_text(json.dumps(s.to_dict(), indent=2))
        logger.info("Wrote %s", out_path)
        if s.run_status != "complete":
            anomalies.append(f"Run {run_number} model {s.model}: status={s.run_status}")

    total_elapsed = time.perf_counter() - run_start
    logger.info(
        "RUN %d/%d COMPLETE - %.0fs (%.1f min)",
        run_number,
        end_run,
        total_elapsed,
        total_elapsed / 60,
    )

    return {
        "run_number": run_number,
        "elapsed_seconds": round(total_elapsed, 1),
        "anomalies": anomalies,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 4 replication: 5 independent adversarial runs"
    )
    parser.add_argument("--db-path", default="data/traces.db")
    parser.add_argument("--adversarial-path", default="data/adversarial_set.jsonl")
    parser.add_argument("--normal-path", default="data/normal_set.jsonl")
    parser.add_argument("--output-base", default="data/phase4-1")
    parser.add_argument(
        "--start-run",
        type=int,
        default=1,
        help="First run number (for resuming after partial failure)",
    )
    parser.add_argument(
        "--end-run",
        type=int,
        default=N_RUNS,
        help="Last run number (inclusive)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing run directories without prompting",
    )
    args = parser.parse_args()

    if args.start_run < 1 or args.end_run < args.start_run:
        print(
            f"Invalid run range: start={args.start_run}, end={args.end_run}. "
            "Requires 1 <= start <= end.",
            file=sys.stderr,
        )
        sys.exit(2)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    output_base = Path(args.output_base)
    existing_runs = []
    for run_num in range(args.start_run, args.end_run + 1):
        run_dir = output_base / f"run-{run_num}"
        if run_dir.exists() and any(run_dir.iterdir()):
            existing_runs.append(run_num)
    if existing_runs and not args.force:
        if not sys.stdin.isatty():
            logger.error(
                "Existing data for runs %s would be overwritten. "
                "Use --force in non-interactive mode.",
                existing_runs,
            )
            sys.exit(2)
        logger.warning(
            "Existing data found for runs: %s. These will be overwritten.",
            existing_runs,
        )
        answer = input("Continue? [y/N] ").strip().lower()
        if answer != "y":
            logger.info("Aborted by user.")
            sys.exit(0)

    settings = Settings()
    models = [m.strip() for m in settings.ollama_models.split(",") if m.strip()]
    if not models:
        models = [settings.ollama_model]

    logger.info("Models: %s", models)
    logger.info("Adversarial dataset: %s", args.adversarial_path)
    logger.info("Normal dataset (FP baseline): %s", args.normal_path)
    logger.info("Output base: %s", args.output_base)
    logger.info("Runs: %d through %d", args.start_run, args.end_run)

    providers = [
        OllamaQwenProvider(model=m, base_url=settings.ollama_base_url) for m in models
    ]

    conn = get_connection(args.db_path)
    init_schema(conn)
    repo = SqliteTraceRepository(conn)

    adv_tickets = load_adversarial_dataset(Path(args.adversarial_path))
    normal_tickets = load_dataset(Path(args.normal_path))

    logger.info(
        "Loaded %d adversarial tickets, %d normal tickets",
        len(adv_tickets),
        len(normal_tickets),
    )

    n_models = len(providers)
    triages_per_run = len(adv_tickets) * n_models
    total_triages = triages_per_run * (args.end_run - args.start_run + 1)
    est_seconds = total_triages * 10
    logger.info(
        "Estimated: %d adv triages per run, %d total, ~%.1f hours at ~10s/triage",
        triages_per_run,
        total_triages,
        est_seconds / 3600,
    )

    overall_start = time.perf_counter()
    run_results: list[dict] = []

    for run_num in range(args.start_run, args.end_run + 1):
        result = run_single_iteration(
            run_number=run_num,
            end_run=args.end_run,
            providers=providers,
            adv_tickets=adv_tickets,
            normal_tickets=normal_tickets,
            repo=repo,
            output_base=output_base,
        )
        run_results.append(result)

        remaining = args.end_run - run_num
        if remaining > 0:
            avg_so_far = (time.perf_counter() - overall_start) / (
                run_num - args.start_run + 1
            )
            logger.info(
                "--- %d runs remaining, estimated %.1f hours left ---",
                remaining,
                (remaining * avg_so_far) / 3600,
            )

    overall_elapsed = time.perf_counter() - overall_start
    logger.info("=" * 60)
    logger.info(
        "ALL RUNS COMPLETE - %.0fs total (%.1f hours)",
        overall_elapsed,
        overall_elapsed / 3600,
    )

    all_anomalies = []
    for r in run_results:
        if r["anomalies"]:
            all_anomalies.extend(r["anomalies"])
        logger.info(
            "  Run %d: %.0fs%s",
            r["run_number"],
            r["elapsed_seconds"],
            f" - ANOMALIES: {r['anomalies']}" if r["anomalies"] else "",
        )

    if all_anomalies:
        logger.warning("ANOMALIES DETECTED: %s", all_anomalies)
        sys.exit(1)


if __name__ == "__main__":
    main()
