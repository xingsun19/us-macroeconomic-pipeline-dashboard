import numpy as np
import pandas as pd
import pytest

from macro_pipeline.transform import clean_monthly, validate_monthly, QualityError


def test_warmup_gives_january_2000_yoy(raw):
    frame = clean_monthly(raw, "2024-07-15")
    assert frame.date.iloc[0] == pd.Timestamp("2000-01-01")
    assert frame.cpi_yoy.iloc[0] == pytest.approx((1.002**12 - 1) * 100)
    assert frame.cpi_mom.iloc[0] == pytest.approx(.2)
    assert len(frame) == 294
    assert validate_monthly(frame, "2024-07-15")["rows"] == 294


def test_explicit_source_gap_is_not_imputed(raw):
    raw.loc[(raw.series_id == "CPIAUCSL") & (raw.date == "2023-05-01"), "value_text"] = "."
    frame = clean_monthly(raw, "2024-07-15").set_index("date")
    assert np.isnan(frame.loc["2023-05-01", "cpiaucsl"])
    assert np.isnan(frame.loc["2023-06-01", "cpi_mom"])
    assert np.isnan(frame.loc["2024-05-01", "cpi_yoy"])
    assert frame.loc["2023-05-01", "cpiaucsl_status"] == "source_missing"
    report = validate_monthly(frame.reset_index(), "2024-07-15")
    assert report["series"]["cpiaucsl"]["source_missing"] == 1


def test_different_release_dates_stay_null(raw):
    raw = raw[~((raw.series_id == "CPIAUCSL") & (raw.date == "2024-06-01"))]
    frame = clean_monthly(raw, "2024-07-15")
    assert pd.isna(frame.cpiaucsl.iloc[-1])
    assert frame.cpiaucsl_status.iloc[-1] == "not_released"
    assert validate_monthly(frame, "2024-07-15")["series"]["cpiaucsl"]["not_released"] == 1


def test_omitted_internal_month_rejected(raw):
    raw = raw[~((raw.series_id == "UNRATE") & (raw.date == "2020-03-01"))]
    with pytest.raises(QualityError, match="omitted"):
        clean_monthly(raw, "2024-07-15")


def test_duplicate_handling(raw):
    exact = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)
    assert len(clean_monthly(exact, "2024-07-15")) == 294
    conflict = raw.iloc[[0]].copy()
    conflict["value_text"] = "88"
    with pytest.raises(QualityError, match="Conflicting"):
        clean_monthly(pd.concat([raw, conflict]), "2024-07-15")


@pytest.mark.parametrize("value", ["garbage", "inf", "-inf"])
def test_invalid_numeric_values_rejected(raw, value):
    raw.loc[0, "value_text"] = value
    with pytest.raises((ValueError, QualityError)):
        clean_monthly(raw, "2024-07-15")


def test_invalid_range_and_staleness_rejected(raw):
    frame = clean_monthly(raw, "2024-07-15")
    frame.loc[5, "unrate"] = 101
    with pytest.raises(QualityError, match="range"):
        validate_monthly(frame, "2024-07-15")
    frame = clean_monthly(raw, "2024-07-15")
    with pytest.raises(QualityError, match="95 days"):
        validate_monthly(frame, "2025-01-01")


def test_excessive_source_missing_blocks_publication(raw):
    raw.loc[(raw.series_id == "UNRATE") & raw.date.between("2022-01-01", "2023-12-01"), "value_text"] = "."
    with pytest.raises(QualityError, match="5%"):
        validate_monthly(clean_monthly(raw, "2024-07-15"), "2024-07-15")


def test_corrupt_derived_identity_rejected(raw):
    frame = clean_monthly(raw, "2024-07-15")
    frame.loc[20, "cpi_yoy"] += 1
    with pytest.raises(QualityError, match="identity"):
        validate_monthly(frame, "2024-07-15")


def test_future_and_nonmonthly_dates_rejected(raw):
    raw.loc[0, "date"] = "2024-07-16"
    with pytest.raises(QualityError, match="month starts"):
        clean_monthly(raw, "2024-07-15")
