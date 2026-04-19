"""Aggregate Phase 4 replication runs into mean/stddev summary.

Reads data/phase4-1/run-N/adversarial-{tag}.json for N=1..5 and writes a
single aggregated JSON to data/phase4-1/analysis/adv-aggregate.json with:

    - Per-model totals: mean +/- stddev for guardrail_blocked,
      model_complied, validation_caught, residual_risk, false_positive_rate
    - Per-model per-category compliance rates: mean +/- stddev of
      complied / ticket_count for each attack_category
    - Parse-failure counts per model, aggregated from compliance checks
      with complied=null + evidence mentioning parse_failure
    - Per-ticket outcome consistency: for each (ticket_id, model) pair,
      whether the verdict was identical across all 5 runs
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_TAGS = ("2b", "4b", "9b")


def _mean_stddev(values: list[float]) -> dict:
    if not values:
        return {"mean": None, "stddev": None, "n": 0}
    return {
        "mean": round(statistics.fmean(values), 4),
        "stddev": round(statistics.pstdev(values), 4) if len(values) > 1 else 0.0,
        "n": len(values),
    }


def load_run(phase4_base: Path, run_num: int, tag: str) -> dict | None:
    path = phase4_base / f"run-{run_num}" / f"adversarial-{tag}.json"
    if not path.exists():
        logger.warning("Missing %s", path)
        return None
    return json.loads(path.read_text())


def aggregate_model(runs: list[dict]) -> dict:
    """Aggregate per-model metrics across runs."""
    if not runs:
        return {}

    totals_fields = (
        "guardrail_blocked",
        "guardrail_warned",
        "reached_model",
        "model_complied",
        "validation_caught",
        "residual_risk",
    )
    totals_values: dict[str, list[int]] = {f: [] for f in totals_fields}
    ticket_count = runs[0]["totals"]["ticket_count"]

    fp_rates: list[float] = []
    needs_review_counts: list[int] = []
    parse_failure_counts: list[int] = []
    complied_true_counts: list[int] = []

    # Per-attack-category: compliance rate (complied=True / ticket_count)
    per_category_complied: dict[str, list[float]] = defaultdict(list)
    per_category_ticket_counts: dict[str, int] = {}

    for r in runs:
        for f in totals_fields:
            totals_values[f].append(r["totals"][f])
        fp_rates.append(r.get("false_positive_rate", 0.0))
        needs_review_counts.append(len(r.get("needs_manual_review", [])))

        # Build per-run per-category counts from compliance_checks
        cat_complied_true: dict[str, int] = defaultdict(int)
        cat_counts: dict[str, int] = defaultdict(int)
        parse_fails = 0
        total_complied_true = 0
        for check in r.get("compliance_checks", []):
            cat = check["attack_category"]
            cat_counts[cat] += 1
            per_category_ticket_counts.setdefault(cat, 0)
            # Tally ticket count once per category; runs share the ticket set
            if per_category_ticket_counts[cat] < cat_counts[cat]:
                per_category_ticket_counts[cat] = cat_counts[cat]
            if check.get("complied") is True:
                cat_complied_true[cat] += 1
                total_complied_true += 1
            if check.get("complied") is None and "parse_failure" in (
                check.get("evidence") or ""
            ):
                parse_fails += 1
        parse_failure_counts.append(parse_fails)
        complied_true_counts.append(total_complied_true)

        for cat, total in cat_counts.items():
            rate = cat_complied_true[cat] / total if total else 0.0
            per_category_complied[cat].append(rate)

    return {
        "model": runs[0]["model"],
        "n_runs": len(runs),
        "ticket_count": ticket_count,
        "totals": {f: _mean_stddev(totals_values[f]) for f in totals_fields},
        "false_positive_rate": _mean_stddev(fp_rates),
        "needs_manual_review": _mean_stddev(needs_review_counts),
        "parse_failure_count": _mean_stddev(parse_failure_counts),
        "model_complied_count": _mean_stddev(complied_true_counts),
        "per_category_compliance_rate": {
            cat: {
                **_mean_stddev(rates),
                "ticket_count": per_category_ticket_counts.get(cat, 0),
            }
            for cat, rates in per_category_complied.items()
        },
    }


def per_ticket_consistency(phase4_base: Path, n_runs: int) -> list[dict]:
    """For each (ticket_id, model), record whether all runs yielded the same
    compliance verdict (True/False/None)."""
    # key: (ticket_id, tag) -> list of verdicts across runs
    verdicts: dict[tuple[str, str], list] = defaultdict(list)
    categories: dict[str, str] = {}
    for run_num in range(1, n_runs + 1):
        for tag in MODEL_TAGS:
            data = load_run(phase4_base, run_num, tag)
            if not data:
                continue
            for check in data.get("compliance_checks", []):
                verdicts[(check["ticket_id"], tag)].append(check.get("complied"))
                categories.setdefault(check["ticket_id"], check["attack_category"])

    rows: list[dict] = []
    for (ticket_id, tag), seq in sorted(verdicts.items()):
        unique = {v for v in seq}
        rows.append(
            {
                "ticket_id": ticket_id,
                "attack_category": categories.get(ticket_id, ""),
                "model": tag,
                "verdicts": [
                    "complied"
                    if v is True
                    else ("resisted" if v is False else "inconclusive")
                    for v in seq
                ],
                "consistent": len(unique) == 1,
                "n_runs": len(seq),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate Phase 4 replication runs into mean/stddev summary"
    )
    parser.add_argument("--phase4-base", default="data/phase4-1")
    parser.add_argument("--n-runs", type=int, default=5)
    parser.add_argument(
        "--output-path",
        default="data/phase4-1/analysis/adv-aggregate.json",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    phase4_base = Path(args.phase4_base)
    if not phase4_base.exists():
        logger.error("Phase 4 base not found: %s", phase4_base)
        sys.exit(2)

    output: dict = {
        "phase4_base": str(phase4_base),
        "n_runs": args.n_runs,
        "per_model": {},
    }

    for tag in MODEL_TAGS:
        runs = []
        for run_num in range(1, args.n_runs + 1):
            data = load_run(phase4_base, run_num, tag)
            if data:
                runs.append(data)
        if not runs:
            logger.warning("No runs found for %s", tag)
            continue
        logger.info("Aggregating %s across %d runs", tag, len(runs))
        output["per_model"][tag] = aggregate_model(runs)

    logger.info("Computing per-ticket consistency")
    output["per_ticket_consistency"] = per_ticket_consistency(phase4_base, args.n_runs)

    inconsistent = [r for r in output["per_ticket_consistency"] if not r["consistent"]]
    output["inconsistent_count"] = len(inconsistent)

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))
    logger.info("Wrote %s", output_path)
    logger.info(
        "Inconsistent (ticket, model) pairs: %d / %d",
        len(inconsistent),
        len(output["per_ticket_consistency"]),
    )
    for r in inconsistent:
        logger.info("  %s / %s: %s", r["ticket_id"], r["model"], r["verdicts"])


if __name__ == "__main__":
    main()
