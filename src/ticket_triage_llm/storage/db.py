import sqlite3


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.Connection(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS traces (
            request_id TEXT PRIMARY KEY,
            run_id TEXT,
            timestamp TEXT NOT NULL,
            model TEXT NOT NULL,
            provider TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            ticket_body TEXT NOT NULL,
            guardrail_result TEXT NOT NULL
                CHECK (guardrail_result IN ('pass', 'warn', 'block')),
            guardrail_matched_rules TEXT NOT NULL DEFAULT '[]',
            validation_status TEXT NOT NULL
                CHECK (validation_status IN (
                    'valid', 'valid_after_retry', 'invalid', 'skipped'
                )),
            retry_count INTEGER NOT NULL DEFAULT 0,
            latency_ms REAL NOT NULL,
            tokens_input INTEGER NOT NULL DEFAULT 0,
            tokens_output INTEGER NOT NULL DEFAULT 0,
            tokens_total INTEGER NOT NULL DEFAULT 0,
            tokens_per_second REAL,
            estimated_cost REAL NOT NULL DEFAULT 0.0,
            status TEXT NOT NULL
                CHECK (status IN ('success', 'failure')),
            failure_category TEXT
                CHECK (failure_category IS NULL OR failure_category IN (
                    'guardrail_blocked', 'model_unreachable',
                    'parse_failure', 'schema_failure', 'semantic_failure'
                )),
            raw_model_output TEXT,
            triage_output_json TEXT,
            CHECK (
                (status = 'success' AND failure_category IS NULL)
                OR (status = 'failure' AND failure_category IS NOT NULL)
            )
        );

        CREATE INDEX IF NOT EXISTS idx_traces_run_id
            ON traces(run_id);
        CREATE INDEX IF NOT EXISTS idx_traces_provider
            ON traces(provider);
        CREATE INDEX IF NOT EXISTS idx_traces_prompt_version
            ON traces(prompt_version);
        CREATE INDEX IF NOT EXISTS idx_traces_timestamp
            ON traces(timestamp);
    """)
