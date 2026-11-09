"""Deterministic synthetic observations for offline tests only."""

from datetime import date
import copy

import pandas as pd
import pytest

from macro_pipeline.config import Settings, SERIES, ALL_SERIES, RACE_SERIES


class FakeFredClient:
    def __init__(self):
        self.payloads = {}
        for sid in ALL_SERIES:
            dates = pd.date_range("2003-01-01" if sid in RACE_SERIES else "1999-01-01", "2024-06-01", freq="MS")
            obs = []
            for i, dt in enumerate(dates):
                value = {"UNRATE": 4 + (i % 24) / 10, "CPIAUCSL": 160 * (1.002 ** i), "FEDFUNDS": 1 + (i % 60) / 20, "LNS14000003": 3 + (i % 24) / 10, "LNS14000006": 6 + (i % 36) / 10, "LNS14032183": 2.5 + (i % 18) / 10, "LNS14000009": 5 + (i % 30) / 10}[sid]
                obs.append({"date": dt.strftime("%Y-%m-%d"), "value": str(value), "realtime_start": "2024-07-15", "realtime_end": "2024-07-15"})
            self.payloads[sid] = {"metadata": {"id": sid, "frequency_short": "M", "title": sid, "units": "Percent", "seasonal_adjustment_short": "SA"}, "observations": obs}

    def fetch_series(self, series_id, start, end):
        return copy.deepcopy(self.payloads[series_id])


@pytest.fixture
def settings(tmp_path):
    return Settings(api_key="x" * 32, db_path=tmp_path / "macro.db", data_dir=tmp_path, as_of=date(2024, 7, 15))


@pytest.fixture
def client():
    return FakeFredClient()


@pytest.fixture
def raw(client):
    return pd.DataFrame([{"series_id": sid, "date": obs["date"], "value_text": obs["value"]} for sid, source in client.payloads.items() if sid in SERIES for obs in source["observations"]])
