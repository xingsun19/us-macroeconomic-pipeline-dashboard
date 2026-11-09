from dataclasses import replace
from datetime import date
import json

import pandas as pd
import pytest

from macro_pipeline.db import connect, read_dataset
from macro_pipeline import pipeline
from macro_pipeline.transform import QualityError


def test_end_to_end_idempotency_and_revision(settings, client):
    first = pipeline.run_pipeline(settings, client)
    before, _ = read_dataset(settings.db_path)
    second = pipeline.run_pipeline(settings, client)
    after, _ = read_dataset(settings.db_path)
    pd.testing.assert_frame_equal(before, after)
    assert first["run_id"] != second["run_id"]
    client.payloads["UNRATE"]["observations"][20]["value"] = "7.7"
    third = pipeline.run_pipeline(settings, client)
    revised, _ = read_dataset(settings.db_path)
    assert revised.loc["2000-09-01", "unrate"] == 7.7
    assert len(revised) == first["rows"]
    with connect(settings.db_path, readonly=True) as conn:
        assert conn.execute("SELECT count(*) FROM pipeline_runs WHERE status='SUCCESS'").fetchone()[0] == 3
        assert conn.execute("SELECT count(*) FROM pipeline_steps WHERE run_id=? AND status='SUCCESS'", (third["run_id"],)).fetchone()[0] == 6


def test_bad_update_preserves_published_snapshot(settings, client):
    first = pipeline.run_pipeline(settings, client)
    before, _ = read_dataset(settings.db_path)
    client.payloads["UNRATE"]["observations"][30]["value"] = "101"
    with pytest.raises(QualityError):
        pipeline.run_pipeline(settings, client)
    after, run = read_dataset(settings.db_path)
    pd.testing.assert_frame_equal(before, after)
    assert run["run_id"] == first["run_id"]
    with connect(settings.db_path, readonly=True) as conn:
        assert conn.execute("SELECT count(*) FROM pipeline_runs WHERE status='FAILED'").fetchone()[0] == 1


def test_network_failure_retains_previous_data(settings, client):
    pipeline.run_pipeline(settings, client)
    before, _ = read_dataset(settings.db_path)
    class BrokenClient:
        def fetch_series(self, *args):
            raise RuntimeError("Test service outage")
    with pytest.raises(RuntimeError):
        pipeline.run_pipeline(settings, BrokenClient())
    after, _ = read_dataset(settings.db_path)
    pd.testing.assert_frame_equal(before, after)


def test_checksum_prevents_tampered_raw_import(settings, client):
    run_id = pipeline.extract(settings, client=client)
    path = settings.data_dir / "raw" / f"{run_id}.json"
    path.write_text(path.read_text() + " ")
    with pytest.raises(QualityError, match="checksum"):
        pipeline.store_raw(settings, run_id)


def test_stages_can_be_retried_without_duplicate_rows(settings, client):
    rid = pipeline.extract(settings, run_id="retry123", client=client)
    assert pipeline.extract(settings, run_id=rid, client=client) == rid
    for fn in [pipeline.store_raw, pipeline.clean, pipeline.validate]:
        fn(settings, rid)
        fn(settings, rid)
    pipeline.publish(settings, rid)
    pipeline.publish(settings, rid)
    assert pipeline.verify(settings, rid)["rows"] == 294


def test_publish_requires_validation(settings, client):
    rid = pipeline.extract(settings, client=client)
    pipeline.store_raw(settings, rid)
    pipeline.clean(settings, rid)
    with pytest.raises(QualityError, match="validated"):
        pipeline.publish(settings, rid)


def test_older_snapshot_cannot_replace_newer(settings, client):
    pipeline.run_pipeline(settings, client)
    older = replace(settings, as_of=date(2024, 7, 1))
    with pytest.raises(QualityError, match="older run"):
        pipeline.run_pipeline(older, client)


def test_transaction_rollback(settings, client):
    pipeline.run_pipeline(settings, client)
    before, _ = read_dataset(settings.db_path)
    with pytest.raises(RuntimeError):
        with connect(settings.db_path) as conn:
            conn.execute("DELETE FROM monthly_indicators")
            raise RuntimeError("Simulated writer crash")
    after, _ = read_dataset(settings.db_path)
    pd.testing.assert_frame_equal(before, after)


def test_source_missing_is_preserved_end_to_end(settings, client):
    client.payloads["CPIAUCSL"]["observations"][-3]["value"] = "."
    result = pipeline.run_pipeline(settings, client)
    frame, _ = read_dataset(settings.db_path)
    assert pd.isna(frame.cpiaucsl.iloc[-3])
    assert result["series"]["cpiaucsl"]["source_missing"] == 1
