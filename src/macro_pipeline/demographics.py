"""Monthly unemployment rates by race and ethnicity, with explicit missingness."""

import numpy as np
import pandas as pd

from .config import RACE_SERIES, RACE_START_DATE
from .db import RACE_COLUMNS, RACE_MONTHLY_COLUMNS
from .transform import QualityError

GROUP_LABELS = {"white": "White", "black": "Black or African American", "asian": "Asian", "hispanic": "Hispanic or Latino"}
GROUP_COLORS = {"white": "#167d9a", "black": "#a85e28", "asian": "#725ac1", "hispanic": "#32866b"}
CATEGORY_NOTE = (
    "Hispanic or Latino is an ethnicity and may include people of any race. "
    "The White, Black, and Asian series include Hispanic people. Categories overlap, "
    "are not exhaustive, and must not be added or treated as population shares. "
    "Each rate is unemployed people divided by that group's labor force (age 16+)."
)
CAUSAL_NOTE = (
    "These are descriptive associations, not causal effects. Economic conditions, "
    "policy responses, occupational composition, sampling variation, and other omitted "
    "factors can influence the patterns. Group averages do not describe every individual."
)


def clean_race_monthly(raw, as_of, end_date=None):
    raw = raw.copy()
    if raw.empty or set(raw.series_id.unique()) != set(RACE_SERIES):
        raise QualityError("All four race and ethnicity series are required.")
    raw["date"] = pd.to_datetime(raw.date, errors="raise")
    if (not raw.date.dt.is_month_start.all() or (raw.date < pd.Timestamp(RACE_START_DATE)).any()
            or (raw.date > pd.Timestamp(as_of)).any()):
        raise QualityError("Demographic dates must be month starts from January 2003 within the vintage.")
    raw = raw.drop_duplicates(["series_id", "date", "value_text"])
    if raw.duplicated(["series_id", "date"]).any():
        raise QualityError("Conflicting demographic duplicate observations.")
    raw["value"] = pd.to_numeric(raw.value_text.replace(".", np.nan), errors="raise")
    if np.isinf(raw.value.to_numpy(dtype=float)).any():
        raise QualityError("Infinite demographic observations are invalid.")
    calendar = pd.date_range(RACE_START_DATE, end_date or raw.date.max(), freq="MS", name="date")
    result = pd.DataFrame(index=calendar)
    for sid, col in RACE_SERIES.items():
        source = raw.loc[raw.series_id == sid].set_index("date")
        if source.index.min() != pd.Timestamp(RACE_START_DATE) or source.index.max() > calendar.max():
            raise QualityError(f"Invalid requested coverage for {sid}.")
        result[col] = source.value.reindex(calendar)
        status = pd.Series("missing_month", index=calendar)
        status.loc[calendar > source.index.max()] = "not_released"
        status.loc[source.index] = np.where(source.value.notna(), "observed", "source_missing")
        if status.eq("missing_month").any():
            raise QualityError(f"{sid} has omitted calendar months in the API payload.")
        result[f"{col}_status"] = status
    result["black_white_gap_pp"] = result.black - result.white
    return result.reset_index()[RACE_MONTHLY_COLUMNS]


def validate_race_monthly(frame, as_of):
    if frame.empty:
        raise QualityError("The demographic candidate dataset is empty.")
    dates = pd.DatetimeIndex(pd.to_datetime(frame.date))
    if not dates.equals(pd.date_range(RACE_START_DATE, dates.max(), freq="MS")) or dates.max() > pd.Timestamp(as_of):
        raise QualityError("Demographic months must be unique, sorted, continuous, and within the vintage.")
    summary = {"rows": len(frame), "start": dates.min().date().isoformat(), "end": dates.max().date().isoformat(),
               "series": {}, "warnings": []}
    for col in RACE_COLUMNS:
        values, flags = frame[col], frame[f"{col}_status"]
        if values.notna().sum() < 13 or not values.dropna().between(0, 100).all():
            raise QualityError(f"Insufficient observations or invalid range for {col} unemployment.")
        if not flags.isin(["observed", "source_missing", "not_released"]).all() or not values.notna().equals(flags.eq("observed")):
            raise QualityError(f"Inconsistent demographic quality flags for {col}.")
        last = dates[values.notna()].max()
        age = (pd.Timestamp(as_of) - last).days
        if age > 95 or ((dates <= last) & flags.eq("not_released")).any():
            raise QualityError(f"Stale or internally unreleased demographic series: {col}.")
        missing = int(flags.eq("source_missing").sum())
        if missing / len(frame) > .05:
            raise QualityError(f"{col} exceeds the 5% source-missing threshold.")
        summary["series"][col] = {"latest_date": last.date().isoformat(), "latest_value": float(values.dropna().iloc[-1]),
            "source_missing": missing, "not_released": int(flags.eq("not_released").sum()), "age_days": age}
        if values.isna().any():
            summary["warnings"].append(f"{col}: {int(values.isna().sum())} missing/unreleased month(s); retained as null.")
    if not np.allclose(frame.black_white_gap_pp, frame.black - frame.white, equal_nan=True, rtol=1e-10, atol=1e-10):
        raise QualityError("Black–White gap identity failed.")
    return summary
