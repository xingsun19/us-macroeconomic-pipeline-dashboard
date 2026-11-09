"""Shared stages used by both the CLI and the actual Airflow DAG."""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
import hashlib
import json
import uuid

import pandas as pd

from .config import Settings, SERIES, WARMUP_DATE
from .db import MONTHLY_COLUMNS, connect, initialize, read_dataset
from .fred import FredClient
from .transform import QualityError, clean_monthly, validate_monthly


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def stage(settings, run_id, name, *, fail_run=True):
    start = perf_counter()
    with connect(settings.db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO pipeline_steps VALUES (?, ?, ?, NULL, NULL, 'RUNNING')", (run_id, name, now()))
    try:
        yield
    except Exception as exc:
        # Store only the exception class: request errors can otherwise include API keys.
        with connect(settings.db_path) as conn:
            if fail_run:
                conn.execute("UPDATE pipeline_runs SET status='FAILED', error_type=?, completed_at=? WHERE run_id=?", (type(exc).__name__, now(), run_id))
            conn.execute("UPDATE pipeline_steps SET status='FAILED', completed_at=?, duration_seconds=? WHERE run_id=? AND stage=?", (now(), perf_counter()-start, run_id, name))
        raise
    else:
        with connect(settings.db_path) as conn:
            conn.execute("UPDATE pipeline_steps SET status='SUCCESS', completed_at=?, duration_seconds=? WHERE run_id=? AND stage=?", (now(), perf_counter()-start, run_id, name))


def get_run(settings, run_id):
    with connect(settings.db_path, readonly=True) as conn:
        result = conn.execute("SELECT * FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
    if result is None:
        raise QualityError("Unknown pipeline run.")
    return dict(result)


def extract(settings: Settings, run_id=None, client=None):
    initialize(settings.db_path)
    run_id = run_id or uuid.uuid4().hex
    # IDs may be passed by a scheduler; never allow a path component from caller input.
    if not run_id.isalnum() or len(run_id) > 64:
        raise ValueError("Run IDs must be alphanumeric and at most 64 characters.")
    with connect(settings.db_path) as conn:
        conn.execute("INSERT OR IGNORE INTO pipeline_runs(run_id, started_at, as_of, status) VALUES (?, ?, ?, 'RUNNING')", (run_id, now(), settings.as_of.isoformat()))
    existing = get_run(settings, run_id)
    if existing["raw_sha256"]:
        return run_id  # Retry reuses the same successful extraction snapshot.
    with stage(settings, run_id, "extract_api"):
        client = client or FredClient(settings.api_key)
        end = existing["as_of"]
        payload = {"schema_version": 1, "as_of": end, "fetched_at": now(), "series": {sid: client.fetch_series(sid, WARMUP_DATE, end) for sid in SERIES}}
        content = json.dumps(payload, sort_keys=True, allow_nan=False).encode()
        dest = settings.data_dir / "raw" / f"{run_id}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp = dest.with_suffix(".tmp")
        temp.write_bytes(content)
        temp.replace(dest)
        with connect(settings.db_path) as conn:
            conn.execute("UPDATE pipeline_runs SET raw_path=?, raw_sha256=?, status='EXTRACTED', error_type=NULL WHERE run_id=?", (str(dest.resolve()), hashlib.sha256(content).hexdigest(), run_id))
    return run_id


def store_raw(settings, run_id):
    with stage(settings, run_id, "store_raw"):
        run = get_run(settings, run_id)
        content = Path(run["raw_path"]).read_bytes()
        if hashlib.sha256(content).hexdigest() != run["raw_sha256"]:
            raise QualityError("Raw snapshot checksum mismatch.")
        payload = json.loads(content)
        if set(payload["series"]) != set(SERIES):
            raise QualityError("Incomplete raw snapshot.")
        with connect(settings.db_path) as conn:
            conn.execute("DELETE FROM raw_observations WHERE run_id=?", (run_id,))
            for sid, source in payload["series"].items():
                conn.execute("INSERT OR REPLACE INTO raw_payloads VALUES (?, ?, ?, ?)", (run_id, sid, json.dumps(source["metadata"]), json.dumps(source["observations"])))
                unique = {}
                for obs in source["observations"]:
                    if obs["date"] in unique and unique[obs["date"]][3] != obs["value"]:
                        raise QualityError("Conflicting duplicate observations in API response.")
                    unique[obs["date"]] = (run_id, sid, obs["date"], obs["value"], obs.get("realtime_start"), obs.get("realtime_end"))
                conn.executemany("INSERT INTO raw_observations VALUES (?, ?, ?, ?, ?, ?)", unique.values())
            conn.execute("UPDATE pipeline_runs SET status='RAW_STORED', error_type=NULL WHERE run_id=?", (run_id,))
    return run_id


def clean(settings, run_id):
    with stage(settings, run_id, "clean_transform"):
        with connect(settings.db_path, readonly=True) as conn:
            raw = pd.read_sql_query("SELECT series_id, date, value_text FROM raw_observations WHERE run_id=? ORDER BY series_id, date", conn, params=(run_id,))
        frame = clean_monthly(raw, get_run(settings, run_id)["as_of"])
        frame["date"] = frame.date.dt.strftime("%Y-%m-%d")
        records = frame.astype(object).where(frame.notna(), None).itertuples(index=False, name=None)
        with connect(settings.db_path) as conn:
            conn.execute("DELETE FROM staged_monthly WHERE run_id=?", (run_id,))
            conn.executemany(f"INSERT INTO staged_monthly VALUES ({','.join('?' for _ in range(len(MONTHLY_COLUMNS)+1))})", ((run_id, *row) for row in records))
            conn.execute("UPDATE pipeline_runs SET status='CLEANED', error_type=NULL WHERE run_id=?", (run_id,))
    return run_id


def validate(settings, run_id):
    with stage(settings, run_id, "validate_quality"):
        with connect(settings.db_path, readonly=True) as conn:
            frame = pd.read_sql_query("SELECT * FROM staged_monthly WHERE run_id=? ORDER BY date", conn, params=(run_id,))
        summary = validate_monthly(frame, get_run(settings, run_id)["as_of"])
        with connect(settings.db_path) as conn:
            conn.execute("UPDATE pipeline_runs SET status='VALIDATED', validation_json=?, error_type=NULL WHERE run_id=?", (json.dumps(summary), run_id))
    return run_id


def publish(settings, run_id):
    with stage(settings, run_id, "publish_database"):
        with connect(settings.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            run = conn.execute("SELECT * FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
            if run["status"] == "SUCCESS":
                return run_id  # Publishing the same run is idempotent.
            if run["status"] != "VALIDATED":
                raise QualityError("Only a validated snapshot can be published.")
            current = conn.execute("SELECT r.as_of, r.started_at FROM dataset_state s JOIN pipeline_runs r USING(run_id)").fetchone()
            if current and (run["as_of"] < current["as_of"] or run["started_at"] < current["started_at"]):
                raise QualityError("An older run cannot overwrite a newer published snapshot.")
            cols = ','.join(MONTHLY_COLUMNS)
            conn.execute("DELETE FROM monthly_indicators")
            conn.execute(f"INSERT INTO monthly_indicators({cols}) SELECT {cols} FROM staged_monthly WHERE run_id=?", (run_id,))
            conn.execute("INSERT OR REPLACE INTO dataset_state VALUES (1, ?, ?)", (run_id, now()))
            conn.execute("UPDATE pipeline_runs SET status='SUCCESS', completed_at=?, error_type=NULL WHERE run_id=?", (now(), run_id))
    return run_id


def verify(settings, run_id):
    with stage(settings, run_id, "verify_update"):
        frame, run = read_dataset(settings.db_path)
        if run["run_id"] != run_id:
            raise QualityError("The published run differs from the expected run.")
        validate_monthly(frame.reset_index(), run["as_of"])
    return json.loads(get_run(settings, run_id)["validation_json"])


def run_pipeline(settings=None, client=None):
    settings = settings or Settings.from_env()
    run_id = extract(settings, client=client)
    for fn in (store_raw, clean, validate, publish):
        fn(settings, run_id)
    return {"run_id": run_id, **verify(settings, run_id)}
