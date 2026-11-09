"""SQLite schema, short-lived connections, and read-only dashboard access."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3

import pandas as pd

VALUE_COLUMNS = ["unrate", "cpiaucsl", "fedfunds", "cpi_yoy", "cpi_mom", "unrate_change_pp", "fedfunds_change_pp", "real_rate_proxy"]
STATUS_COLUMNS = ["unrate_status", "cpiaucsl_status", "fedfunds_status"]
MONTHLY_COLUMNS = ["date", *VALUE_COLUMNS, *STATUS_COLUMNS]
MONTHLY_FIELDS = """
    date TEXT NOT NULL,
    unrate REAL, cpiaucsl REAL, fedfunds REAL,
    cpi_yoy REAL, cpi_mom REAL,
    unrate_change_pp REAL, fedfunds_change_pp REAL, real_rate_proxy REAL,
    unrate_status TEXT NOT NULL, cpiaucsl_status TEXT NOT NULL, fedfunds_status TEXT NOT NULL
"""
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, completed_at TEXT,
    as_of TEXT NOT NULL, status TEXT NOT NULL,
    raw_path TEXT, raw_sha256 TEXT, validation_json TEXT, error_type TEXT
);
CREATE TABLE IF NOT EXISTS pipeline_steps (
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id), stage TEXT NOT NULL,
    started_at TEXT NOT NULL, completed_at TEXT, duration_seconds REAL, status TEXT NOT NULL,
    PRIMARY KEY (run_id, stage)
);
CREATE TABLE IF NOT EXISTS raw_payloads (
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id), series_id TEXT NOT NULL,
    metadata_json TEXT NOT NULL, observations_json TEXT NOT NULL,
    PRIMARY KEY (run_id, series_id)
);
CREATE TABLE IF NOT EXISTS raw_observations (
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id), series_id TEXT NOT NULL,
    date TEXT NOT NULL, value_text TEXT NOT NULL,
    realtime_start TEXT, realtime_end TEXT,
    PRIMARY KEY (run_id, series_id, date)
);
CREATE INDEX IF NOT EXISTS idx_raw_series_date ON raw_observations(series_id, date);
CREATE TABLE IF NOT EXISTS staged_monthly (
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id), {MONTHLY_FIELDS}, PRIMARY KEY (run_id, date)
);
CREATE TABLE IF NOT EXISTS monthly_indicators ({MONTHLY_FIELDS}, PRIMARY KEY (date));
CREATE TABLE IF NOT EXISTS dataset_state (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id), published_at TEXT NOT NULL
);
PRAGMA user_version = 1;
"""


@contextmanager
def connect(path: Path, readonly=False):
    path = Path(path).resolve()
    if readonly:
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=30)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
        if not readonly:
            conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize(path):
    with connect(path) as conn:
        conn.executescript(SCHEMA)


def read_dataset(path):
    with connect(path, readonly=True) as conn:
        # Both reads share a snapshot, even if an update publishes concurrently.
        conn.execute("BEGIN")
        frame = pd.read_sql_query("SELECT * FROM monthly_indicators ORDER BY date", conn, parse_dates=["date"])
        run = conn.execute("SELECT r.*, s.published_at FROM dataset_state s JOIN pipeline_runs r USING (run_id)").fetchone()
    if frame.empty or run is None:
        raise ValueError("No published data. Run macro-pipeline update first.")
    return frame.set_index("date"), dict(run)
