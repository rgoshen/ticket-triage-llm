"""Phase 3 replication: run E1, E3, E2 five times for reproducibility baselines.

Configuration:
    - Sampling: temperature=0.2, top_p=0.9, top_k=40, rep_penalty=1.0, think=false
    - Models: qwen3.5:2b, qwen3.5:4b, qwen3.5:9b
    - Dataset: data/normal_set.jsonl (35 tickets)
    - Output: data/phase3-1/run-N/ (N=1..5), each with 3 JSON files

Per-run triage counts:
    E1: 3 models × 35 tickets = 105
    E3: 3 models × 2 configs × 35 tickets = 210 (validated + skipped per model)
    Total per run: 315 triages
    Total all runs: 1,575 triages
    Estimated time at ~10s/ticket (think=false): ~4.4 hours
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from ticket_triage_llm.config import Settings
from ticket_triage_llm.eval.datasets import load_dataset
from ticket_triage_llm.eval.runners.run_local_comparison import run_local_comparison
from ticket_triage_llm.eval.runners.run_validation_impact import (
    compose_and_write_e2,
    run_validation_impact,
)
from ticket_triage_llm.providers.ollama_qwen import OllamaQwenProvider
from ticket_triage_llm.services.trace import SqliteTraceRepository
from ticket_triage_llm.storage.db import get_connection, init_schema

logger = logging.getLogger(__name__)

N_RUNS = 5


def run_single_iteration(
    run_number: int,
    end_run: int,
    providers: list[OllamaQwenProvider],
    tickets: list,
    repo: SqliteTraceRepository,
    output_base: Path,
) -> dict:
    """Execute one complete iteration of E1 + E3 + E2."""
    run_dir = output_base / f"run-{run_number}"
    run_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"r{run_number}"
    anomalies: list[str] = []

    logger.info("=" * 60)
    logger.info(
        "RUN %d/%d — suffix=%s, output=%s",
        run_number,
        end_run,
        suffix,
        run_dir,
    )
    logger.info("=" * 60)

    # --- E1: model size comparison ---
    run_start = time.perf_counter()
    logger.info(
        "--- E1: model size comparison (3 models × %d tickets) ---", len(tickets)
    )
    try:
        e1_summary = run_local_comparison(providers, tickets, repo, run_suffix=suffix)
        e1_path = run_dir / "e1-local-comparison.json"
        e1_path.write_text(json.dumps(e1_summary.to_dict(), indent=2))
        e1_elapsed = time.perf_counter() - run_start
        logger.info("E1 complete — %.0fs elapsed, written to %s", e1_elapsed, e1_path)
    except Exception:
        logger.exception("E1 FAILED on run %d", run_number)
        anomalies.append(f"E1 failed on run {run_number}")
        e1_path = None

    # --- E3: validation impact + E2 data point ---
    e3_start = time.perf_counter()
    logger.info(
        "--- E3: validation impact (%d models × 2 configs × %d tickets) ---",
        len(providers),
        len(tickets),
    )
    try:
        e3_summary, e2_run_id = run_validation_impact(
            providers, tickets, repo, run_suffix=suffix
        )
        e3_path = run_dir / "e3-validation-impact.json"
        e3_path.write_text(json.dumps(e3_summary.to_dict(), indent=2))
        e3_elapsed = time.perf_counter() - e3_start
        logger.info("E3 complete — %.0fs elapsed, written to %s", e3_elapsed, e3_path)
    except Exception:
        logger.exception("E3 FAILED on run %d", run_number)
        anomalies.append(f"E3 failed on run {run_number}")
        e2_run_id = None

    # --- E2: composed from E1 + E3 ---
    if e1_path and e1_path.exists() and e2_run_id:
        logger.info("--- E2: composing from E1 + E3 data ---")
        try:
            compose_and_write_e2(e1_path, e2_run_id, tickets, repo, run_dir)
            logger.info("E2 written to %s", run_dir / "e2-size-vs-controls.json")
        except Exception:
            logger.exception("E2 composition FAILED on run %d", run_number)
            anomalies.append(f"E2 composition failed on run {run_number}")
    else:
        logger.warning("E2 skipped — missing E1 results or E2 run_id")
        anomalies.append(f"E2 skipped on run {run_number} (missing prerequisites)")

    total_elapsed = time.perf_counter() - run_start
    logger.info(
        "RUN %d/%d COMPLETE — total %.0fs (%.1f min)",
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
        description="Phase 3 replication: 5 independent runs of E1/E3/E2"
    )
    parser.add_argument("--db-path", default="data/traces.db")
    parser.add_argument("--dataset-path", default="data/normal_set.jsonl")
    parser.add_argument("--output-base", default="data/phase3-1")
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
    logger.info("Dataset: %s", args.dataset_path)
    logger.info("Output base: %s", args.output_base)
    logger.info("Runs: %d through %d", args.start_run, args.end_run)

    providers = [
        OllamaQwenProvider(model=m, base_url=settings.ollama_base_url) for m in models
    ]

    conn = get_connection(args.db_path)
    init_schema(conn)
    repo = SqliteTraceRepository(conn)
    tickets = load_dataset(Path(args.dataset_path))

    logger.info("Loaded %d tickets", len(tickets))

    n_models = len(providers)
    # E1: N models × tickets, E3: N models × 2 configs × tickets
    triages_per_run = len(tickets) * (n_models + n_models * 2)
    total_triages = triages_per_run * (args.end_run - args.start_run + 1)
    est_seconds = total_triages * 10
    logger.info(
        "Estimated: %d triages per run, %d total, ~%.1f hours at ~10s/triage",
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
            tickets=tickets,
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
        "ALL RUNS COMPLETE — %.0fs total (%.1f hours)",
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
            f" — ANOMALIES: {r['anomalies']}" if r["anomalies"] else "",
        )

    if all_anomalies:
        logger.warning("ANOMALIES DETECTED: %s", all_anomalies)
        sys.exit(1)


if __name__ == "__main__":
    main()
