"""Command-line entry point with machine-readable, credential-free output."""

import argparse
from datetime import date
from dataclasses import replace
from pathlib import Path
import json
import sys

from .config import Settings
from .db import read_dataset, read_race_dataset, has_race_data
from .demographics import validate_race_monthly
from .pipeline import run_pipeline
from .transform import validate_monthly
from .transform import QualityError
from .fred import FredError


def main():
    parser = argparse.ArgumentParser(description="FRED → SQLite macroeconomic pipeline")
    parser.add_argument("command", choices=["update", "validate", "status", "export", "analyze"])
    parser.add_argument("--as-of", type=date.fromisoformat, help="FRED vintage and observation cutoff (YYYY-MM-DD)")
    parser.add_argument("--output", type=Path, default=Path("reports"))
    args = parser.parse_args()
    settings = Settings.from_env()
    if args.as_of:
        settings = replace(settings, as_of=args.as_of)
    try:
        if args.command == "update":
            result = run_pipeline(settings)
        else:
            frame, run = read_dataset(settings.db_path)
            if args.command == "validate":
                result = validate_monthly(frame.reset_index(), run["as_of"])
            elif args.command == "export":
                args.output.mkdir(parents=True, exist_ok=True)
                dest = args.output / "monthly_indicators.csv"
                frame.to_csv(dest, index_label="date")
                result = {"export": str(dest), "rows": len(frame)}
            elif args.command == "analyze":
                from .analysis import write_analysis
                result = write_analysis(frame, run, args.output)
            else:
                result = {"run_id": run["run_id"], "status": run["status"], "as_of": run["as_of"], "published_at": run["published_at"], "rows": len(frame)}
            if has_race_data(settings.db_path):
                race, race_run = read_race_dataset(settings.db_path)
                if race_run["run_id"] != run["run_id"]:
                    raise QualityError("The dataset changed during the command; retry against the current publication.")
                if args.command == "validate":
                    result["demographics"] = validate_race_monthly(race.reset_index(), run["as_of"])
                elif args.command == "export":
                    folder = args.output / "race"
                    folder.mkdir(parents=True, exist_ok=True)
                    race.to_csv(folder / "monthly_unemployment.csv", index_label="date")
                    result["demographic_export"] = str(folder / "monthly_unemployment.csv")
                elif args.command == "analyze":
                    from .race_analysis import write_race_analysis
                    result["demographics"] = write_race_analysis(race, run, args.output)
                result["demographic_rows"] = len(race)
        print(json.dumps(result, indent=2, allow_nan=False))
    except (QualityError, FredError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # Safe CLI boundary: an unexpected library error must not disclose credentials.
        print(f"{type(exc).__name__}: operation failed. Check configuration and pipeline_runs/pipeline_steps for audit status.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
