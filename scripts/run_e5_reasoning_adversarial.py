"""E5: reasoning mode on the adversarial set - 9B only, think=off vs think=on.

Scope (stated up front so results are judged against a fixed question):
    - Model: qwen3.5:9b only (production decision per OD-4 resolution)
    - Dataset: data/adversarial_set.jsonl only (no normal_set - accuracy is
      secondary; the adversarial question is what affects the production-config
      decision about thinking mode)
    - Conditions: think=False (baseline, matches Phase 4 replication) and
      think=True
    - Replications: 3 per condition (lower than Phase 4's n=5 - adversarial
      behavior on the 9B is highly deterministic, and n=3 is sufficient to
      distinguish signal from noise)

Configuration (locked, do not deviate):
    - Sampling: temperature=0.2, top_p=0.9, top_k=40, rep_penalty=1.0
    - num_ctx=16384 (production value)
    - prompt v1, full validation pipeline

Decision criteria (stated before running, to prevent post-hoc rationalization):
    Thinking-on is worth considering as a production default only if BOTH:
      (a) it closes a-009 at stddev=0 across all 3 runs, AND
      (b) it does not introduce any new adversarial compliance on
          previously-resisted tickets.
    Otherwise, thinking stays off and the experiment is a documented finding,
    not a configuration change.
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
from ticket_triage_llm.eval.runners.run_adversarial_eval import (
    run_adversarial_eval as run_adv_suite,
)
from ticket_triage_llm.providers.ollama_qwen import OllamaQwenProvider
from ticket_triage_llm.services.trace import SqliteTraceRepository
from ticket_triage_llm.storage.db import get_connection, init_schema

logger = logging.getLogger(__name__)

MODEL = "qwen3.5:9b"
N_RUNS = 3
CONDITIONS = [
    ("think-off", False),
    ("think-on", True),
]


def run_single_condition(
    run_number: int,
    condition_label: str,
    think_flag: bool,
    base_url: str,
    adv_tickets: list,
    normal_tickets: list,
    repo: SqliteTraceRepository,
    run_dir: Path,
) -> list[str]:
    """Execute one (run, condition) pass - one provider, one adversarial sweep."""
    suffix = f"r{run_number}-{condition_label}"
    anomalies: list[str] = []

    logger.info("-" * 60)
    logger.info(
        "RUN %d / condition=%s (think=%s) / suffix=%s",
        run_number,
        condition_label,
        think_flag,
        suffix,
    )
    logger.info("-" * 60)

    start = time.perf_counter()

    provider = OllamaQwenProvider(model=MODEL, base_url=base_url, think=think_flag)

    try:
        summaries = run_adv_suite(
            providers=[provider],
            adv_tickets=adv_tickets,
            normal_tickets=normal_tickets,
            trace_repo=repo,
            run_suffix=suffix,
        )
    except Exception:
        logger.exception("Run %d %s FAILED", run_number, condition_label)
        anomalies.append(f"Run {run_number} {condition_label}: exception raised")
        return anomalies

    if not summaries:
        anomalies.append(f"Run {run_number} {condition_label}: no summary produced")
        return anomalies

    summary = summaries[0]
    tag = summary.model.split(":")[-1] if ":" in summary.model else summary.model
    out_path = run_dir / f"adversarial-{tag}-{condition_label}.json"
    out_path.write_text(json.dumps(summary.to_dict(), indent=2))
    logger.info("Wrote %s", out_path)

    if summary.run_status != "complete":
        anomalies.append(
            f"Run {run_number} {condition_label}: status={summary.run_status}"
        )

    elapsed = time.perf_counter() - start
    logger.info(
        "RUN %d %s: residual_risk=%d, elapsed=%.0fs",
        run_number,
        condition_label,
        summary.totals.residual_risk,
        elapsed,
    )
    return anomalies


def main() -> None:
    parser = argparse.ArgumentParser(
        description="E5: reasoning mode on adversarial set - 9B only"
    )
    parser.add_argument("--db-path", default="data/traces.db")
    parser.add_argument("--adversarial-path", default="data/adversarial_set.jsonl")
    parser.add_argument("--normal-path", default="data/normal_set.jsonl")
    parser.add_argument("--output-base", default="data/e5-reasoning")
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

    logger.info("=" * 60)
    logger.info("E5: reasoning mode on adversarial set - 9B only")
    logger.info("Model: %s", MODEL)
    logger.info("Adversarial dataset: %s", args.adversarial_path)
    logger.info("Normal dataset (FP baseline): %s", args.normal_path)
    logger.info("Output base: %s", args.output_base)
    logger.info("Runs: %d through %d", args.start_run, args.end_run)
    logger.info("Conditions: %s", [c[0] for c in CONDITIONS])
    logger.info("=" * 60)

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

    n_conditions = len(CONDITIONS)
    triages_per_run = len(adv_tickets) * n_conditions
    logger.info(
        "Estimated: %d triages per run (think-on pass ~2-3x slower than think-off)",
        triages_per_run,
    )

    overall_start = time.perf_counter()
    all_anomalies: list[str] = []

    for run_num in range(args.start_run, args.end_run + 1):
        run_dir = output_base / f"run-{run_num}"
        run_dir.mkdir(parents=True, exist_ok=True)

        logger.info("=" * 60)
        logger.info("RUN %d/%d", run_num, args.end_run)
        logger.info("=" * 60)

        run_start = time.perf_counter()

        for condition_label, think_flag in CONDITIONS:
            anomalies = run_single_condition(
                run_number=run_num,
                condition_label=condition_label,
                think_flag=think_flag,
                base_url=settings.ollama_base_url,
                adv_tickets=adv_tickets,
                normal_tickets=normal_tickets,
                repo=repo,
                run_dir=run_dir,
            )
            all_anomalies.extend(anomalies)

        run_elapsed = time.perf_counter() - run_start
        logger.info(
            "RUN %d COMPLETE - %.0fs (%.1f min)",
            run_num,
            run_elapsed,
            run_elapsed / 60,
        )

    overall_elapsed = time.perf_counter() - overall_start
    logger.info("=" * 60)
    logger.info(
        "ALL RUNS COMPLETE - %.0fs total (%.1f min)",
        overall_elapsed,
        overall_elapsed / 60,
    )

    if all_anomalies:
        logger.warning("ANOMALIES DETECTED:")
        for a in all_anomalies:
            logger.warning("  %s", a)
        sys.exit(1)


if __name__ == "__main__":
    main()
