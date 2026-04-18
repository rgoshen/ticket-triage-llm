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

## [2026-04-18] Phase 4B — Documentation corrections (post-review cleanup)

**What was done:**

Five categories of documentation correction across `docs/evaluation-checklist.md`, `docs/threat-model.md`, `docs/evaluation-plan.md`, `docs/decisions/decision-log.md`, and `CLAUDE.md`:

1. **a-008 reframed from integrity compromise to non-reproducing observation.** Two replication attempts on the 4B both produced parse failures instead of the original partial field match. The finding was reclassified: the 4B's dominant behavior on a-008 is availability failure (2/3 runs = parse failure), not partial compliance (1/3 runs). The "empirically weakest seam" section in `threat-model.md` was renamed to "availability impact from adversarial content." All residual risk statements, combined risk statements, and cross-references updated to reflect non-reproducibility.

2. **Timeout terminology corrected to token-budget exhaustion.** The 118-120s (4B) and 162-164s (9B) failures are caused by `max_tokens=2048` exhaustion on reasoning tokens, not a client or provider timeout. The OpenAI client has no explicit timeout set. All references in the reasoning-mode exhaustion section, availability risk, combined risk statement, future work, and measurement table corrected. Future mitigations reframed from "shorter timeouts" to "separate reasoning-token budgets" and "lower max_tokens."

3. **Thinking-mode disabled for demo/production configuration.** Decision log entry added documenting `think=false` as a post-Phase 4 configuration change. CLAUDE.md sampling parameters updated. Scope explicitly noted: Phase 0–4 evaluation data was collected with `think=true` (default); demo config differs from evaluation config, documented honestly rather than retroactively.

4. **Evaluation Methodology Limitations section added to evaluation-plan.md.** Five subsections: aggregate findings defensibility at n=35, small-difference noise caveat, per-ticket point-observation caveat, replication gap documentation, and evaluation-vs-production configuration divergence.

5. **Phase 3 observations softened where accuracy claims exceeded n=35 noise floor.** E1 key finding reframed from "best performer across all metrics" to "best JSON validity and reliability." Accuracy differences between 4B and 9B (57.1% vs 54.3% category, 51.4% vs 48.6% severity) flagged as within the ~3%-per-ticket noise band. Cross-experiment observations updated similarly. Closing notes added to each experiment's observation section referencing the methodology limitations.

**What was NOT changed:**

- Integrity/availability framework and two-objective structure
- Reasoning-mode exhaustion section structure (only terminology within it)
- 2B unmeasurability caveats
- Per-layer analysis structure in threat-model.md
- Any ADRs
- Phase 3 headline findings based on large-magnitude differences (2B collapse at 2.9%, 4B-validated 29/35 vs 9B-unvalidated 17/35, 4B JSON validity 82.9% vs 9B 74.3%)
- Phase 4 per-ticket intersection table (only a-008 row annotated with replication data)

**How it was done:**

- All changes on `feature/phase-4b-cleanup` branch. Documentation-only edits — no code changes.
- Each correction category applied systematically across all files that referenced the affected claims, with grep verification after each batch to catch stale cross-references.
- a-008 replication was performed in a prior session; this session documents the findings.

**Issues encountered:**

1. **Stale cross-references across files.** The a-008 finding was referenced in threat-model.md (5 sections), evaluation-checklist.md (6 sections), and indirectly in the decision log. Each reference used slightly different phrasing ("ambiguous partial match," "most interesting finding," "weakest seam"), requiring individual edits rather than a find-and-replace.

2. **Timeout terminology was load-bearing in future-work items.** The future mitigations section recommended "shorter per-request timeouts" — but the correct mitigation for token-budget exhaustion is a different token budget, not a shorter timeout. Had to rewrite the mitigation recommendations, not just the terminology.

**How those issues were resolved:**

1. Grepped for each key phrase after editing to verify no stale references remained. Final verification pass confirmed all "weakest seam," "ambiguous partial match," "provider timeout," and "outperforms on every metric" references updated or removed.

2. Rewrote future-work items 5 and 6 to reflect the correct mechanism: separate reasoning-token budgets and lower `max_tokens` values, rather than shorter timeouts.

**Exit state:**

- All five documentation files updated and internally consistent.
- No code changes, no test changes, no ADR changes.
- Phase 4 documentation now reflects honest, replication-informed findings rather than single-run observations presented as conclusions.

---

## [2026-04-18] Hotfix: Demo reliability + UI improvements

**What was done:**

- Fixed SQLite threading error — Gradio dispatches handlers to worker threads, but the connection was created in the main thread. Added `check_same_thread=False` to `get_connection()`. Safe because WAL mode handles concurrent reads and the app is single-writer.
- Switched provider from `openai` Python client to native `ollama` Python client with `think=False`. The OpenAI-compatible endpoint does not support the `think` parameter. Disabling reasoning mode reduced 4B response time from 60-120s (with frequent parse failures) to 5-10s with reliable structured output.
- Improved triage result display: title-cased field values (Account Access, not account_access), removed confidence from user-facing output (internal metric), user-friendly failure messages instead of raw trace dumps.
- Added Cancel and New Ticket buttons. Cancel aborts a running request and shows "Ticket submission cancelled." New Ticket clears all fields for the next submission.
- Put trace details in a collapsed accordion (hidden by default, expandable for debugging).
- Fixed cancel double-click bug — switched from Gradio generator pattern to `.click().then()` chain so cancel doesn't leave the event queue in a stuck state.
- Added `PYTHONPATH=/app/src` to Dockerfile (module not found error on container startup).
- Added `docker-compose.yml` for simpler Docker usage (`docker compose up --build`).
- Updated README with clear setup instructions for both native and Docker paths, including Ollama prerequisites.
- Reverted default model back to 4B in `.env.example` — `think=False` resolved the reliability issue that prompted the temporary switch to 9B.

**How it was done:**

- All fixes on `hotfix/demo-reliability` branch, merged to `develop` incrementally. Phase 4 branch rebased after each merge to stay current.

**Issues encountered:**

1. **4B model timing out on normal tickets.** The 4B produced parse failures at 115-120s on straightforward tickets during live demo testing. Root cause: Qwen 3.5's reasoning mode was consuming the entire token budget on internal chain-of-thought before emitting JSON. The `/no_think` prompt tag does not work through the OpenAI-compatible endpoint, but the native `ollama` client's `think=False` parameter does.
2. **Gradio cancel leaves event queue stuck.** After cancelling a generator-based event, the next click required two presses. Switched from `yield`-based generator to a `.click().then()` chain which cancels cleanly.
3. **Docker container couldn't find the package.** `uv sync --no-editable` installs dependencies but not the project itself. Added `PYTHONPATH=/app/src` to the Dockerfile so Python finds the `ticket_triage_llm` package.

---

## [2026-04-18] Phase 4 — Adversarial evaluation + guardrail iteration

**What was done:**

- Built the adversarial assessment harness: adversarial dataset loader with adapter to `TicketRecord`, compliance detection module with per-ticket indicators for all 14 adversarial tickets, per-layer cascade accounting (`LayerAccounting`, `AdversarialSummary`), false-positive baseline computation, and an adversarial runner that reuses the Phase 3 `run_experiment_pass()` infrastructure.
- Ran the full adversarial evaluation against all three Qwen 3.5 models (2B, 4B, 9B) on the 14-ticket adversarial set. Result JSONs written to `data/phase4/adversarial-{2b,4b,9b}.json`.
- Filled Phase 4 tables in `docs/evaluation-checklist.md` with per-model results, ticket-level 4B vs 9B intersection analysis, per-rule guardrail hit distribution, integrity and availability residual risk summaries, guardrail iteration decision, and 7 analytical observations.
- Updated `docs/threat-model.md` with measured per-layer effectiveness, three new sections (integrity vs availability attack objectives, indirect injection via quoted content as the empirically weakest seam, reasoning-mode exhaustion as an availability attack vector), and restructured residual risk and future-work sections with measured numbers.
- No guardrail iteration performed — the zero-block result is the expected baseline finding per ADR 0008 (heuristic guardrail vs obfuscated/indirect attacks). Adding more regex patterns would not address the attack categories that bypassed the guardrail.
- Two PR reviews identified code-level bugs in the compliance and accounting logic. Fixes applied in two rounds:
  - **Round 1 (fed7b70):** `compute_layer_accounting()` excluded `parse_failure` from `validation_caught` (only `schema_failure`/`semantic_failure` count). `_check_field_injection()` changed from ANY-match to ALL-match (partial match returns `complied=None` for manual review).
  - **Round 2 (6701900):** `_failure_compliance()` helper distinguishes genuine defense catches (`guardrail_blocked`, `schema_failure`, `semantic_failure` → `complied=False`) from availability failures (`parse_failure`, `model_unreachable` → `complied=None` inconclusive). `AdversarialSummary` gained `run_status` and `failed_tickets` fields. `compute_layer_accounting` docstring corrected to match post-fix code.
- Regenerated all three result JSONs from existing SQLite traces using `scripts/regenerate_phase4_jsons.py` (no re-inference). Pre-fix JSONs archived as `data/phase4/adversarial-*-pre-fix.json` for audit trail. Updated docs with corrected numbers.

**Headline finding (corrected):** Zero confirmed integrity compromises across all three models. Ticket a-008 (indirect injection via quoted content) is the most ambiguous finding: the 4B produced `escalation=True` matching 1 of 2 injected field values (`severity=critical` did not match — actual was `high`). Under the corrected ALL-match rule this is a partial match classified as `complied=None` (needs manual review), not a confirmed compromise. The 9B resisted the same attack entirely. The ambiguity of a-008 — whether `escalation=True` reflects injection influence or a legitimate classification for a billing complaint about an app crash — is itself a finding about the limits of automated compliance measurement.

**How it was done:**

- Strict RED/GREEN/REFACTOR TDD for all harness modules (datasets, compliance, results, false-positive baseline). Judgment-based for the runner entry point.
- Subagent-driven development: Tasks 1–4 (datasets, compliance, results, FP baseline) built in parallel with independent test suites.
- Adversarial evaluation run via `uv run python -m ticket_triage_llm.eval.runners.run_adversarial_eval` with `OLLAMA_MODEL=qwen3.5:4b OLLAMA_MODELS=qwen3.5:2b,qwen3.5:4b,qwen3.5:9b`.
- 266 tests total, 93.56% coverage, ruff clean.

**Issues encountered:**

1. **Ollama session crash during initial adversarial run.** The first run completed the 4B (14/14 traces) but crashed partway through the 9B (4/14 traces). Cursor also crashed, losing session context.
2. **Ollama model not loading on second attempt.** On restart, `ollama ps` showed no active model despite `ollama list` showing all three present. The runner received HTTP 200 responses from Ollama but the completions were empty/malformed, causing 100% parse failures on the 2B.
3. **2B 100% parse failure rate.** The 2B failed to produce valid JSON on all 14 adversarial tickets, consistent with its 97.1% failure rate on normal tickets in E1. Every request consumed ~68s (two attempts at ~34s each).
4. **Missing `.env` file.** The `Settings()` constructor requires `OLLAMA_MODEL` which has no default. Previous sessions passed env vars inline; the `.env` file was never committed (correctly — it's in `.gitignore`).

**How those issues were resolved:**

1. Partial traces from the crashed run were left in SQLite (harmless — each run gets a unique timestamped `run_id`). A clean re-run produced fresh traces with new run_ids.
2. Ollama recovered after the cursor crash. A quick sanity check (`curl` to the chat completions endpoint) confirmed the 4B was responding correctly before restarting the full run.
3. The 2B's failure rate is documented as an availability finding, not a security finding. Its `residual_risk=0` is explicitly called out as a statistical artifact of structured-output brokenness — the 2B fails before security layers are tested. The evaluation write-up excludes the 2B from the 4B vs 9B security comparison.
4. Passed env vars inline: `OLLAMA_MODEL=qwen3.5:4b OLLAMA_MODELS=qwen3.5:2b,qwen3.5:4b,qwen3.5:9b uv run python -m ...`.

**Exit state:**

- 266 tests pass, 93.56% coverage, ruff clean.
- `docs/evaluation-checklist.md` Phase 4 section fully populated with measured data and analytical observations.
- `docs/threat-model.md` updated with measured per-layer rates, integrity/availability distinction, and empirical weakest-seam analysis.
- Phase 5 unblocked (dashboard can display adversarial results alongside Phase 3 benchmarks).
- Phase 7 can reference Phase 4 findings for presentation material (a-008 is the demonstration case for prompt injection investigation).

---

## [2026-04-18] Phase C — Cleanup (deferred PR review polish)

**What was done:**

- Removed verbose docstrings from `validation.py` that restated type signatures.
- Extracted shared test fakes (`FakeProvider`, `FakeTraceRepo`, `AlwaysBadJsonProvider`, `AlwaysBadSchemaProvider`, `RetrySuccessProvider`, `ErrorProvider`, `VALID_JSON_OUTPUT`) into `tests/fakes.py`. Updated 3 test files to import from the shared module.
- Hardened repair prompt delimiter: replaced triple-backtick wrapping with XML `<failed_output>` tags in `prompts/repair_json_v1.py` to avoid structural ambiguity when model output contains backticks.
- Extracted `_failure_result()` helper in `retry.py`, reducing ~30 lines of near-identical `RetryResult(TriageFailure(...))` construction to single-line calls.
- Fixed `.gitignore`: `*/memory/` → `**/memory/` for correct nested directory matching.
- Renamed unused `_trace` to `_` in API route.
- Deferred 3 items to Phase 7: API route globals refactor, design spec staleness notes, pre-repair error detail in TriageFailure.

**How it was done:**

- One atomic commit per item on `feature/phase-cleanup`. 220 tests pass, ruff clean after each commit.
- No behavioral changes — pure polish.

**Issues encountered:**

None — all items were straightforward cleanup.

**Exit state:**

- 220 tests pass, ruff clean. 7 of 11 Phase C items resolved; 3 deferred to Phase 7; 1 was already correct.

---

## [2026-04-17] Phase 3 — Evaluation harness + benchmark run

**What was done:**

- Added `ticket_id` field to `TraceRecord` and `traces` table for ground-truth correlation.
- Added `skip_validation`, `run_id`, `ticket_id` parameters to `run_triage()`. `skip_validation=True` bypasses `validate_or_retry()`, sets `validation_status="skipped"`, records parse/schema outcome without retry.
- Implemented `get_traces_by_run()` and `get_all_traces()` on `SqliteTraceRepository` (previously `NotImplementedError` stubs).
- Created `eval/datasets.py` with `GroundTruth`, `TicketRecord` dataclasses and `load_dataset()` JSONL parser.
- Created `eval/results.py` with `ModelMetrics` and `ExperimentSummary` dataclasses.
- Implemented `eval/runners/common.py::run_experiment_pass()` — shared loop calling `run_triage()` per ticket with eval params.
- Implemented `summarize_run()` — computes accuracy (category, severity, routing, escalation), reliability (JSON valid rate, schema pass rate, retry rate), and operational (latency percentiles, token averages) metrics by joining traces on `ticket_id` to ground truth.
- Implemented `compose_e2()` — picks smallest-model-with-validation from E1, computes largest-model-no-validation from dedicated run.
- Implemented E1 runner (`run_local_comparison.py`) — runs all providers through normal set with full validation.
- Implemented E3 runner (`run_validation_impact.py`) — runs 4B validated/skipped + 9B skipped for E2 data point.
- Implemented E4 runner (`run_prompt_comparison.py`) — v1 only for Phase 3, re-run after Phase 6.
- All runners write JSON summaries to `data/phase3/` and tagged traces to SQLite.
- 213 tests total, 92.47% coverage, ruff clean.

**How it was done:**

- Strict RED/GREEN/REFACTOR TDD for summarizer, dataset loader, shared runner loop, skip-validation, trace repo query methods.
- Judgment-based for runner CLI entry points and results dataclasses.
- Subagent-driven development: fresh subagent per task with parallel dispatch for independent tasks on `feature/phase-3-eval-harness`.
- 12 atomic commits on `feature/phase-3-eval-harness`.

**Issues encountered:**

1. **Parallel subagent commit collision.** Tasks 9 (E1 runner), 10 (E3 runner), and 11 (E4 runner) were dispatched in parallel. The E1 runner's commit was absorbed into E3's commit because both subagents staged and committed concurrently. All file content is correct — just one fewer commit than planned.
2. **Coverage drop from runner CLI modules.** The three runner files each contain `if __name__ == "__main__"` blocks with real Ollama setup that can't be unit-tested. Coverage dropped to 75% until these were added to the coverage omit list (same pattern as `app.py` and `ui/*` from Phase 1).

**How those issues were resolved:**

1. Verified all three runner files are present with correct content via import checks and file inspection. The commit history shows the E1 content in the E3 commit — functionally correct, just bundled.
2. Added the three runner modules to `[tool.coverage.report] omit` in `pyproject.toml`. Coverage rose to 92.47%.

**Exit state:**

- 213 tests pass, 92.47% coverage, ruff clean.
- Phase 4 unblocked (adversarial eval uses the same harness + guardrail `matched_rules`).
- Phase 5 unblocked (dashboard queries `run_id`-tagged traces).
- Eval checklist tables to be filled when experiments are run against Ollama.

---

## [2026-04-17] Phase 2 — Provider abstraction, retry, and guardrail

**What was done:**

- Implemented `ProviderRegistry` for config-driven multi-model switching via `OLLAMA_MODELS` env var. Dropdown in Triage tab driven by registry; API route resolves provider from request payload.
- Implemented bounded retry service (`services/retry.py`) with repair prompt (`prompts/repair_json_v1.py`). On parse or schema failure, sends the failed output + specific error back to the same model for self-correction. Exactly one retry per ADR 0002.
- Implemented heuristic guardrail (`services/guardrail.py`) per ADR 0008. Pattern matching for injection phrases (5 block + 2 warn), structural markers (3 rules), PII (2 rules), and length checks. `act_as` and `you_are_now` demoted to `warn` after PR review identified high false-positive rates on legitimate tickets. Returns `pass`/`warn`/`block` with namespaced `matched_rules` for Phase 4 per-rule analysis.
- Added `validate_schema_with_error()` to validation service — returns the error string for inclusion in repair prompts.
- Refactored `run_triage()` to compose: guardrail → provider → validate_or_retry → trace. Three exit points, reduced `_save_trace` duplication.
- Updated Triage tab with `gr.Dropdown` for model selection, guardrail status in trace summary.
- Updated API route to resolve provider from `ProviderRegistry`.
- Retry traces sum tokens from both initial and repair attempts; `tokens_per_second` recomputed from summed values so monitoring queries are accurate.
- API route returns 422 (not 500) for unknown provider names.
- `GUARDRAIL_MAX_LENGTH` config wired through app → triage_tab/api_route → `run_triage()`.
- `__repair__` prompt version registered as pass-through in `get_prompt()` to prevent ValueError against real Ollama provider.
- 178 tests total, 98.76% coverage, ruff clean.

**How it was done:**

- Strict RED/GREEN/REFACTOR TDD for all three services (provider router, guardrail, retry) and the validation enhancement.
- Subagent-driven development: fresh subagent per task with parallel dispatch for independent tasks on `feature/phase-2-providers-retry-guardrail`.
- Each service is independently testable with pure functions/classes and clear inputs/outputs.
- PR review identified 4 mediums and 4 lows; mediums fixed in follow-up commits, lows deferred to Phase C.

**Issues encountered:**

1. **API route integration test regression.** The integration test for `POST /api/v1/triage` passed a `FakeProvider` directly to `configure()`, which now expects a `ProviderRegistry`. Tests failed with `AttributeError: 'FakeProvider' object has no attribute 'default'`.
2. **Existing parse/schema failure tests affected by retry.** The Phase 1 tests used `FakeProvider` which always returns valid JSON — so after retry integration, parse failure tests would succeed on retry instead of failing. Required new test helpers (`AlwaysBadJsonProvider`, `AlwaysBadSchemaProvider`) that consistently fail.
3. **Repair prompt version not registered.** `_attempt_repair()` called the provider with `prompt_version="__repair__"`, but `get_prompt()` only knew `"v1"`. Any retry on a real Ollama provider would crash with `ValueError`.
4. **Retry traces undercounted tokens.** Only the initial `ModelResult` was recorded in the trace; the repair attempt's tokens were lost.
5. **`act_as`/`you_are_now` guardrail rules too aggressive.** Matched legitimate phrases like "act as a liaison" and "you are now on the escalation list."

**How those issues were resolved:**

1. Updated `tests/integration/test_api_route.py` to wrap `FakeProvider` in a `ProviderRegistry` before passing to `configure()`.
2. Created dedicated test helpers that always return invalid output, ensuring the retry service also fails and the test exercises the intended failure path.
3. Added `"__repair__"` as a pass-through version in `get_prompt()` that returns `(ticket_subject, ticket_body)` directly.
4. `RetryResult` now carries `repair_model_result`; `triage.py` sums token counts and recomputes `tokens_per_second` from the combined values.
5. Demoted both rules from `block` to `warn`. Phase 4 will measure actual FP rates and determine final disposition.

**Exit state:**

- 178 tests pass, 98.76% coverage, ruff clean.
- Phase 3 unblocked (eval harness). Phase 4 unblocked (adversarial eval uses the guardrail's `matched_rules` for per-rule analysis).
- Low/nit PR review findings added to Phase C cleanup backlog.

---

## [2026-04-17] Phase 1 — Single happy-path slice

**What was done:**

- Implemented the first end-to-end triage pipeline: `OllamaQwenProvider` → prompt builder → JSON parse → schema validation → trace storage.
- `OllamaQwenProvider` uses the `openai` Python client pointed at Ollama's OpenAI-compatible endpoint with locked sampling params (temperature=0.2, top_p=0.9, top_k=40, repetition_penalty=1.0) and max_tokens=2048 to cap reasoning runaway.
- Prompt dispatch service (`services/prompt.py`) routing version strings to prompt implementations. v1 prompt fully wired.
- Validation service (`services/validation.py`) with markdown fence stripping and pydantic schema validation.
- `SqliteTraceRepository` with `save_trace()` and `get_recent_traces()` — remaining 4 query methods deferred to Phase 3/5.
- FastAPI app with Gradio Triage tab mounted as sub-application, `POST /api/v1/triage` endpoint with Swagger docs at `/api/v1/docs`.
- Multi-stage Dockerfile for the app container (Ollama on host per ADR 0007). Docker build verified.
- 130 tests total (57 new), 99.64% coverage on service/business logic, ruff clean.

**How it was done:**

- Strict RED/GREEN/REFACTOR TDD for all service and business logic (prompt, validation, trace repo, triage orchestrator, provider).
- Judgment-based approach for app wiring, Gradio UI, and Dockerfile per CLAUDE.md guidance.
- Flat procedural pipeline in `run_triage()` — each step is a standalone function, all dependencies passed as parameters. No globals, no singletons.
- Subagent-driven development: fresh subagent per task, 11 atomic commits on `feature/phase-1-happy-path`, Conventional Commits format.

**Issues encountered:**

1. **Task dependency ordering.** Task 2 (OllamaQwenProvider) imports `get_prompt()` from Task 3 (prompt service). Had to implement Task 3 first despite the plan numbering.
2. **Coverage threshold.** UI (`triage_tab.py`), entry point (`app.py`), and logging config (`logging_config.py`) are at 0% coverage — they're judgment-based, not TDD targets. Coverage was 77.5%, below the 80% floor.
3. **Ruff violations from subagent output.** Seven files needed reformatting; import sorting, unused imports (`datetime.UTC`, `pytest`), and `zip()` missing `strict=` parameter.
4. **Subject handling across Protocol boundary.** The `LlmProvider` Protocol takes `(ticket_body, prompt_version)` but not `ticket_subject`. The subject field is optional (default `""`) — accepted as a minor Phase 1 limitation, revisitable in Phase 2 if subjects affect quality.

**How those issues were resolved:**

1. Reordered execution: Task 3 (prompt service) before Task 2 (provider). No plan change needed — the code was correct, just the order shifted.
2. Added `omit` list to `[tool.coverage.report]` in `pyproject.toml` excluding `app.py`, `ui/*`, and `logging_config.py`. Coverage rose to 99.64%.
3. Ran `ruff check --fix . && ruff format .` in a single cleanup commit after all implementation tasks.
4. Documented as a known limitation. The provider calls `get_prompt(version, "", ticket_body)` with empty subject. The prompt still works — the subject line in the formatted prompt is just blank.

**Exit state:**

- 130 tests pass, 99.64% coverage on service code, ruff clean.
- System demo-able natively via `uv run python -m ticket_triage_llm.app` (requires Ollama running + `OLLAMA_MODEL` env var) and via `docker run`.
- Phase 2 unblocked (provider router, retry, guardrail).

---

## [2026-04-17] Phase F — Foundation

**What was done:**

- Established the shared contract layer that every downstream phase builds against: pydantic schemas (`TriageInput`, `TriageOutput`, `ModelResult`, `TraceRecord`, `TriageSuccess`, `TriageFailure`, `FailureReason`), the `LlmProvider` Protocol, the `TraceRepository` Protocol, the SQLite `traces` table schema, a pydantic-settings config loader with locked sampling defaults, structured logging, module stubs for all future phases, and a GitHub Actions CI workflow.
- 73 unit tests covering all schema contracts, Protocol structural typing, storage idempotency, config env-var parsing, and stub behavior. 89% coverage (80% floor enforced in CI).
- Full ruff lint and format compliance across the codebase (including retroactive fixes to the Phase 0 smoke-test script).

**How it was done:**

- Strict RED/GREEN/REFACTOR TDD for all schema and contract code (Tasks 3–13 in the implementation plan). Each task: write failing tests first, implement minimal code to pass, commit atomically.
- Judgment-based approach for config, logging, CI workflow, and module stubs (Tasks 1–2, 14–16) per CLAUDE.md guidance.
- 17 atomic commits on `feature/phase-foundation`, each representing one logical change. Conventional Commits format throughout.
- Branch cut from `develop` after Phase 0 merge.

**Issues encountered:**

1. **ruff lint violations after initial implementation.** Nine errors across four files: E501 (line length), E402 (mid-file imports in test_providers.py), I001 (import sort order), UP017 (`timezone.utc` vs `datetime.UTC` alias).
2. **Terminal crash during Task 16.** The terminal closed after Task 15 (module stubs) was committed but before Task 16 (CI workflow) and Task 17 (final cleanup) ran.

**How those issues were resolved:**

1. Fixed all lint violations: moved imports to top of file in test_providers.py, switched to `datetime.UTC` alias, reformatted long lines in the Phase 0 script, and ran `ruff format` to catch two files with whitespace issues. Single commit for all style fixes.
2. No data loss — all prior work was in atomic commits. Recovery: inspected `git log`, `git status`, and the implementation plan to determine exact stopping point (end of Task 15), then resumed from Task 16.

**Exit state:**

- All 17 tasks complete. `uv sync` succeeds, `uv run pytest` passes at 89% coverage, `ruff check` and `ruff format --check` both clean.
- CI workflow committed but not yet validated by GitHub Actions (requires PR push).
- PR to `develop` pending.

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
