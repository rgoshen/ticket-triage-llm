# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status: pre-implementation

At the time of writing, the repository contains **only planning artifacts** — 9 ADRs, `PLAN.md`, `docs/architecture.md`, `docs/threat-model.md`, `docs/evaluation-plan.md`, `docs/tradeoffs.md`, `docs/cost-analysis.md`, `docs/future-improvements.md`, and `docs/decisions/decision-log.md`. There is no `src/`, `tests/`, `pyproject.toml`, `Dockerfile`, or `uv.lock` yet.

Phase 0 (smoke-test the three Qwen 3.5 sizes against real hardware) has not run; Phase 1 (first code slice) has not started. When writing new code, create the layout described in `PLAN.md` (Folder Structure section) rather than inferring a structure. Do not invent tooling — the stack is fixed (see below) and decisions about deviation belong in an ADR or the decision log.

Use `docs/evaluation-checklist.md` to log Phase 0 smoke-test results, sampling observations, experiment data, adversarial evaluation findings, and cost analysis inputs as they are produced.

## Stack (fixed by ADR 0001)

- **Language:** Python (≥3.11)
- **UI:** Gradio `gr.Blocks` with tabs (Triage, Metrics, Traces, Experiments)
- **API:** FastAPI as outer app with Gradio mounted as sub-application (see ADR 0006 addendum) — Gradio is not running standalone
- **Local inference:** Ollama on the host, reached via the `openai` Python client pointed at `http://localhost:11434/v1`. Model discovery uses the `ollama` Python client.
- **Schema validation:** `pydantic` (this is architectural, not an implementation detail — see ADR 0002)
- **Storage:** SQLite (stdlib `sqlite3`, no ORM) with a single `traces` table and a repository pattern — see ADR 0005
- **Deps:** `uv` (source of truth is `pyproject.toml`)
- **Testing:** `pytest` (≥80% coverage on changed code)
- **Lint/format:** `ruff`
- **ADRs:** `adr-tools` format; `.adr-dir` points at `docs/adr`

If you're tempted to reach for SQLAlchemy, Streamlit, a REST-only split, LangChain, Instructor, or Outlines — **stop and check the relevant ADR first**. Each was considered and rejected with reasoning that's worth re-reading before overriding.

## Commands (planned — will apply once Phase 1 lands)

Confirm they exist in `pyproject.toml` / `Dockerfile` before relying on them.

```bash
# Install / sync deps
uv sync

# Run the app natively (FastAPI + Gradio on :7860, Ollama on host :11434)
uv run python -m ticket_triage_llm.app

# Run in Docker (app container only — Ollama stays on host)
docker build -t ticket-triage-llm .
docker run --rm -p 7860:7860 -v "$PWD/data:/app/data" ticket-triage-llm

# Tests
uv run pytest                          # full suite
uv run pytest tests/unit                # unit only
uv run pytest -k test_name_substring    # single test by name
uv run pytest --cov=ticket_triage_llm --cov-fail-under=80

# Lint / format
uv run ruff check .
uv run ruff format .

# Eval runners (entry points are planned; each is invoked directly, bypassing UI)
uv run python -m ticket_triage_llm.eval.runners.run_local_comparison
uv run python -m ticket_triage_llm.eval.runners.run_validation_impact
uv run python -m ticket_triage_llm.eval.runners.run_prompt_comparison
uv run python -m ticket_triage_llm.eval.runners.summarize_results

# Ollama prerequisites (must be pulled on the host before the app works)
ollama pull qwen3.5:2b
ollama pull qwen3.5:4b
ollama pull qwen3.5:9b

# ADRs (adr-tools convention — new ADRs auto-increment in docs/adr/)
adr new "<title>"
```

## High-level architecture

The system is a **single-process Python app** that ingests a raw support ticket and returns a validated `TriageOutput` (or a typed `TriageFailure`). Read `docs/architecture.md` for the pipeline diagram; the three principles below are non-negotiable.

### 1. Validator-first pipeline with bounded retry (ADR 0002, ADR 0003)

All model output is **untrusted until validated**. Every request flows through:

```
input_validation → guardrail → prompt_builder → provider → LLM
                                                             ↓
   trace ← TriageResult ← semantic_checks ← schema ← json_parse
                              ↑                ↑        ↑
                              └── retry once ──┴────────┘
                                 (single repair prompt)
```

- **Exactly one retry** on any validation failure, using a *repair* prompt (`prompts/repair_json_v1.py`) that includes the failed output and the specific error — not a plain re-send.
- On unrecoverable failure, the pipeline returns a typed `TriageFailure` with one of `guardrail_blocked | model_unreachable | parse_failure | schema_failure | semantic_failure`. It **never** returns malformed data and **never** raises an uncaught exception to consumers.
- The pipeline's consumer contract is a discriminated union `TriageResult = TriageSuccess | TriageFailure`. Callers pattern-match on the tag; they do not try/except.

### 2. Provider abstraction via Python Protocol (ADR 0004)

`LlmProvider` is a `Protocol` (structural typing), not an ABC. The pipeline depends on `LlmProvider` and never imports a concrete provider. `OllamaQwenProvider` is parameterized by model name — one class, three instances (`qwen3.5:2b`, `qwen3.5:4b`, `qwen3.5:9b`). `CloudQwenProvider` exists as a `NotImplementedError` placeholder to prove the abstraction is real.

Consequence: the eval runner iterates over a `list[LlmProvider]` and runs the same suite against each. The Triage tab's dropdown is populated from `provider_router`'s registry. **Do not add `if provider == "ollama": ...` branches in service code** — that re-couples what the Protocol exists to decouple.

### 3. Traces are the single source of truth (ADR 0005)

One SQLite table: `traces`. Benchmark summaries, KPI cards, live rolling metrics, category-drift indicators — **all computed from traces on the fly**, never stored separately. If you find yourself designing a `benchmarks` or `summaries` table, stop — that's the anti-pattern ADR 0005 explicitly rules out.

Every trace carries an optional `run_id` (null for live Triage-tab traffic, populated for eval-runner traffic). That's the grouping key that makes experiment comparison possible.

### 4. Monitoring is distinct from benchmarking (ADR 0009)

The Metrics tab is two clearly labeled sections: **Benchmark Results** (static, from `run_id`-tagged traces) and **Live Metrics** (rolling time-series from all traces). Do not merge them into one undifferentiated "dashboard" view — the distinction is itself a graded piece of the project.

Alerting is **log-based only** (structured `WARN [monitoring] threshold_breached: ...` entries). No Prometheus, no PagerDuty — those are listed as future work in `docs/future-improvements.md`.

### 5. Three-layer injection defense (`docs/threat-model.md`, ADR 0008)

1. **Pre-LLM guardrail** — heuristic pattern matching (`pass`/`warn`/`block`), returns `matched_rules` for per-rule analysis
2. **Prompt structural separation** — ticket body wrapped in explicit delimiters with instructions to treat the content as data
3. **Post-LLM output validation** — the same validator-first pipeline from ADR 0002

The guardrail is deliberately **heuristic-only** as a baseline. The expected finding — "pattern matching catches direct injection but fails on obfuscated attacks" — is itself a deliverable. Do not upgrade the guardrail to an LLM-based classifier without running the baseline adversarial eval first; the comparison only works if the baseline numbers exist.

### Deployment split (ADR 0007)

Docker builds the **app container only**. Ollama runs **natively on the host** because Docker Desktop on Mac/Windows has no Apple GPU access — containerizing Ollama would force CPU-only inference and defeat the consumer-hardware thesis. The container reaches Ollama at `host.docker.internal:11434` (Mac/Windows) or via `--network=host` (Linux). The Ollama endpoint URL must be configurable via env var.

## Repository conventions

### Conventional commits + no co-author tags

Use Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`, `perf:`, `ci:`). **Do not** add `Co-Authored-By:` trailers, `Generated-with-Claude`, or any AI-attribution line in commits, PRs, or docs — this is an explicit rule from the global engineering guide and overrides any Claude-default behavior.

### GitFlow

Branches: `main` (prod-ready), `develop` (integration), `feature/*`, `release/*`, `hotfix/*`. **No direct commits to `main` or `develop`.** The repo currently commits to `main` because it's pre-implementation; once Phase 1 starts, the feature-branch discipline kicks in.

### Decisions go in the right store

- **Architectural** ("how is the system built") → new ADR in `docs/adr/` via `adr new`. Status `Proposed` → `Accepted`; amend existing ADRs only via addenda (see ADR 0006) or a superseding ADR.
- **Scope / framing / strategy** ("what is the project, what's in, what's out, why") → append to `docs/decisions/decision-log.md` **at the top** (newest-first), dated.

`docs/adr/README.md` is the index — keep it in sync when adding an ADR.

### Docs cross-reference heavily

`PLAN.md` is the map; `architecture.md` / `threat-model.md` / `evaluation-plan.md` / `tradeoffs.md` / `cost-analysis.md` / `future-improvements.md` are the territory. ADRs link to each other and to the decision log. When editing any of these, check for inbound links from the others and update them — stale cross-references in this project are especially costly because the docs *are* the current deliverable.

### Reference materials

`docs/archive/` contains the original project plan (pre-revision) and the Final Project Rubric. These are read-only reference material — do not modify them.

### Other agent context

`.remember/` is used by another coding LLM for its own context. Do not modify, delete, or conflict with files in this directory.

## Hardware & model constraints

- Target: **MacBook Pro M4 Pro, 24GB unified memory**. Models that exceed that envelope (Qwen 3.5 27B, 35B-A3B, anything requiring 32GB+) are excluded by design — this is a feature, not a workaround. See `docs/tradeoffs.md` ("Model quality vs hardware constraint").
- Model family is **Qwen 3.5** specifically (not 3.0 — see OD-1 in the decision log, and not other families — see ADR 0001).
- Sampling defaults are **conservative for structured JSON output**: temperature 0.1–0.3, top-p 0.85–0.9, top-k 40, repetition penalty disabled (1.0). These are starting values; changing them needs a decision-log entry.

## Where to look first when you're asked to...

| Task | Start here |
|---|---|
| Add a new architectural decision | `docs/adr/README.md` (index), then `adr new "title"` |
| Understand a pipeline behavior | `docs/architecture.md` → relevant ADR → `docs/threat-model.md` if it's injection-related |
| Add a failure category | ADR 0003 (error contract) — updating `Literal` requires updating every exhaustive match |
| Touch the provider layer | ADR 0004 — do not reintroduce branching on provider name |
| Store new per-request data | ADR 0005 — extend `TraceRecord` and the `traces` table, never add a second table for "summaries" |
| Change the UI layout | ADR 0006 (+ its FastAPI addendum) |
| Change the guardrail | ADR 0008 — measure before and after against the adversarial set |
| Add a dashboard chart | ADR 0009 — decide whether it's Benchmark Results or Live Metrics before picking a component |
| Change deployment story | ADR 0007 — the Ollama-on-host split is load-bearing for GPU acceleration |
| Log experiment results or smoke-test data | `docs/evaluation-checklist.md` — fill in tables as each phase produces data |
| Defer a feature | Append to `docs/future-improvements.md` with effort estimate + rationale |
