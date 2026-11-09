from pathlib import Path
from datetime import date

from streamlit.testing.v1 import AppTest

from macro_pipeline.pipeline import run_pipeline

APP = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"


def setup_app(settings, client, monkeypatch):
    run_pipeline(settings, client)
    monkeypatch.setenv("MACRO_DB_PATH", str(settings.db_path))
    return AppTest.from_file(str(APP), default_timeout=30).run()


def test_dashboard_metrics_filters_charts_and_download(settings, client, monkeypatch):
    app = setup_app(settings, client, monkeypatch)
    assert not app.exception
    assert len(app.metric) == 3
    assert len(app.get("plotly_chart")) == 3
    assert len(app.get("download_button")) == 1
    app.date_input(key="date_range").set_value((date(2020, 1, 1), date(2024, 1, 1)))
    app.multiselect(key="indicators").set_value(["unrate", "fedfunds"])
    app.radio(key="comparison").set_value("Standardized (z-score)").run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 49
    assert "cpiaucsl" not in app.dataframe[0].value.columns
    app.slider(key="lag").set_value(12).run()
    app.radio(key="correlation_mode").set_value("Monthly changes").run()
    assert not app.exception


def test_empty_selection_and_short_window(settings, client, monkeypatch):
    app = setup_app(settings, client, monkeypatch)
    app.multiselect(key="indicators").set_value([]).run()
    assert not app.exception
    assert "Select at least one" in app.info[-1].value
    app.multiselect(key="indicators").set_value(["unrate"])
    app.date_input(key="date_range").set_value((date(2024, 6, 1), date(2024, 6, 1)))
    app.radio(key="comparison").set_value("Standardized (z-score)").run()
    assert not app.exception


def test_missing_database_has_actionable_message(settings, monkeypatch):
    monkeypatch.setenv("MACRO_DB_PATH", str(settings.db_path))
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert "macro-pipeline update" in app.info[0].value
