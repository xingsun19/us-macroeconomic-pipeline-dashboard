"""Verify cross-module publication, demographic data quality, and interpretation."""

from dataclasses import replace
import sqlite3

import numpy as np
import pandas as pd
import pytest

from macro_pipeline.config import RACE_SERIES
from macro_pipeline.db import connect, read_dataset, read_race_dataset, has_race_data
from macro_pipeline.demographics import clean_race_monthly, validate_race_monthly
from macro_pipeline.pipeline import run_pipeline
from macro_pipeline.race_analysis import crisis_comparison, policy_correlations, CATEGORY_NOTE
from macro_pipeline.transform import QualityError


def race_raw(client):
    return pd.DataFrame([{"series_id": sid, "date": o["date"], "value_text": o["value"]}
                         for sid in RACE_SERIES for o in client.payloads[sid]["observations"]])


def test_seven_series_share_one_publication_and_revision(settings, client):
    result = run_pipeline(settings, client)
    macro, run = read_dataset(settings.db_path)
    race, race_run = read_race_dataset(settings.db_path)
    assert run["run_id"] == race_run["run_id"] == result["run_id"]
    assert len(macro) == 294 and len(race) == 258
    assert race.index.min() == pd.Timestamp("2003-01-01")
    pd.testing.assert_series_equal(race.fedfunds, macro.fedfunds.loc[race.index])
    np.testing.assert_allclose(race.black_white_gap_pp, race.black - race.white)
    client.payloads["LNS14000006"]["observations"][5]["value"] = "15.2"
    run_pipeline(settings, client)
    revised, _ = read_race_dataset(settings.db_path)
    assert revised.loc["2003-06-01", "black"] == 15.2
    assert revised.loc["2003-06-01", "black_white_gap_pp"] == pytest.approx(15.2 - revised.loc["2003-06-01", "white"])
    assert len(revised) == len(race)


def test_missing_and_unreleased_rates_propagate_to_gap(client):
    raw = race_raw(client)
    raw.loc[(raw.series_id == "LNS14000006") & (raw.date == "2020-04-01"), "value_text"] = "."
    raw = raw.loc[~((raw.series_id == "LNS14000003") & (raw.date == "2024-06-01"))]
    frame = clean_race_monthly(raw, "2024-07-15")
    indexed = frame.set_index("date")
    assert pd.isna(indexed.loc["2020-04-01", "black_white_gap_pp"])
    assert indexed.loc["2020-04-01", "black_status"] == "source_missing"
    assert indexed.loc["2024-06-01", "white_status"] == "not_released"
    assert pd.isna(indexed.loc["2024-06-01", "black_white_gap_pp"])
    assert validate_race_monthly(frame, "2024-07-15")["series"]["black"]["source_missing"] == 1


def test_omitted_month_and_conflicting_duplicates_rejected(client):
    raw = race_raw(client)
    assert len(clean_race_monthly(pd.concat([raw, raw.iloc[[0]]]), "2024-07-15")) == 258
    duplicate = raw.iloc[[0]].copy()
    duplicate["value_text"] = "17"
    with pytest.raises(QualityError, match="duplicate"):
        clean_race_monthly(pd.concat([raw, duplicate]), "2024-07-15")
    with pytest.raises(QualityError, match="omitted"):
        clean_race_monthly(raw.drop(index=5), "2024-07-15")


@pytest.mark.parametrize("bad", ["-1", "101", "inf", "garbage"])
def test_invalid_values_rejected(client, bad):
    raw = race_raw(client)
    raw.loc[0, "value_text"] = bad
    with pytest.raises((QualityError, ValueError)):
        validate_race_monthly(clean_race_monthly(raw, "2024-07-15"), "2024-07-15")


def test_gap_missingness_and_freshness_checks(client):
    frame = clean_race_monthly(race_raw(client), "2024-07-15")
    bad = frame.copy(); bad.loc[10, "black_white_gap_pp"] += 1
    with pytest.raises(QualityError, match="identity"):
        validate_race_monthly(bad, "2024-07-15")
    with pytest.raises(QualityError, match="Stale"):
        validate_race_monthly(frame, "2025-01-01")
    raw = race_raw(client)
    raw.loc[(raw.series_id == "LNS14000003") & (raw.date < "2005-01-01"), "value_text"] = "."
    with pytest.raises(QualityError, match="5%"):
        validate_race_monthly(clean_race_monthly(raw, "2024-07-15"), "2024-07-15")


def test_demographic_failure_preserves_both_modules(settings, client):
    run_pipeline(settings, client)
    before, original = read_dataset(settings.db_path)
    race_before, _ = read_race_dataset(settings.db_path)
    client.payloads["UNRATE"]["observations"][20]["value"] = "8.5"
    client.payloads["LNS14032183"]["metadata"]["seasonal_adjustment_short"] = "NSA"
    with pytest.raises(QualityError, match="metadata"):
        run_pipeline(settings, client)
    after, current = read_dataset(settings.db_path)
    race_after, _ = read_race_dataset(settings.db_path)
    pd.testing.assert_frame_equal(before, after)
    pd.testing.assert_frame_equal(race_before, race_after)
    assert current["run_id"] == original["run_id"]


def test_sql_failure_rolls_back_both_publications(settings, client):
    run_pipeline(settings, client)
    macro_before, original = read_dataset(settings.db_path)
    race_before, _ = read_race_dataset(settings.db_path)
    client.payloads["UNRATE"]["observations"][20]["value"] = "8.5"
    with connect(settings.db_path) as conn:
        conn.execute("CREATE TRIGGER fail_race BEFORE INSERT ON race_unemployment BEGIN SELECT RAISE(ABORT, 'simulated publication failure'); END;")
    with pytest.raises(sqlite3.IntegrityError):
        run_pipeline(settings, client)
    macro_after, current = read_dataset(settings.db_path)
    race_after, _ = read_race_dataset(settings.db_path)
    pd.testing.assert_frame_equal(macro_before, macro_after)
    pd.testing.assert_frame_equal(race_before, race_after)
    assert current["run_id"] == original["run_id"]


def test_existing_database_upgrade_and_legacy_publication(settings, client):
    run_pipeline(replace(settings, include_demographics=False), client)
    before, _ = read_dataset(settings.db_path)
    with connect(settings.db_path) as conn:
        conn.execute("DROP TABLE race_unemployment")
        conn.execute("DROP TABLE staged_race_unemployment")
        conn.execute("PRAGMA user_version=1")
    assert not has_race_data(settings.db_path)
    run_pipeline(settings, client)
    assert has_race_data(settings.db_path)
    after, _ = read_dataset(settings.db_path)
    pd.testing.assert_frame_equal(before, after)
    run_pipeline(replace(settings, include_demographics=False), client)
    assert not has_race_data(settings.db_path)


def test_crisis_baselines_and_calendar_lags(settings, client):
    run_pipeline(settings, client)
    frame, _ = read_race_dataset(settings.db_path)
    frame.loc["2020-02-01", "white"] = 3
    frame.loc["2020-04-01", "white"] = 20
    frame.loc["2020-03-01", "white"] = np.nan
    events = crisis_comparison(frame)
    row = events.loc[(events.group == "white") & events.window.str.startswith("Pandemic")].iloc[0]
    assert row.peak_month == "2020-04" and row.peak_change_pp == 17
    correlations = policy_correlations(frame)
    row = correlations.loc[(correlations.outcome == "white") & (correlations.transformation == "Monthly changes") & (correlations.lag_months == 6)].iloc[0]
    pairs = pd.concat([frame.fedfunds.diff(), frame.white.diff().shift(-6)], axis=1).dropna()
    assert row.paired_months == len(pairs)
    assert row.pearson_r == pytest.approx(pairs.iloc[:,0].corr(pairs.iloc[:,1]))
    assert "ethnicity" in CATEGORY_NOTE and "overlap" in CATEGORY_NOTE
