"""Exercise the independent page, range selection, gaps, and downloads."""

from pathlib import Path
from dataclasses import replace
import json

import pandas as pd
from streamlit.testing.v1 import AppTest

from macro_pipeline.pipeline import run_pipeline
from macro_pipeline.db import read_race_dataset

APP = Path(__file__).resolve().parents[1] / "dashboard/pages/1_Unemployment_by_Race_and_Ethnicity.py"


def app_for(settings, client, monkeypatch):
    run_pipeline(settings, client)
    monkeypatch.setenv("MACRO_DB_PATH", str(settings.db_path))
    return AppTest.from_file(str(APP), default_timeout=30).run()


def test_page_comparison_ranges_and_download(settings, client, monkeypatch):
    app = app_for(settings, client, monkeypatch)
    assert not app.exception
    assert len(app.metric) == 6
    chart = json.loads(app.get("plotly_chart")[0].proto.spec)
    assert len(chart["data"]) == 4 and len(chart["data"][0]["x"]) == 258
    assert any("ethnicity" in x.value and "overlap" in x.value for x in app.info)
    app.selectbox(key="race_period").set_value("Last 5 years").run()
    assert len(app.dataframe[-1].value) == 60
    app.multiselect(key="race_groups").set_value(["white", "black"]).run()
    assert len(json.loads(app.get("plotly_chart")[0].proto.spec)["data"]) == 2
    assert "asian" not in app.dataframe[-1].value
    app.selectbox(key="race_period").set_value("Custom dates").run()
    app.date_input(key="race_dates").set_value((pd.Timestamp("2020-01-01").date(), pd.Timestamp("2020-12-01").date())).run()
    assert not app.exception
    table = app.dataframe[-1].value
    assert len(table) == 12 and table.index.min() == pd.Timestamp("2020-01-01")
    expected, _ = read_race_dataset(settings.db_path)
    pd.testing.assert_frame_equal(table, expected.loc["2020", table.columns])
    assert app.get("download_button")[0].proto.label == "Download selected period · CSV"
    app.radio(key="race_policy_mode").set_value("Monthly changes").run()
    assert not app.exception


def test_gap_only_missing_month_and_empty_group_selection(settings, client, monkeypatch):
    for sid in ("LNS14000003", "LNS14000006"):
        next(o for o in client.payloads[sid]["observations"] if o["date"] == "2020-04-01")["value"] = "."
    app = app_for(settings, client, monkeypatch)
    app.multiselect(key="race_groups").set_value([]).run()
    assert not app.exception
    assert any("Select at least one" in i.value for i in app.info)
    app.selectbox(key="race_period").set_value("Custom dates").run()
    app.date_input(key="race_dates").set_value((pd.Timestamp("2020-04-01").date(), pd.Timestamp("2020-04-01").date())).run()
    assert not app.exception
    assert any("No matched" in i.value for i in app.info)
    assert app.dataframe[-1].value.black_white_gap_pp.isna().all()


def test_legacy_database_and_offline_label(settings, client, monkeypatch):
    run_pipeline(replace(settings, include_demographics=False), client)
    monkeypatch.setenv("MACRO_DB_PATH", str(settings.db_path))
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception and "updated Run.command" in app.info[0].value
    monkeypatch.setenv("MACRO_OFFLINE", "1")
    app = app_for(settings, client, monkeypatch)
    assert not app.exception and any("Archived snapshot" in x.value for x in app.info)
