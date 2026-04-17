# TODO

Phased build plan for `ticket-triage-llm`. Foundation phase ships first to establish shared files, types, interfaces, and contracts that every subsequent phase depends on. Once foundation is merged to `develop`, phases without explicit cross-dependencies can run in parallel on their own feature branches.

Phase numbering here is **independent of** the `Phase 0–7` numbering in [`PLAN.md`](PLAN.md) (which is the overall project build plan). The mapping column below shows the correspondence. Reference them distinctly when it matters.

Foundation runs TDD only where CLAUDE.md requires it (service and business logic). Config files, Dockerfiles, prompt templates, and the CI workflow itself are judgment-based — write the tests that actually prove behavior.

---

## Legend

- **Dependencies:** which TODO phase(s) must merge to `develop` before this one can start. "Foundation" means Phase F. "None beyond Foundation" means it can start as soon as F lands.
- **PLAN.md mapping:** which PLAN.md phase this corresponds to (if any).
- **TDD required?** Yes = RED/GREEN/REFACTOR strictly. Judgment = exercise judgment per CLAUDE.md ("write the tests that actually prove behavior").

---

## [2026-04-17] Phase F — Foundation (COMPLETE)

- [x] Python project scaffolding — `pyproject.toml`, `ruff.toml`, `.env.example`, `.dockerignore`, `.gitignore`, package skeleton
- [x] Shared pydantic schemas (TDD) — `TriageInput`, `TriageOutput`, `ModelResult`, `TraceRecord`, `TriageSuccess`/`TriageFailure`, `FailureReason`
- [x] `LlmProvider` Protocol (TDD) — structural typing per ADR 0004, `OllamaQwenProvider` + `CloudQwenProvider` stubs
- [x] Failure-reason literal + exhaustive-match helper (TDD)
- [x] Storage contract (TDD) — `init_schema()`, `TraceRepository` Protocol
- [x] Config loader (TDD) — pydantic-settings `Settings` with locked sampling defaults
- [x] Structured logging — stdlib formatter with ADR 0009 monitoring format
- [x] CI workflow — GitHub Actions, Python 3.11/3.12, ruff + pytest
- [x] Module stubs for future phases
- [x] Lint/format cleanup
- [x] SUMMARY.md + TODO.md updated
- [x] PR #4 opened (feature/phase-foundation → develop)
- [x] CI green on PR #4
- [x] PR #4 merged to `develop`

**Dependencies:** none — branches off `develop` directly.
**PLAN.md mapping:** predecessor scaffolding for PLAN.md Phase 1.
**Branch:** `feature/phase-foundation` (off `develop`).
**Implementation plan:** [`docs/superpowers/plans/2026-04-17-phase-foundation.md`](docs/superpowers/plans/2026-04-17-phase-foundation.md)

---

## [2026-04-17] Phase 1 — Single happy-path slice (COMPLETE)

- [x] Concrete `OllamaQwenProvider` against one model (likely 4B per OD-4)
- [x] `services/triage.py::run_triage()` — prompt builder → provider → JSON parse → schema validation (no retry yet)
- [x] Prompt module `prompts/triage_v1.py` wired into the service layer
- [x] Minimal SQLite trace insert on every request via `TraceRepository`
- [x] FastAPI app in `app.py` with Gradio mounted as sub-application (ADR 0006). `POST /api/v1/triage` + Triage tab
- [x] `Dockerfile` for app container only (Ollama on host per ADR 0007)
- [x] Service-layer tests (TDD), API route smoke test, Dockerfile build check
- [x] Happy-path integration test (mocked provider) + failed-parse unit test
- [x] SUMMARY.md + TODO.md updated
- [ ] PR opened, CI green, merged to `develop`

**Dependencies:** Foundation (F).
**Can run in parallel with:** nothing — everything else builds on the service layer this phase instantiates.
**PLAN.md mapping:** PLAN.md Phase 1.
**Branch:** `feature/phase-1-happy-path` (off `develop`, after F merges).

---

## [2026-04-17] Phase 2 — Provider abstraction + retry + guardrail stub

- [ ] `provider_router.py` registry keyed on config (no `if provider == ...` branches per ADR 0004)
- [ ] Dropdown in Triage tab driven by registry
- [ ] `services/retry.py` — bounded retry (max 1) with repair prompt (`prompts/repair_json_v1.py`)
- [ ] `services/guardrail.py` — injection phrase regexes, structural markers, length checks, basic PII regex (ADR 0008)
- [ ] Guardrail returns `pass`/`warn`/`block` + `matched_rules` list
- [ ] Unit tests (TDD) for retry policy branches, guardrail rule matches/misses, provider router selection
- [ ] SUMMARY.md + TODO.md updated
- [ ] PR opened, CI green, merged to `develop`

**Dependencies:** Foundation (F), Phase 1.
**Can run in parallel with:** Phase 3 (eval harness can start against Phase 1 service layer while Phase 2 adds retry).
**PLAN.md mapping:** PLAN.md Phase 2.
**Branch:** `feature/phase-2-providers-retry-guardrail`.

---

## [2026-04-17] Phase 3 — Evaluation harness + benchmark run

- [ ] `eval/runners/run_local_comparison.py` (E1) — local model size comparison
- [ ] `eval/runners/run_validation_impact.py` (E3) — validation on/off impact (needs Phase 2 retry)
- [ ] `eval/runners/run_prompt_comparison.py` (E4) — prompt v1 vs v2 (partial; re-run after Phase 6)
- [ ] `eval/runners/summarize_results.py` — aggregate results, compute E2 as composition of E1+E3
- [ ] All runs tag rows with `run_id` in traces table (ADR 0005)
- [ ] Fill in `docs/evaluation-checklist.md` Phase 3 sections + "Expected Benchmark Table" in `PLAN.md`
- [ ] Unit tests (TDD) for summarizer aggregation logic
- [ ] SUMMARY.md + TODO.md updated
- [ ] PR opened, CI green, merged to `develop`

**Dependencies:** Foundation (F), Phase 1. E3 needs Phase 2's retry.
**Can run in parallel with:** Phase 2 (except E3).
**PLAN.md mapping:** PLAN.md Phase 3.
**Branch:** `feature/phase-3-eval-harness`.

---

## [2026-04-17] Phase 4 — Adversarial evaluation + guardrail iteration

- [ ] Run adversarial set (`data/adversarial_set.jsonl`) against all local models using Phase 3 harness
- [ ] Per-layer accounting: guardrail blocked / reached model / model complied / validation caught / end-to-end success
- [ ] Fill Phase 4 tables in `docs/evaluation-checklist.md`
- [ ] Iterate on `services/guardrail.py` only if findings reveal concretely fixable misses
- [ ] Update `docs/threat-model.md` with measured numbers + residual-risk paragraph
- [ ] SUMMARY.md + TODO.md updated
- [ ] PR opened, CI green, merged to `develop`

**Dependencies:** Foundation (F), Phase 2 (guardrail), Phase 3 (baseline numbers).
**PLAN.md mapping:** PLAN.md Phase 4.
**Branch:** `feature/phase-4-adversarial`.

---

## [2026-04-17] Phase 5 — Dashboard, traces, live monitoring

- [ ] Metrics tab — "Benchmark Results" (static, from `run_id`-tagged traces) + "Live Metrics" (rolling time-series)
- [ ] Traces tab — request inspection and filtering
- [ ] Experiments tab — side-by-side experiment comparison
- [ ] Category-distribution drift indicator
- [ ] Log-based alerts (`WARN [monitoring] threshold_breached: ...`) per ADR 0009
- [ ] SUMMARY.md + TODO.md updated
- [ ] PR opened, CI green, merged to `develop`

**Dependencies:** Foundation (F), Phase 1 (traces exist), Phase 3 (benchmark data exists).
**Can run in parallel with:** Phase 4 (different surface area).
**PLAN.md mapping:** PLAN.md Phase 5.
**Branch:** `feature/phase-5-dashboard`.

---

## [2026-04-17] Phase 6 — Prompt v2 + prompt comparison

- [ ] Author `prompts/triage_v2.py` — meaningfully different prompt (not a tweak)
- [ ] Re-run Experiment 4 with both prompt versions
- [ ] Wire prompt-version filtering into the dashboard
- [ ] SUMMARY.md + TODO.md updated
- [ ] PR opened, CI green, merged to `develop`

**Dependencies:** Foundation (F), Phase 1, Phase 5 (dashboard filter).
**PLAN.md mapping:** PLAN.md Phase 6.
**Branch:** `feature/phase-6-prompt-v2`.

---

## [2026-04-17] Phase 7 — Hardening, documentation, presentation prep

- [ ] Sweep adversarial misses that are cheap to fix
- [ ] Write `DEPLOYMENT.md` with native + Docker quick-starts
- [ ] Cross-platform Docker testing (macOS / Windows / Linux) per ADR 0007
- [ ] Finalize ADRs reflecting what was actually built
- [ ] `demo-script.md` + `presentation-notes.md`
- [ ] Rehearse the demo twice
- [ ] SUMMARY.md + TODO.md updated
- [ ] PR opened, CI green, merged to `develop` → `main`

**Dependencies:** Phases 1–6 all merged.
**PLAN.md mapping:** PLAN.md Phase 7.
**Branch:** `release/v1-presentation` (GitFlow stabilization branch).

---

## Phase dependency graph

```text
                F (Foundation)
                │
        ┌───────┼────────────────┐
        ▼       ▼                ▼
       P1 ──► P2 ──► P4         P3 ───► P5
        │      │      ▲          │       ▲
        │      └──────┘          │       │
        └─────────────────►──────┴───────┘
                                         │
                                         ▼
                                        P6
                                         │
                                         ▼
                                        P7
```

P2 and P3 can kick off in parallel once P1 merges, subject to the "E3 needs retry from P2" scheduling note. P4 needs P2 and P3. P5 needs P3 and runs alongside P4. P6 needs P5. P7 needs everything.

---

## Completed phases

### [2026-04-17] Phase 1 — Single happy-path slice (COMPLETE)

**Objective:** Deliver the first end-to-end triage slice: OllamaQwenProvider → prompt builder → JSON parse → schema validation → trace storage, with FastAPI + Gradio UI and a Dockerfile.

**Outcome:** 130 tests, 99.64% coverage (excluding UI/entry point), ruff clean. 11 atomic commits on `feature/phase-1-happy-path`. Flat procedural pipeline in `run_triage()`. Docker build verified. System demo-able natively and via Docker.

**References:** `SUMMARY.md` (Phase 1 entry), design spec at `docs/superpowers/specs/2026-04-17-phase-1-happy-path-design.md`, implementation plan at `docs/superpowers/plans/2026-04-17-phase-1-happy-path.md`.

### [2026-04-17] Phase F — Foundation (COMPLETE)

**Objective:** Establish the shared skeleton that every subsequent phase depends on: package scaffolding, shared pydantic schemas, the `LlmProvider` Protocol, the `TriageResult` discriminated union, the SQLite `traces` table contract, the logging configuration, and CI.

**Outcome:** 73 unit tests, 89% coverage, ruff clean, CI workflow committed. 17 atomic commits on `feature/phase-foundation`. All contracts published; downstream phases unblocked.

**References:** `SUMMARY.md` (Phase F entry), PR pending (feature/phase-foundation → develop).

### [2026-04-16] Phase 0 — Smoke test (COMPLETE)

**Objective:** Empirically verify that Qwen 3.5 2B / 4B / 9B each produce structured output for the triage task on the target MacBook Pro M4 Pro / 24 GB machine, before any pipeline code is written. Serve as a go/no-go gate on the model lineup.

**Approach:** `scripts/phase0_smoke_test.py` hitting Ollama's OpenAI-compatible endpoint with the locked sampling config (temperature=0.2, top_p=0.9) on 3 normal-set tickets per model; raw outputs to `data/phase0/`.

**Outcome:** all three models 3/3 valid JSON, 3/3 correct field shape, 3/3 correct category+severity. All three retained. Two findings recorded for downstream phases: (1) the 2B's reasoning mode can over-run latency (652 s observed on `n-007`) — Phase 1+ must add a token cap or timeout; (2) MLX is not engaged for the `qwen35` architecture in Ollama 0.20.7 — Metal GGML is the active backend.

**References:** `docs/evaluation-checklist.md` (Phase 0 section), `docs/decisions/decision-log.md` (2026-04-16 Phase 0 entry), PR #1 (merged to `develop`), PR #2 (merged `develop` to `main`).
