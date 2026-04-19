"""Build per-adversarial-ticket x per-model matrix across Phase 4 replication runs.

Reads the trace DB plus the per-run JSON result files under data/phase4-1/run-N/
and produces a CSV showing, for each (ticket_id, model) pair across 5 runs:

    guardrail_blocked / guardrail_warned / success / parse_failure / complied_true
    plus per-run outcome consistency.

Output: data/phase4-1/analysis/adv-per-ticket-matrix.csv

Usage:
    uv run python scripts/analysis/build_adv_per_ticket_matrix.py
        [--db-path data/traces.db]
        [--phase4-base data/phase4-1]
        [--n-runs 5]
        [--output-path data/phase4-1/analysis/adv-per-ticket-matrix.csv]
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_TAGS = ("2b", "4b", "9b")


def _short_tag(model_name: str) -> str:
    """Map 'ollama:qwen3.5:4b' or 'qwen3.5:4b' -> '4b'."""
    return model_name.split(":")[-1]


def load_compliance_from_runs(
    phase4_base: Path, n_runs: int
) -> dict[tuple[str, str, int], dict]:
    """Load (ticket_id, model_tag, run_number) -> compliance-check dict.

    Uses the per-run adversarial-{tag}.json files rather than the DB because
    the JSON contains the already-computed `complied` verdict and evidence.
    """
    by_key: dict[tuple[str, str, int], dict] = {}
    for run_num in range(1, n_runs + 1):
        for tag in MODEL_TAGS:
            path = phase4_base / f"run-{run_num}" / f"adversarial-{tag}.json"
            if not path.exists():
                logger.warning("Missing expected file: %s", path)
                continue
            data = json.loads(path.read_text())
            for check in data.get("compliance_checks", []):
                by_key[(check["ticket_id"], tag, run_num)] = check
    return by_key


def load_trace_outcomes(db_path: Path, n_runs: int) -> dict[tuple[str, str, int], dict]:
    """Load per-request trace outcomes keyed by (ticket_id, model_tag, run_number).

    Run number is parsed out of the run_id suffix `-rN`. Adversarial run_ids
    produced by run_adversarial_eval follow `adv-{tag}-{ts}-r{N}`; anything
    that does not match that shape is ignored.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            """
            SELECT ticket_id, model, run_id, status, failure_category,
                   guardrail_result, retry_count
            FROM traces
            WHERE run_id LIKE 'adv-%' AND run_id LIKE '%-r_'
            """
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    out: dict[tuple[str, str, int], dict] = {}
    for ticket_id, model, run_id, status, failure_cat, guardrail, retry in rows:
        # run_id: adv-{tag}-{timestamp}-r{N}
        try:
            run_num = int(run_id.rsplit("-r", 1)[1])
        except (IndexError, ValueError):
            continue
        if run_num < 1 or run_num > n_runs:
            continue
        tag = _short_tag(model)
        key = (ticket_id, tag, run_num)
        # If duplicate rows exist for the same key (shouldn't happen in a
        # single replication sweep), keep the latest.
        out[key] = {
            "status": status,
            "failure_category": failure_cat,
            "guardrail_result": guardrail,
            "retry_count": retry,
        }
    return out


def classify_outcome(trace: dict | None, compliance: dict | None) -> str:
    """Collapse a per-run outcome into a single-letter bucket.

    Buckets:
        B - guardrail blocked (trace.guardrail_result == 'block')
        C - model complied with the attack (compliance.complied is True)
        R - model resisted (compliance.complied is False)
        P - parse/schema failure (status == 'failure', not guardrail-blocked)
        U - model unreachable or other failure
        ? - unknown / missing data
    """
    if trace is None:
        return "?"
    if trace.get("guardrail_result") == "block":
        return "B"
    if trace.get("status") == "failure":
        fc = trace.get("failure_category") or ""
        if fc in ("parse_failure", "schema_failure", "semantic_failure"):
            return "P"
        if fc == "model_unreachable":
            return "U"
        if fc == "guardrail_blocked":
            return "B"
        return "U"
    # status == success — use compliance verdict
    if compliance is None:
        return "?"
    if compliance.get("complied") is True:
        return "C"
    if compliance.get("complied") is False:
        return "R"
    return "?"


def build_matrix(
    traces_by_key: dict[tuple[str, str, int], dict],
    compliance_by_key: dict[tuple[str, str, int], dict],
    n_runs: int,
) -> list[dict]:
    """Aggregate per-(ticket, model) counts across all runs."""
    ticket_categories: dict[str, str] = {}
    for (ticket_id, _tag, _run), check in compliance_by_key.items():
        ticket_categories.setdefault(ticket_id, check.get("attack_category", ""))

    keys_seen: set[tuple[str, str]] = set()
    for ticket_id, tag, _run in compliance_by_key:
        keys_seen.add((ticket_id, tag))
    for ticket_id, tag, _run in traces_by_key:
        keys_seen.add((ticket_id, tag))

    rows: list[dict] = []
    for ticket_id, tag in sorted(keys_seen):
        counts = defaultdict(int)
        per_run_outcomes: list[str] = []
        for run_num in range(1, n_runs + 1):
            trace = traces_by_key.get((ticket_id, tag, run_num))
            compliance = compliance_by_key.get((ticket_id, tag, run_num))
            bucket = classify_outcome(trace, compliance)
            counts[bucket] += 1
            per_run_outcomes.append(bucket)

        rows.append(
            {
                "ticket_id": ticket_id,
                "attack_category": ticket_categories.get(ticket_id, ""),
                "model": tag,
                "blocked_n": counts["B"],
                "complied_n": counts["C"],
                "resisted_n": counts["R"],
                "parse_failure_n": counts["P"],
                "unreachable_n": counts["U"],
                "unknown_n": counts["?"],
                "total_runs": n_runs,
                "per_run_sequence": "".join(per_run_outcomes),
                "consistent": len(set(per_run_outcomes)) == 1,
            }
        )
    return rows


def write_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "ticket_id",
        "attack_category",
        "model",
        "blocked_n",
        "complied_n",
        "resisted_n",
        "parse_failure_n",
        "unreachable_n",
        "unknown_n",
        "total_runs",
        "per_run_sequence",
        "consistent",
    ]
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build per-adversarial-ticket matrix across replication runs"
    )
    parser.add_argument("--db-path", default="data/traces.db")
    parser.add_argument("--phase4-base", default="data/phase4-1")
    parser.add_argument("--n-runs", type=int, default=5)
    parser.add_argument(
        "--output-path",
        default="data/phase4-1/analysis/adv-per-ticket-matrix.csv",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    db_path = Path(args.db_path)
    phase4_base = Path(args.phase4_base)
    output_path = Path(args.output_path)

    if not db_path.exists():
        logger.error("Trace DB not found: %s", db_path)
        sys.exit(2)
    if not phase4_base.exists():
        logger.error("Phase 4 replication base not found: %s", phase4_base)
        sys.exit(2)

    logger.info("Loading traces from %s", db_path)
    traces_by_key = load_trace_outcomes(db_path, args.n_runs)
    logger.info("Loaded %d trace rows", len(traces_by_key))

    logger.info("Loading compliance checks from %s", phase4_base)
    compliance_by_key = load_compliance_from_runs(phase4_base, args.n_runs)
    logger.info("Loaded %d compliance rows", len(compliance_by_key))

    rows = build_matrix(traces_by_key, compliance_by_key, args.n_runs)
    logger.info("Built matrix with %d rows", len(rows))

    write_csv(rows, output_path)
    logger.info("Wrote %s", output_path)

    inconsistent = [r for r in rows if not r["consistent"]]
    if inconsistent:
        logger.info(
            "Inconsistent (ticket, model) pairs (%d):",
            len(inconsistent),
        )
        for r in inconsistent:
            logger.info(
                "  %s / %s: sequence=%s",
                r["ticket_id"],
                r["model"],
                r["per_run_sequence"],
            )


if __name__ == "__main__":
    main()
