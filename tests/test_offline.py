"""Replay the real archived observations with no API calls and isolated outputs."""

from dataclasses import replace
from pathlib import Path
import hashlib
import json
import shutil

import nbformat
import pandas as pd
import pytest
import requests

from macro_pipeline.db import read_dataset
from macro_pipeline.offline import load_snapshot, restore_snapshot
from macro_pipeline.reporting import execute_analysis
from macro_pipeline.transform import QualityError

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "snapshots/manifest.json"


def test_real_snapshot_rebuild_matches_submitted_data_without_api(settings, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline replay must not make HTTP requests")
    monkeypatch.setattr(requests.Session, "request", forbidden)
    result = restore_snapshot(replace(settings, api_key=""), MANIFEST)
    frame, run = read_dataset(settings.db_path)
    expected = pd.read_csv(ROOT / "reports/monthly_indicators.csv", index_col="date", parse_dates=["date"])
    pd.testing.assert_frame_equal(frame, expected, check_freq=False, check_exact=False, rtol=1e-12)
    assert result["mode"] == "offline" and run["as_of"] == "2026-11-08"
    assert len(frame) == 322


def test_corrupt_snapshot_is_rejected_before_database_creation(settings, tmp_path):
    archive = tmp_path / "archive"
    shutil.copytree(ROOT / "snapshots", archive)
    manifest = json.loads((archive / "manifest.json").read_text())
    with (archive / manifest["file"]).open("ab") as handle:
        handle.write(b"tampered")
    with pytest.raises(QualityError, match="checksum"):
        restore_snapshot(settings, archive / "manifest.json")
    assert not settings.db_path.exists()


def test_snapshot_manifest_cannot_escape_archive(tmp_path):
    manifest = json.loads(MANIFEST.read_text())
    manifest["file"] = "../outside.json"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(QualityError, match="inside"):
        load_snapshot(path)


def test_offline_notebook_outputs_are_separate(settings, tmp_path, monkeypatch):
    monkeypatch.setenv("MACRO_OFFLINE", "1")
    result = restore_snapshot(replace(settings, api_key=""), MANIFEST)
    source = ROOT / "notebooks/01_macroeconomic_eda.ipynb"
    original = source.read_bytes()
    output = tmp_path / "offline-reports"
    executed = output / source.name
    manifest = execute_analysis(settings, source, output, expected_run_id=result["run_id"], published_notebook_path=executed)
    assert source.read_bytes() == original
    assert manifest["executed_code_cells"] == 11
    assert hashlib.sha256(executed.read_bytes()).hexdigest() == manifest["notebook"]["sha256"]
    assert "Archived snapshot reproduction" in (output / "eda.html").read_text()
    cells = [c for c in nbformat.read(executed, as_version=4).cells if c.cell_type == "code"]
    assert all(c.execution_count and all(o.output_type != "error" for o in c.outputs) for c in cells)
