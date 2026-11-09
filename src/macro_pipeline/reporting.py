"""Execute analysis against a frozen database and publish verified artifacts."""

from contextlib import contextmanager
from pathlib import Path
import fcntl
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile

from .db import connect, read_dataset, read_race_dataset, has_race_data
from .pipeline import now, stage
from .transform import QualityError

REPORT_FILES = (
    "eda.html", "analysis_summary.json", "findings.md", "monthly_indicators.csv",
    "descriptive_statistics.csv", "correlation_levels.csv", "correlation_changes.csv",
    "lag_correlations.csv", "figures/historical_trends.png",
    "figures/inflation_and_policy.png", "figures/correlations.png",
    "figures/relationship_stability.png",
)


def run_analysis_task(settings, pipeline_run_id, python_path, script_path):
    """Run the isolated analysis interpreter while recording Airflow-stage outcomes."""
    # A report failure must not mark already validated/published data invalid.
    with stage(settings, pipeline_run_id, "generate_analysis", fail_run=False):
        subprocess.run(
            [str(python_path), str(script_path), "--expected-run-id", pipeline_run_id],
            check=True, timeout=540,
        )
    return pipeline_run_id


@contextmanager
def report_lock(reports_dir):
    # Both supported hosts (macOS and Docker/Linux) provide flock.
    with (reports_dir / ".analysis.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
        temp = Path(handle.name)
        try:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)


def execute_analysis(settings, notebook_path, reports_dir, *, expected_run_id=None, kernel_name="python3", published_notebook_path=None):
    """Preserve published outputs until all cells, HTML, and figures pass validation.

    Each output is replaced atomically, with the checksum manifest written last.
    The kernel reads a consistent SQLite backup, even if another writer runs.
    """
    # Keep notebook dependencies out of the Airflow scheduler's Python environment.
    import nbformat
    from nbclient import NotebookClient
    from nbconvert import HTMLExporter
    from .race_analysis import RACE_REPORT_FILES

    notebook_path, reports_dir = Path(notebook_path).resolve(), Path(reports_dir).resolve()
    published_notebook_path = Path(published_notebook_path).resolve() if published_notebook_path else notebook_path
    reports_dir.mkdir(parents=True, exist_ok=True)
    with report_lock(reports_dir), tempfile.TemporaryDirectory(prefix=".analysis-", dir=reports_dir) as folder:
        work = Path(folder)
        snapshot = work / "snapshot.db"
        with connect(settings.db_path, readonly=True) as source:
            with sqlite3.connect(snapshot) as destination:
                source.backup(destination)
        frame, run = read_dataset(snapshot)
        has_demographics = has_race_data(snapshot)
        required_files = (*REPORT_FILES, *RACE_REPORT_FILES) if has_demographics else REPORT_FILES
        if run["status"] != "SUCCESS" or (expected_run_id and run["run_id"] != expected_run_id):
            raise QualityError("Analysis requires the expected successfully published data run.")

        output = work / "reports"
        output.mkdir()
        notebook = nbformat.read(notebook_path, as_version=4)
        code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
        if not code_cells:
            raise QualityError("The analysis notebook has no executable cells.")
        for cell in code_cells:
            cell.execution_count, cell.outputs = None, []
        kernel_env = {key: value for key, value in os.environ.items()
                      if not key.startswith(("AIRFLOW", "_AIRFLOW"))
                      and key not in {"FRED_API_KEY", "GH_TOKEN", "GITHUB_TOKEN"}}
        kernel_env.update(MACRO_DB_PATH=str(snapshot), MACRO_DATA_DIR=str(work), MACRO_REPORT_DIR=str(output))
        NotebookClient(notebook, timeout=180, kernel_name=kernel_name, force_raise_errors=True).execute(
            cwd=str(work), env=kernel_env,
        )
        if any(cell.execution_count is None for cell in code_cells) or any(
            item.output_type == "error" for cell in code_cells for item in cell.outputs
        ):
            raise QualityError("Every analysis cell must execute successfully.")

        executed = nbformat.writes(notebook).encode("utf-8")
        html, _ = HTMLExporter().from_notebook_node(notebook)
        (output / "eda.html").write_text(html, encoding="utf-8")
        for name in required_files:
            path = output / name
            if not path.is_file() or not path.stat().st_size:
                raise QualityError(f"The analysis did not generate {name}.")
            if path.suffix == ".png" and not path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                raise QualityError(f"The analysis generated an invalid PNG: {name}.")
        summary = json.loads((output / "analysis_summary.json").read_text())
        if (summary["run_id"], summary["as_of"], summary["rows"]) != (run["run_id"], run["as_of"], len(frame)):
            raise QualityError("The analysis outputs do not match the database snapshot.")
        demographic_rows = 0
        if has_demographics:
            race, _ = read_race_dataset(snapshot)
            demographic_rows = len(race)
            race_summary = json.loads((output / "race/analysis_summary.json").read_text())
            if (race_summary["run_id"], race_summary["as_of"], race_summary["rows"]) != (run["run_id"], run["as_of"], demographic_rows):
                raise QualityError("The demographic reports do not match the database snapshot.")

        manifest = {
            "run_id": run["run_id"], "as_of": run["as_of"], "rows": len(frame),
            "generated_at": now(), "executed_code_cells": len(code_cells),
            "demographic_rows": demographic_rows,
            "notebook": {"name": published_notebook_path.name, "sha256": hashlib.sha256(executed).hexdigest()},
            "files": {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in required_files},
        }
        # Hold a short write reservation so the publication pointer cannot change
        # between the final check and replacement of this run's report files.
        with connect(settings.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute("SELECT run_id FROM dataset_state WHERE singleton=1").fetchone()
            if current is None or current["run_id"] != run["run_id"]:
                raise QualityError("A newer dataset was published during analysis; rerun against it.")
            for name in required_files:
                atomic_write(reports_dir / name, (output / name).read_bytes())
            if not has_demographics:
                # A replay of a legacy archive must not leave a newer demographic report beside it.
                for name in RACE_REPORT_FILES:
                    (reports_dir / name).unlink(missing_ok=True)
            atomic_write(published_notebook_path, executed)
            atomic_write(reports_dir / "report_manifest.json", json.dumps(manifest, indent=2).encode() + b"\n")
        return manifest
