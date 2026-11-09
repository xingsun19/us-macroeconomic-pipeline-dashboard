"""Monthly alignment and economic transformations without implicit imputation."""

import numpy as np
import pandas as pd

from .config import SERIES, START_DATE, WARMUP_DATE
from .db import MONTHLY_COLUMNS


class QualityError(ValueError):
    """A candidate snapshot cannot safely replace the published dataset."""


def clean_monthly(raw: pd.DataFrame, as_of: str) -> pd.DataFrame:
    raw = raw.copy()
    if raw.empty or set(raw.series_id.unique()) != set(SERIES):
        raise QualityError("Exactly three non-empty source series are required.")
    raw["date"] = pd.to_datetime(raw["date"], errors="raise")
    if not raw.date.dt.is_month_start.all() or (raw.date > pd.Timestamp(as_of)).any() or (raw.date < pd.Timestamp(WARMUP_DATE)).any():
        raise QualityError("Observation dates must be month starts inside the requested window.")
    raw = raw.drop_duplicates(["series_id", "date", "value_text"])
    if raw.duplicated(["series_id", "date"]).any():
        raise QualityError("Conflicting duplicate observations.")
    raw["value"] = pd.to_numeric(raw.value_text.replace(".", np.nan), errors="raise")
    if np.isinf(raw.value.to_numpy(dtype=float)).any():
        raise QualityError("Infinite observations are invalid.")
    calendar = pd.date_range(WARMUP_DATE, raw.date.max(), freq="MS", name="date")
    result = pd.DataFrame(index=calendar)
    for series_id in SERIES:
        source = raw.loc[raw.series_id == series_id].set_index("date")
        if source.index.min() != pd.Timestamp(WARMUP_DATE):
            raise QualityError(f"{series_id} must include the January 1999 warm-up observation.")
        col = series_id.lower()
        result[col] = source.value.reindex(calendar)
        # Retain missing values. Never forward-fill unreleased data or revise history synthetically.
        status = pd.Series("missing_month", index=calendar)
        status.loc[calendar > source.index.max()] = "not_released"
        status.loc[source.index] = np.where(source.value.notna(), "observed", "source_missing")
        if status.eq("missing_month").any():
            raise QualityError(f"{series_id} has omitted calendar months in the API payload.")
        result[f"{col}_status"] = status
    result["cpi_yoy"] = result.cpiaucsl.pct_change(12, fill_method=None) * 100
    result["cpi_mom"] = result.cpiaucsl.pct_change(1, fill_method=None) * 100
    result["unrate_change_pp"] = result.unrate.diff()
    result["fedfunds_change_pp"] = result.fedfunds.diff()
    result["real_rate_proxy"] = result.fedfunds - result.cpi_yoy
    return result.loc[START_DATE:].reset_index()[MONTHLY_COLUMNS]


def validate_monthly(frame: pd.DataFrame, as_of: str) -> dict:
    if frame.empty:
        raise QualityError("The candidate dataset is empty.")
    dates = pd.DatetimeIndex(pd.to_datetime(frame.date))
    expected = pd.date_range(START_DATE, dates.max(), freq="MS")
    if dates.has_duplicates or not dates.equals(expected):
        raise QualityError("Monthly rows must be unique, sorted, and continuous from January 2000.")
    if dates.max() > pd.Timestamp(as_of):
        raise QualityError("Future observations are invalid.")
    limits = {"unrate": (0, 100), "cpiaucsl": (0.000001, 100_000), "fedfunds": (-20, 100)}
    summary = {"rows": len(frame), "start": dates.min().date().isoformat(), "end": dates.max().date().isoformat(), "as_of": as_of, "series": {}, "warnings": []}
    for col, (lo, hi) in limits.items():
        values = frame[col]
        if values.notna().sum() < 13 or not values.dropna().between(lo, hi).all():
            raise QualityError(f"Insufficient observations or invalid range for {col}.")
        statuses = frame[f"{col}_status"]
        if not statuses.isin(["observed", "source_missing", "missing_month", "not_released"]).all():
            raise QualityError(f"Unknown data quality flag for {col}.")
        if not values.notna().equals(statuses.eq("observed")):
            raise QualityError(f"Inconsistent value/status for {col}.")
        last = dates[values.notna()].max()
        # Month-start dates can lag by 1-2 calendar months under ordinary release schedules.
        lag = (pd.Timestamp(as_of) - last).days
        if lag > 95:
            raise QualityError(f"{col} has no observation within 95 days of the requested as-of date.")
        if statuses.eq("missing_month").any() or ((dates <= last) & statuses.eq("not_released")).any():
            raise QualityError(f"{col} has omitted or incorrectly flagged internal months.")
        source_missing = int(statuses.eq("source_missing").sum())
        trailing = int(statuses.eq("not_released").sum())
        if source_missing / len(frame) > 0.05:
            raise QualityError(f"{col} exceeds the 5% source-missing threshold.")
        summary["series"][col] = {"latest_date": last.date().isoformat(), "latest_value": float(values.loc[values.notna()].iloc[-1]), "missing": int(values.isna().sum()), "source_missing": source_missing, "not_released": trailing, "age_days": lag}
        if source_missing:
            summary["warnings"].append(f"{col}: {source_missing} explicit source-missing month(s); retained as null, never imputed.")
        if trailing:
            summary["warnings"].append(f"{col}: {trailing} trailing unreleased month(s); no imputation.")
    checks = {
        "cpi_yoy": frame.cpiaucsl.pct_change(12, fill_method=None) * 100,
        "cpi_mom": frame.cpiaucsl.pct_change(1, fill_method=None) * 100,
        "unrate_change_pp": frame.unrate.diff(),
        "fedfunds_change_pp": frame.fedfunds.diff(),
        "real_rate_proxy": frame.fedfunds - frame.cpi_yoy,
    }
    for col, expected_values in checks.items():
        # Initial changes were calculated from the 1999 warm-up, outside this published table.
        offset = 12 if col == "cpi_yoy" else (0 if col == "real_rate_proxy" else 1)
        if not np.allclose(frame[col].iloc[offset:], expected_values.iloc[offset:], rtol=1e-8, atol=1e-8, equal_nan=True):
            raise QualityError(f"Derived-variable identity failed for {col}.")
    return summary
