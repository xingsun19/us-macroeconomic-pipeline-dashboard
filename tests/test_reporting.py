"""Exercise actual kernel execution, failure isolation, and report provenance."""

from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

import nbformat
import pandas as pd
import pytest

from macro_pipeline.db import connect, read_dataset
from macro_pipeline.pipeline import run_pipeline
from macro_pipeline.reporting import REPORT_FILES, execute_analysis, run_analysis_task
from macro_pipeline.transform import QualityError
from macro_pipeline.race_analysis import RACE_REPORT_FILES


@pytest.fixture
def report_source(tmp_path):
    path = tmp_path / "analysis.ipynb"
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell("# Report execution integration test"),
        nbformat.v4.new_code_cell("""import os
from pathlib import Path
from macro_pipeline.config import Settings
from macro_pipeline.db import read_dataset
from macro_pipeline.analysis import write_analysis
from macro_pipeline.db import read_race_dataset, has_race_data
from macro_pipeline.race_analysis import write_race_analysis
frame, run = read_dataset(Settings.from_env().db_path)
write_analysis(frame, run, Path(os.environ['MACRO_REPORT_DIR']))
if has_race_data(Settings.from_env().db_path):
    race, _ = read_race_dataset(Settings.from_env().db_path)
    write_race_analysis(race, run, Path(os.environ['MACRO_REPORT_DIR']))
print(run['run_id'])"""),
        nbformat.v4.new_code_cell("assert len(frame) > 0"),
    ])
    nbformat.write(notebook, path)
    return path


def test_real_execution_and_revision_refresh(settings, client, report_source, tmp_path):
    first = run_pipeline(settings, client)
    reports = tmp_path / "reports"
    manifest = execute_analysis(settings, report_source, reports, expected_run_id=first["run_id"])
    assert manifest["executed_code_cells"] == 2
    assert set(manifest["files"]) == set((*REPORT_FILES, *RACE_REPORT_FILES))
    for name, checksum in manifest["files"].items():
        assert hashlib.sha256((reports / name).read_bytes()).hexdigest() == checksum
    assert hashlib.sha256(report_source.read_bytes()).hexdigest() == manifest["notebook"]["sha256"]
    assert first["run_id"] in (reports / "eda.html").read_text()

    client.payloads["UNRATE"]["observations"][20]["value"] = "7.7"
    updated = run_pipeline(settings, client)
    execute_analysis(settings, report_source, reports, expected_run_id=updated["run_id"])
    latest = json.loads((reports / "report_manifest.json").read_text())
    assert latest["run_id"] == updated["run_id"] != first["run_id"]
    exported = pd.read_csv(reports / "monthly_indicators.csv", index_col="date", parse_dates=["date"])
    current, _ = read_dataset(settings.db_path)
    pd.testing.assert_frame_equal(exported, current, check_freq=False)


def test_failed_notebook_preserves_reports_and_records_failed_task(settings, client, report_source, tmp_path, monkeypatch):
    run = run_pipeline(settings, client)
    reports = tmp_path / "reports"
    execute_analysis(settings, report_source, reports, expected_run_id=run["run_id"])
    published = {name: (reports / name).read_bytes() for name in (*REPORT_FILES, *RACE_REPORT_FILES, "report_manifest.json")}
    notebook = nbformat.read(report_source, as_version=4)
    notebook.cells.append(nbformat.v4.new_code_cell("raise RuntimeError('Deliberate analysis failure after writing staged figures')"))
    nbformat.write(notebook, report_source)
    original_notebook = report_source.read_bytes()
    for name, value in {"MACRO_DB_PATH": settings.db_path, "MACRO_REPORT_DIR": reports,
                        "MACRO_NOTEBOOK_PATH": report_source, "FRED_API_KEY": settings.api_key}.items():
        monkeypatch.setenv(name, str(value))
    script = Path(__file__).resolve().parents[1] / "scripts/execute_notebook.py"
    with pytest.raises(subprocess.CalledProcessError):
        run_analysis_task(settings, run["run_id"], sys.executable, script)
    for name, content in published.items():
        assert (reports / name).read_bytes() == content
    assert report_source.read_bytes() == original_notebook
    assert not list(reports.glob(".analysis-*"))
    with connect(settings.db_path, readonly=True) as conn:
        assert conn.execute("SELECT status FROM pipeline_steps WHERE run_id=? AND stage='generate_analysis'", (run["run_id"],)).fetchone()[0] == "FAILED"
        assert conn.execute("SELECT status FROM pipeline_runs WHERE run_id=?", (run["run_id"],)).fetchone()[0] == "SUCCESS"


def test_expected_run_mismatch_is_rejected(settings, client, report_source, tmp_path):
    run_pipeline(settings, client)
    with pytest.raises(QualityError, match="expected"):
        execute_analysis(settings, report_source, tmp_path / "reports", expected_run_id="another_run")
    assert not (tmp_path / "reports/eda.html").exists()


def test_missing_figure_prevents_publication(settings, client, report_source, tmp_path):
    run = run_pipeline(settings, client)
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "eda.html").write_text("Previous successful report")
    notebook = nbformat.read(report_source, as_version=4)
    notebook.cells.append(nbformat.v4.new_code_cell("(Path(os.environ['MACRO_REPORT_DIR']) / 'figures/correlations.png').unlink()"))
    nbformat.write(notebook, report_source)
    with pytest.raises(QualityError, match="correlations.png"):
        execute_analysis(settings, report_source, reports, expected_run_id=run["run_id"])
    assert (reports / "eda.html").read_text() == "Previous successful report"
