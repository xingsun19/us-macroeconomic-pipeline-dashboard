from pathlib import Path
import json

import pandas as pd

from streamlit.testing.v1 import AppTest

from macro_pipeline.pipeline import run_pipeline
from macro_pipeline.db import read_dataset

APP = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"


def setup_app(settings, client, monkeypatch):
    run_pipeline(settings, client)
    monkeypatch.setenv("MACRO_DB_PATH", str(settings.db_path))
    return AppTest.from_file(str(APP), default_timeout=30).run()


def test_dashboard_full_history_charts_and_download(settings, client, monkeypatch):
    app = setup_app(settings, client, monkeypatch)
    assert not app.exception
    assert len(app.metric) == 3
    assert len(app.get("plotly_chart")) == 3
    assert len(app.get("download_button")) == 1
    assert not app.date_input
    expected, _ = read_dataset(settings.db_path)
    trend = json.loads(app.get("plotly_chart")[0].proto.spec)
    assert len(trend["data"][0]["x"]) == len(expected)
    assert not trend["layout"]["xaxis"]["rangeslider"]["visible"]
    app.multiselect(key="indicators").set_value(["unrate", "fedfunds"])
    app.radio(key="comparison").set_value("Standardized (z-score)").run()
    assert not app.exception
    pd.testing.assert_frame_equal(app.dataframe[0].value, expected[["unrate", "fedfunds", "unrate_status", "cpiaucsl_status", "fedfunds_status"]])
    assert "cpiaucsl" not in app.dataframe[0].value.columns
    trend = json.loads(app.get("plotly_chart")[0].proto.spec)
    assert len(trend["data"][0]["x"]) == len(expected)
    assert not trend["layout"]["xaxis"]["rangeslider"]["visible"]
    assert app.get("download_button")[0].proto.label == "Download full history · CSV"
    app.slider(key="lag").set_value(12).run()
    app.radio(key="correlation_mode").set_value("Monthly changes").run()
    assert not app.exception


def test_empty_selection_and_single_indicator(settings, client, monkeypatch):
    app = setup_app(settings, client, monkeypatch)
    app.multiselect(key="indicators").set_value([]).run()
    assert not app.exception
    assert "Select at least one" in app.info[-1].value
    app.multiselect(key="indicators").set_value(["unrate"])
    app.radio(key="comparison").set_value("Standardized (z-score)").run()
    assert not app.exception
    assert not app.date_input
    expected, _ = read_dataset(settings.db_path)
    assert len(app.dataframe[0].value) == len(expected)


def test_missing_database_has_actionable_message(settings, monkeypatch):
    monkeypatch.setenv("MACRO_DB_PATH", str(settings.db_path))
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert "macro-pipeline update" in app.info[0].value


def test_archived_dashboard_labels_the_vintage(settings, client, monkeypatch):
    monkeypatch.setenv("MACRO_OFFLINE", "1")
    app = setup_app(settings, client, monkeypatch)
    assert not app.exception
    assert any("Archived snapshot" in notice.value for notice in app.info)
    assert not app.warning
