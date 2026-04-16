# 0005. SQLite for trace storage with repository pattern

## Status

Accepted

## Context

The triage pipeline produces data that must survive beyond a single request and beyond a single process lifecycle. Specifically:

**Why the system needs persistent storage at all:**

1. **Trace records** — every triage request (whether from the Triage tab or the eval runner) produces a trace: request ID, ticket hash, model, provider, prompt version, guardrail result, validation status, semantic check status, retry count, latency, token counts, tokens/sec, estimated cost, failure category (if applicable), and timestamp. These traces serve three purposes:
   - **Evaluation:** the eval runner tags traces with a `run_id` so that experiment results can be grouped, compared, and reproduced. Without persistence, closing the app loses all experiment data.
   - **Monitoring:** the live monitoring dashboard queries recent traces to compute rolling latency trends, error rates, and category distribution drift. Without persistence, refreshing the page loses the monitoring window.
   - **Demo evidence:** the instructor needs to see traces from multiple runs side-by-side during the demo. If traces only live in memory, the demo depends on never restarting the app.

2. **No separate summary storage.** Benchmark summaries (accuracy, avg latency, retry rate, etc.) are *not* stored as their own records. They are computed on the fly from the trace records by the metrics service, grouped by `run_id`, provider, prompt version, or time window as needed. The trace records are the single source of truth. This avoids the risk of summary data drifting out of sync with the underlying traces and keeps the storage schema simple.

**What the storage system needs to support:**

- Insert a trace record on every triage request (including during eval runs of 25–30+ tickets per experiment)
- Query traces by `run_id`, by provider, by prompt version, by time window, by validation status, and by combinations of these
- Survive process restarts (the app can be stopped and restarted without losing data)
- Work inside a Docker container and on any platform (macOS, Windows, Linux)
- Require zero external infrastructure setup (no database server to install, configure, or maintain)

## Options Considered

### Option A: SQLite with a repository pattern

A single SQLite database file stored in the project's data directory. A thin `TraceRepository` class encapsulates all SQL and exposes typed Python methods to the service layer. No ORM. The metrics service queries through the repository to compute summaries on the fly.

### Option B: Flat JSON files

Write traces as JSON files (one per request or one per run) to a directory. Read them back by scanning the directory.

### Option C: In-memory only (no persistence)

Store traces in a Python list or dict. All data is lost when the process exits.

### Option D: PostgreSQL

Run a PostgreSQL server alongside the app. Access via psycopg2 or SQLAlchemy.

### Option E: SQLAlchemy ORM over SQLite

Use SQLAlchemy's ORM layer to define models and manage the SQLite database, rather than writing SQL directly.

## Decision

We chose **Option A: SQLite with a repository pattern**.

The storage layer consists of:

- **`storage/db.py`** — connection management and schema creation. Creates the SQLite file and the `traces` table on first run. Uses `sqlite3` from the Python standard library.
- **`storage/trace_repo.py`** — the single repository class. Encapsulates all SQL. Exposes typed methods:
  - `save_trace(trace: TraceRecord) -> None`
  - `get_traces_by_run(run_id: str) -> list[TraceRecord]`
  - `get_traces_by_provider(provider: str) -> list[TraceRecord]`
  - `get_traces_since(since: datetime) -> list[TraceRecord]`
  - `get_recent_traces(limit: int) -> list[TraceRecord]`
  - `get_all_traces() -> list[TraceRecord]`
  - and filtered variants as needed

The metrics service calls these methods and computes aggregate summaries (accuracy, avg/p50/p95 latency, retry rate, etc.) in Python from the returned trace records. No aggregate queries are pushed to SQLite; the dataset scale (hundreds to low thousands of traces) makes in-Python aggregation fast enough that there is no performance reason to push it to SQL.

The `traces` table schema mirrors the `TraceRecord` pydantic model with appropriate indexes on `run_id`, `provider`, `prompt_version`, and `timestamp` for the most common query patterns.

## Rationale

1. **SQLite requires zero infrastructure.** It ships with Python (`sqlite3` is in the standard library). There is nothing to install, nothing to configure, no server to start, no port to expose, no credentials to manage. The database is a single file. This fits the project's consumer-hardware thesis and the Docker deployment model — the container runs without any external database dependency.

2. **SQLite is more than sufficient for this data scale.** The project will produce at most a few thousand trace records (4 experiments × 3 models × ~35 tickets per run = ~420 traces from the eval, plus live traffic traces). SQLite comfortably handles millions of rows; hundreds are trivial. There is no performance justification for a heavier database.

3. **SQLite survives process restarts and works inside Docker.** The database file persists on disk. Mounting it as a Docker volume means traces survive container rebuilds. In-memory storage (Option C) would lose all data on restart, which breaks the demo scenario where the instructor wants to see traces from earlier runs.

4. **The repository pattern keeps SQL out of service code.** The metrics service and the UI tabs never write SQL. They call typed Python methods on `TraceRepository` and get back `TraceRecord` objects. This makes the service layer independently testable (inject a fake repository) and means the storage implementation could be swapped (to PostgreSQL, to a cloud database, to flat files) without changing any service or UI code. The repository is the boundary.

5. **No ORM because the schema is one table.** SQLAlchemy's value proposition is managing complex relational schemas with migrations, relationships, and query composition. This project has one table with a flat schema. An ORM would add a dependency, a learning curve (if unfamiliar), and a layer of abstraction that provides no benefit at this scale. Raw `sqlite3` with parameterized queries is simpler, more transparent, and sufficient.

6. **Summaries are computed, not stored, because traces are the single source of truth.** If summaries were stored separately, they could drift out of sync with the underlying traces (a trace is deleted or corrected but the summary isn't updated). Computing summaries on the fly from tagged traces eliminates this risk and keeps the schema to one table. The computational cost of aggregating a few hundred records in Python is negligible.

## Tradeoffs

- **Upside:** Zero infrastructure dependencies, single-file database, standard library only, trivially portable across platforms, survives restarts, works in Docker, simple schema, repository pattern enables clean separation and testability.

- **Downside:** SQLite has limited concurrency support (one writer at a time). It does not support concurrent writes from multiple processes. Aggregation is done in Python rather than in SQL, which would not scale to millions of records.

- **Why we accept the downside:** The project is a single-process Gradio app. There is never more than one writer. The data scale is hundreds of records, not millions. Both limitations would matter for a real production service at scale; neither matters for a single-instance demo system on consumer hardware. These limitations are documented honestly in `docs/tradeoffs.md` (forthcoming) as things that would need to change if the system were scaled up.

## Consequences

- The `traces` table is the only table in the database. There is no `benchmarks` or `metrics` table. All summary data is derived from traces at query time.

- Every trace is tagged with a `run_id` (nullable — live traffic traces from the Triage tab have no run_id; eval runner traces do). This is the grouping key that makes experiment comparison possible.

- The database file location is configurable via environment variable (defaulting to `data/traces.db` relative to the project root). The `.gitignore` excludes the `data/` directory so that database files are not committed.

- For Docker deployment, the `data/` directory should be mounted as a volume so traces persist across container restarts.

- The `TraceRepository` is the only code in the project that imports `sqlite3`. All other code interacts with traces through the repository's typed interface. This is enforced by code review and by the convention that service code imports from `storage/trace_repo.py`, never from `sqlite3` directly.

- If the project were later scaled to a multi-process or multi-instance deployment, SQLite would need to be replaced with a database that supports concurrent writes (PostgreSQL, for example). The repository pattern makes this swap a localized change — only `trace_repo.py` and `db.py` need to change; the service layer and UI are unaffected.

## Alternatives Not Chosen

- **Option B (flat JSON files):** rejected because file-per-trace creates filesystem clutter at scale, file-per-run loses per-request granularity, querying across files requires loading and parsing all of them, and there is no transactional safety (a crash mid-write can corrupt a file). SQLite solves all four of these problems for zero additional complexity.

- **Option C (in-memory only):** rejected because it loses all data on process restart. The demo scenario requires traces from earlier runs to be visible, the monitoring dashboard requires a history window, and the eval runner produces data that must survive beyond the runner's execution. Persistence is not optional.

- **Option D (PostgreSQL):** rejected because it requires installing and running a database server, which violates the project's zero-infrastructure-dependency goal and complicates both the native and Docker deployment paths. PostgreSQL's advantages (concurrent writes, advanced query capabilities, replication) are not relevant at this project's data scale.

- **Option E (SQLAlchemy ORM):** rejected because the schema is one table with a flat structure. An ORM adds a dependency, an abstraction layer, and a learning curve without providing any benefit that raw `sqlite3` doesn't already provide. If the schema were more complex (multiple related tables, migrations, foreign keys), an ORM would be justified. For one table, it is overhead.
