"""Reproduce the archived FRED vintage without API calls or credentials."""

from pathlib import Path
import argparse
import json
import os

from macro_pipeline.config import Settings
from macro_pipeline.offline import restore_snapshot
from macro_pipeline.reporting import execute_analysis, atomic_write


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=root / "snapshots/manifest.json")
    args = parser.parse_args()
    # Offline outputs are separate from the current-data database and reports.
    data_dir, output = root / "data/offline", root / "reports/offline"
    settings = Settings(db_path=data_dir / "macroeconomics.db", data_dir=data_dir)
    result = restore_snapshot(settings, args.snapshot)
    os.environ["MACRO_OFFLINE"] = "1"
    manifest = execute_analysis(
        settings, root / "notebooks/01_macroeconomic_eda.ipynb", output,
        expected_run_id=result["run_id"],
        published_notebook_path=output / "01_macroeconomic_eda.ipynb",
    )
    atomic_write(output / "snapshot_provenance.json", json.dumps(result, indent=2).encode() + b"\n")
    print(json.dumps({"mode": "offline", "as_of": manifest["as_of"], "rows": manifest["rows"],
                      "report": str(output / "eda.html"), "executed_code_cells": manifest["executed_code_cells"]}, indent=2))


if __name__ == "__main__":
    main()
