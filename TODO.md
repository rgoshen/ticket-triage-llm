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

**Objective:** Establish the shared skeleton that every subsequent phase depends on: package scaffolding, shared pydantic schemas, the `LlmProvider` Protocol, the `TriageResult` discriminated union, the SQLite `traces` table contract, the logging configuration, and CI. Nothing here contains business logic; the point is to publish the contracts so downstream phases can be built against them in parallel without merge conflicts.

**Dependencies:** none — branches off `develop` directly as `feature/phase-foundation`.

**PLAN.md mapping:** predecessor scaffolding for PLAN.md Phase 1 (single happy-path slice). Where PLAN.md Phase 1 says "create the Python project skeleton, pydantic schemas, the `OllamaQwenProvider` against one model, `triage_service.run_triage()` end-to-end, one Gradio tab, minimal SQLite trace storage, basic Dockerfile," this Phase F carves out only the shared-contract pieces — the runnable pipeline is still TODO phase 1.

**Approach:**

1. **Python project scaffolding** (judgment)
   - `pyproject.toml` with pinned versions: `python>=3.11`, `fastapi`, `gradio`, `openai`, `ollama`, `pydantic`, `pytest`, `pytest-cov`, `ruff`, dev extras for testing. Source of truth for deps per CLAUDE.md.
   - `uv.lock` generated via `uv sync`.
   - `ruff.toml` (or `[tool.ruff]` in `pyproject.toml`).
   - `pytest` config with `--cov=ticket_triage_llm --cov-fail-under=80` on changed code.
   - `.gitignore`, `.env.example`, `.dockerignore` placeholder (the real Dockerfile lives in TODO Phase 1).
   - Package skeleton under `src/ticket_triage_llm/` matching the layout in PLAN.md "Folder Structure" section — empty `__init__.py` files and module stubs, no logic.

2. **Shared pydantic schemas** (TDD: yes — these are business-logic contracts)
   - `schemas/triage_input.py` — `TriageInput`
   - `schemas/triage_output.py` — `TriageOutput` with enum-constrained `category`, `severity`, `routingTeam`; numeric bounds on `confidence`.
   - `schemas/trace.py` — `TraceRecord` with the fields enumerated in ADR 0005 (including `run_id`, `model`, `prompt_version`, `validation_status`).
   - Discriminated union: `TriageSuccess`, `TriageFailure` (with `failure_reason: Literal[...]` per ADR 0003), `TriageResult = Union[TriageSuccess, TriageFailure]`.
   - Tests: field-type enforcement, enum rejection of invalid values, numeric-bound enforcement, discriminator round-trip through `model_dump`/`model_validate`.

3. **`LlmProvider` Protocol** (TDD: yes — the contract is the deliverable)
   - `providers/base.py` — define the `LlmProvider` `Protocol` with `name: str` and `generate_structured_ticket(ticket_body: str, prompt_version: str) -> ModelResult` per ADR 0004.
   - `providers/ollama_qwen.py` — class stub with signatures only; raises `NotImplementedError`. Concrete body belongs to TODO Phase 1.
   - `providers/cloud_qwen.py` — `NotImplementedError` placeholder (ADR 0004 requires it to exist to prove the abstraction is real).
   - Tests: a minimal fake implementing the Protocol passes structural typing; `OllamaQwenProvider` currently raises `NotImplementedError`; `CloudQwenProvider` raises `NotImplementedError`.

4. **Failure-reason literal + exhaustive-match helper** (TDD: yes)
   - Define `FailureReason = Literal["guardrail_blocked", "model_unreachable", "parse_failure", "schema_failure", "semantic_failure"]` per ADR 0003.
   - Add an assert-never helper so every `match` on `TriageResult` downstream is exhaustive.
   - Tests: exhaustiveness — a match that forgets a case fails `mypy --strict` (documented in the test) and the assert-never helper raises at runtime.

5. **Storage contract** (TDD: yes — schema definition is load-bearing)
   - `storage/db.py` — `get_connection()` + `init_schema()`. Single `traces` table matching ADR 0005 (one row per request, no summary tables).
   - `storage/trace_repo.py` — Protocol/interface only for the repository; concrete insert/query methods are TODO Phase 1.
   - Tests: `init_schema()` is idempotent; schema matches the ADR 0005 column list; repository Protocol can be satisfied by a fake.

6. **Config loader** (TDD: yes — env-var parsing is testable and easy to break)
   - `config.py` — pydantic-settings or equivalent; reads `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`), `OLLAMA_MODEL` (no default — must be set per instance), sampling params (defaults: `temperature=0.2`, `top_p=0.9`, `top_k=40`, `repetition_penalty=1.0` per 2026-04-16 sampling-lock decision), DB path.
   - Tests: defaults are the locked sampling values; env overrides are picked up; missing required values error cleanly.

7. **Structured logging** (judgment)
   - One-file `logging_config.py` setting up a structured formatter (`logging` stdlib, not a new dep). Includes the `WARN [monitoring] threshold_breached: ...` format shape from ADR 0009 so later phases emit it consistently.

8. **CI workflow** (judgment — this is infra, not business logic)
   - `.github/workflows/ci.yml` triggered on `pull_request` and `push` to `develop`/`main`.
   - Job steps: checkout, install `uv`, `uv sync --all-extras --dev`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest --cov=ticket_triage_llm --cov-fail-under=80`.
   - Python version matrix: 3.11, 3.12 (keep small; we target 3.11+).
   - Caches: uv cache keyed on `pyproject.toml` + `uv.lock`.
   - No deploy step yet; runs only in the app repo, no Ollama in CI (providers in CI use the `NotImplementedError` stubs from this phase; real provider integration tests run locally).
   - Fail-fast on any step.

**Tests:**

- Unit tests for every schema (6 above), the Protocol structural check, the failure-reason exhaustiveness helper, storage `init_schema()` idempotency, and config env-var handling.
- CI workflow validated by pushing the branch: the PR itself must turn the "CI passed" check green before merge.
- No integration tests in this phase — pipeline orchestration is TODO Phase 1.

**Risks & Tradeoffs:**

- **Over-engineering risk:** it is tempting to add the concrete `OllamaQwenProvider` body here "since the stub is already in place." Resist. This phase is deliberately limited to contracts. Merging a working provider here delays the phase and makes PR review heavier. The body belongs to TODO Phase 1.
- **CI in a contracts-only phase:** running `pytest --cov-fail-under=80` on a phase that intentionally contains mostly stubs risks a coverage shortfall. Mitigation: the schemas, config, storage schema, and failure-reason helpers are fully testable and will comfortably clear 80% on the code that actually has logic. Stub files (`ollama_qwen.py` placeholder, tab stubs) with `NotImplementedError` are measured as having coverage only if exercised — write a single import-and-assert-raises test per stub so coverage reflects the real surface.
- **pydantic-settings vs stdlib env parsing:** using `pydantic-settings` adds a dep but buys type-safe env handling that pairs with the other schemas. Tradeoff accepted.
- **CI running only on stubs is low-value on the first pass** — but it means every subsequent PR in the project enters CI the moment it opens, which is the real point.

**Branch:** `feature/phase-foundation` (off `develop`).
**Exit criteria:** `docs/adr/` links resolve, `uv sync` succeeds, `uv run pytest` passes at ≥80% on changed code, `uv run ruff check .` clean, CI green on the PR, `SUMMARY.md` updated, PR merged to `develop`.

---

## [2026-04-17] Phase 1 — Single happy-path slice

**Objective:** First end-to-end working slice: one ticket in, one structured triage object out, via one model, one prompt, one Gradio tab. Demo-able natively and via Docker.

**Dependencies:** Foundation (F).
**Can run in parallel with:** nothing — everything else builds on the service layer this phase instantiates.
**PLAN.md mapping:** PLAN.md Phase 1.

**Approach:**

1. Concrete `OllamaQwenProvider` against one model (default from Phase 0 go/no-go — likely 4B; decision deferred to post-experiment data per OD-4).
2. `services/triage.py::run_triage()` orchestrating prompt builder → provider → JSON parse → schema validation. No retry yet (bounded retry lands in TODO Phase 2).
3. Prompt module `prompts/triage_v1.py` carrying the prompt already exercised in the Phase 0 smoke test (same structural-delimiter design).
4. Minimal SQLite trace insert on every request using the repo from Phase F.
5. FastAPI app in `app.py` with Gradio mounted as sub-application (ADR 0006 addendum). `POST /api/v1/triage` route plus the Triage tab.
6. `Dockerfile` for the app container only (Ollama stays on host per ADR 0007); `.dockerignore`.
7. One happy-path integration test (mocked provider) and one failed-parse unit test against the validation step.

**Tests:** service-layer tests (TDD yes); API route smoke test; Dockerfile build check in CI.

**Risks & Tradeoffs:**

- Retry is deferred to TODO Phase 2 to keep this phase small. Known consequence: if the model produces malformed JSON on the happy path the request will `TriageFailure` at `parse_failure`; that is acceptable for a first slice.
- Default model defer-until-data (OD-4 in PLAN.md) — this phase picks one reasonable default and flags it for revisit.

**Branch:** `feature/phase-1-happy-path` (off `develop`, after F merges).

---

## [2026-04-17] Phase 2 — Provider abstraction + retry + guardrail stub

**Objective:** All three local models behind the same `LlmProvider` Protocol, one-click switching in the UI, bounded retry (max 1) wired in, and the heuristic guardrail in its initial form.

**Dependencies:** Foundation (F), Phase 1.
**Can run in parallel with:** Phase 3 (eval harness can be authored against the Phase 1 service layer while Phase 2 adds retry).
**PLAN.md mapping:** PLAN.md Phase 2.

**Approach:**

- `provider_router.py` registry keyed on config.
- Dropdown in the Triage tab driven by the registry (no `if provider == ...` branches in services, per ADR 0004).
- `services/retry.py` implementing the bounded retry with the repair prompt (`prompts/repair_json_v1.py`).
- `services/guardrail.py` first pass: known injection phrase regexes, structural markers, length checks, basic PII regex (ADR 0008).
- Guardrail returns `pass` / `warn` / `block` and an optional `matched_rules` list per ADR 0008 / 0009.

**Tests:** unit tests (TDD yes) for retry policy branches, guardrail rule matches/misses, provider router selection.

**Risks & Tradeoffs:**

- Guardrail false-positive risk on legitimate tickets quoting injection-like phrases. Tracked as an empirical question for Phase 4.

**Branch:** `feature/phase-2-providers-retry-guardrail`.

---

## [2026-04-17] Phase 3 — Evaluation harness + benchmark run

**Objective:** Run the four planned experiments, produce real numbers to replace the placeholder TBDs in `PLAN.md`.

**Dependencies:** Foundation (F), Phase 1. **Can start in parallel with Phase 2**, but the validation-on/off experiment (E3) needs Phase 2's retry to mean anything; schedule E3 after Phase 2 merges.
**PLAN.md mapping:** PLAN.md Phase 3.

**Approach:**

- `eval/runners/run_local_comparison.py` (E1), `run_validation_impact.py` (E3), `run_prompt_comparison.py` (E4 — v2 not yet authored; E4 runs partially here and again after Phase 6), and `summarize_results.py`.
- E2 (model size vs engineering controls) is a *composition* of E1 + E3 results — write the summarizer to compute it rather than running a separate pass.
- All runs tag rows with `run_id` in the `traces` table (ADR 0005). Summaries are computed on the fly from traces (no second table).
- Fill in `docs/evaluation-checklist.md` Phase 3 sections and the "Expected Benchmark Table" in `PLAN.md`.

**Tests:** unit tests for summarizer aggregation logic (TDD yes); eval runners themselves are thin wrappers and are validated end-to-end by the benchmark run.

**Risks & Tradeoffs:**

- Runs are long — a full sweep of 35 normal tickets × 3 models × 2 validation configs × 2 prompt versions could take hours. Plan for an overnight run; structure runners so partial-completion traces are still usable.

**Branch:** `feature/phase-3-eval-harness`.

---

## [2026-04-17] Phase 4 — Adversarial evaluation + guardrail iteration

**Objective:** Run the adversarial set against all local models; measure per-layer effectiveness; iterate on the guardrail based on findings. Produce the residual-risk statement.

**Dependencies:** Foundation (F), Phase 2 (guardrail must exist), Phase 3 (baseline benchmark numbers must exist so guardrail-iteration effects are measurable).
**PLAN.md mapping:** PLAN.md Phase 4.

**Approach:**

- Reuse Phase 3 harness, swapping the dataset for `data/adversarial_set.jsonl`.
- Per-layer accounting (guardrail blocked / reached model / model complied / validation caught / end-to-end success) fills the Phase 4 tables in `docs/evaluation-checklist.md`.
- Iterate on `services/guardrail.py` only if findings reveal a concretely fixable miss. Record each iteration in the checklist's iteration table.
- Update `docs/threat-model.md` with the measured numbers and an honest residual-risk paragraph.

**Risks & Tradeoffs:** ADR 0008 explicitly expects the heuristic guardrail to miss obfuscated attacks — those misses are *findings*, not defects. Do not over-engineer the guardrail to suppress expected failures; the comparison only works if the heuristic baseline is real.

**Branch:** `feature/phase-4-adversarial`.

---

## [2026-04-17] Phase 5 — Dashboard, traces, live monitoring

**Objective:** Metrics / Traces / Experiments tabs fully populated; Metrics split into "Benchmark Results" (static) and "Live Metrics" (rolling) per ADR 0009; log-based alerting wired up.

**Dependencies:** Foundation (F), Phase 1 (traces exist), Phase 3 (benchmark data exists).
**Can run in parallel with:** Phase 4 (different surface area).
**PLAN.md mapping:** PLAN.md Phase 5.

**Approach:** as specified in `PLAN.md` Phase 5 and ADR 0009 — two-section Metrics tab, category-distribution drift indicator, log-based alerts (`WARN [monitoring] threshold_breached: ...`). No separate time-series DB, no Prometheus.

**Branch:** `feature/phase-5-dashboard`.

---

## [2026-04-17] Phase 6 — Prompt v2 + prompt comparison

**Objective:** Author `prompts/triage_v2.py` as a meaningfully different prompt (not a tweak), re-run Experiment 4 with both prompts, wire prompt-version filtering into the dashboard.

**Dependencies:** Foundation (F), Phase 1, Phase 5 (dashboard filter lands here if not earlier).
**PLAN.md mapping:** PLAN.md Phase 6.

**Branch:** `feature/phase-6-prompt-v2`.

---

## [2026-04-17] Phase 7 — Hardening, documentation, presentation prep

**Objective:** Everything polished for demo day.

**Dependencies:** Phases 1–6 all merged.
**PLAN.md mapping:** PLAN.md Phase 7.

**Approach:** sweep adversarial misses that are cheap to fix; write `DEPLOYMENT.md` with native + Docker quick-starts; cross-platform Docker testing (macOS / Windows / Linux) per ADR 0007; finalize ADRs reflecting what was actually built; `demo-script.md`; `presentation-notes.md`; rehearse the demo twice.

**Branch:** `release/v1-presentation` (per GitFlow — this is the stabilization branch for the final deliverable).

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

### [2026-04-17] Phase F — Foundation (COMPLETE)

**Objective:** Establish the shared skeleton that every subsequent phase depends on: package scaffolding, shared pydantic schemas, the `LlmProvider` Protocol, the `TriageResult` discriminated union, the SQLite `traces` table contract, the logging configuration, and CI.

**Outcome:** 73 unit tests, 89% coverage, ruff clean, CI workflow committed. 17 atomic commits on `feature/phase-foundation`. All contracts published; downstream phases unblocked.

**References:** `SUMMARY.md` (Phase F entry), PR pending (feature/phase-foundation → develop).

### [2026-04-16] Phase 0 — Smoke test (COMPLETE)

**Objective:** Empirically verify that Qwen 3.5 2B / 4B / 9B each produce structured output for the triage task on the target MacBook Pro M4 Pro / 24 GB machine, before any pipeline code is written. Serve as a go/no-go gate on the model lineup.

**Approach:** `scripts/phase0_smoke_test.py` hitting Ollama's OpenAI-compatible endpoint with the locked sampling config (temperature=0.2, top_p=0.9) on 3 normal-set tickets per model; raw outputs to `data/phase0/`.

**Outcome:** all three models 3/3 valid JSON, 3/3 correct field shape, 3/3 correct category+severity. All three retained. Two findings recorded for downstream phases: (1) the 2B's reasoning mode can over-run latency (652 s observed on `n-007`) — Phase 1+ must add a token cap or timeout; (2) MLX is not engaged for the `qwen35` architecture in Ollama 0.20.7 — Metal GGML is the active backend.

**References:** `docs/evaluation-checklist.md` (Phase 0 section), `docs/decisions/decision-log.md` (2026-04-16 Phase 0 entry), PR #1 (merged to `develop`), PR #2 (merged `develop` to `main`).
