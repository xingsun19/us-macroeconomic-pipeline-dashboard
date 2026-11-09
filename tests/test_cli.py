import json
import sys

from macro_pipeline.cli import main
from macro_pipeline.pipeline import run_pipeline


def test_status_validate_export_analysis(settings, client, monkeypatch, capsys, tmp_path):
    run_pipeline(settings, client)
    monkeypatch.setenv("MACRO_DB_PATH", str(settings.db_path))
    for command in ["status", "validate", "export", "analyze"]:
        monkeypatch.setattr(sys, "argv", ["macro-pipeline", command, "--output", str(tmp_path / "report")])
        assert main() == 0
        assert isinstance(json.loads(capsys.readouterr().out), dict)
    assert (tmp_path / "report/monthly_indicators.csv").exists()


def test_cli_safe_failure(settings, monkeypatch, capsys):
    monkeypatch.setenv("MACRO_DB_PATH", str(settings.db_path))
    monkeypatch.setattr(sys, "argv", ["macro-pipeline", "status"])
    assert main() == 1
    assert settings.api_key not in capsys.readouterr().err
