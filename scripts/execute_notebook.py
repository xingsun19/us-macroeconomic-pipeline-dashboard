"""Execute and publish the complete analysis, manually or as the final DAG task."""

from pathlib import Path
import argparse
import json
import os

from macro_pipeline.config import Settings
from macro_pipeline.reporting import execute_analysis


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-run-id", help="Require the database publication from this pipeline run")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = execute_analysis(
        Settings.from_env(),
        os.getenv("MACRO_NOTEBOOK_PATH", str(root / "notebooks/01_macroeconomic_eda.ipynb")),
        os.getenv("MACRO_REPORT_DIR", str(root / "reports")),
        expected_run_id=args.expected_run_id,
        kernel_name=os.getenv("MACRO_NOTEBOOK_KERNEL", "python3"),
    )
    print(json.dumps({key: result[key] for key in ("run_id", "as_of", "rows", "generated_at", "executed_code_cells")}, indent=2))


if __name__ == "__main__":
    main()
