# SUMMARY

Historical log across all phases of `ticket-triage-llm`. Single file; newest entries at the top. Each phase appends one entry on completion — do not create per-phase SUMMARY files.

Each entry captures:

- **What was done** — the artifact produced or the change made
- **How it was done** — the approach, the tools, the commits/PRs
- **Issues encountered** — real obstacles, not rhetorical ones
- **How those issues were resolved** — the fix, workaround, or deferral

Related artifacts:

- [`TODO.md`](TODO.md) — forward-looking phase plan with dependencies
- [`PLAN.md`](PLAN.md) — overall project build plan (phase numbering differs from `TODO.md`)
- [`docs/decisions/decision-log.md`](docs/decisions/decision-log.md) — scope/framing/strategy decisions with rationale
- [`docs/adr/`](docs/adr/) — architectural decision records
- [`docs/evaluation-checklist.md`](docs/evaluation-checklist.md) — empirical results by phase

---

## [2026-04-16] Phase 0 — Smoke test

**What was done:**

- Verified that the three planned local Qwen 3.5 models (2B, 4B, 9B) can produce structured JSON output for the triage task on the target MacBook Pro M4 Pro / 24 GB machine.
- Made the go/no-go decision on each model: all three retained for the Phase 3 size comparison.
- Filled in the Phase 0 section of `docs/evaluation-checklist.md` with pull verification, MLX acceleration check, per-ticket result tables, aggregate summary, and go/no-go checkboxes.
- Appended the Phase 0 go/no-go entry to `docs/decisions/decision-log.md` with per-model rationale and evidence.
- Established GitFlow branches on the repo: `develop` created from `main` (pushed to origin), and the feature branch `feature/phase-0-smoke-test` cut from `develop`.

**How it was done:**

- Ran `scripts/phase0_smoke_test.py` (pre-existing, shipped in commit `db2e78f`) via `uv run --with openai python scripts/phase0_smoke_test.py`. The script uses the OpenAI client pointed at Ollama's OpenAI-compatible endpoint (`http://localhost:11434/v1`) with the locked sampling configuration (temperature=0.2, top_p=0.9). It sent three normal-set tickets (`n-004` critical outage, `n-007` medium billing, `n-003` low feature request) to each model and scored the responses on JSON validity, field completeness, and category/severity correctness against ground truth.
- Raw model outputs written to `data/phase0/qwen3.5-{2b,4b,9b}-smoke.jsonl`, one JSONL record per ticket per model including the parsed JSON, the raw response, latency, and token usage.
- MLX check performed separately with `OLLAMA_MLX=1 ollama run <model> --verbose` on a throwaway prompt to capture decode-token-rate numbers.
- Results summarized in a new entry at the top of `docs/decisions/decision-log.md` and in the filled-in Phase 0 section of `docs/evaluation-checklist.md`.
- Shipped as PR #1 (`feature/phase-0-smoke-test` → `develop`), merged. A follow-up PR #2 merged `develop` to `main`.

**Issues encountered:**

1. **Missing `qwen3.5:9b` tag.** `ollama list` showed the 9B model was already present locally but tagged as `qwen3.5:latest` (6.6 GB, Q4_K_M, 9.7B params). The smoke-test runner hard-codes the tag `qwen3.5:9b`.
2. **2B reasoning-mode latency tail.** Ticket `n-007` took 652 s on the 2B because the model ran away in thinking mode (3138 completion tokens for a routine billing question) before emitting the final JSON. The JSON was clean — correctness was fine — but the latency is unusable without a bound.
3. **MLX not engaged.** Decode rates under `OLLAMA_MLX=1` were 61.72 / 36.03 / 26.73 tok/s for 2B / 4B / 9B, consistent with the Metal GGML backend rather than MLX kernels.
4. **No `pyproject.toml` / `uv.lock` yet.** Phase 0 predates the Python project scaffolding (which belongs to TODO Phase F — Foundation), so `uv sync` is not yet a thing in this repo. The runner needs `openai` as a dep.

**How those issues were resolved:**

1. Non-destructive local alias: `ollama cp qwen3.5:latest qwen3.5:9b`. No re-download; no runtime effect on the base model; the alias is captured in the decision-log entry and in the Phase 0 checklist so anyone running the script on another machine will know to do the same.
2. Documented as a Phase 1+ risk in the decision-log entry and in `TODO.md` Phase 1. Mitigations are in the design space: a `max_tokens` cap, a wall-clock timeout on the provider, or setting `"think": false` on the Ollama request. Decision on which mitigation to use is deferred to Phase 1 implementation. The 2B was not dropped — it was kept in the lineup specifically to surface this kind of behavior.
3. Treated as an empirical finding, no plan change. `PLAN.md` already framed MLX as "a pleasant possibility, not a planning assumption." The checklist and decision-log entry flag that benchmarks should be rerun if a future Ollama release adds MLX coverage for the `qwen35` architecture.
4. Sidestepped for this phase only: `uv run --with openai` installed `openai` ad-hoc into a throwaway environment without requiring a `pyproject.toml`. Real dependency management is a Foundation-phase deliverable.

**Exit state:**

- All three Qwen 3.5 local models retained. Model lineup for the Phase 3 experiments is locked as **2B / 4B / 9B**.
- `docs/evaluation-checklist.md` Phase 0 section is no longer a template — it reads as a completed record.
- `docs/decisions/decision-log.md` has a dated top entry recording the go/no-go.
- `PLAN.md` Phase 0 is complete. Phase 1 is unblocked, pending Foundation phase per `TODO.md`.
- Working tree on `develop` after merge: clean. `main` fast-forwarded via PR #2.
