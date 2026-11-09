"""Deterministic synthetic observations for offline tests only."""

from datetime import date
import copy

import pandas as pd
import pytest

from macro_pipeline.config import Settings, SERIES


class FakeFredClient:
    def __init__(self):
        self.payloads = {}
        dates = pd.date_range("1999-01-01", "2024-06-01", freq="MS")
        for sid in SERIES:
            obs = []
            for i, dt in enumerate(dates):
                value = {"UNRATE": 4 + (i % 24) / 10, "CPIAUCSL": 160 * (1.002 ** i), "FEDFUNDS": 1 + (i % 60) / 20}[sid]
                obs.append({"date": dt.strftime("%Y-%m-%d"), "value": str(value), "realtime_start": "2024-07-15", "realtime_end": "2024-07-15"})
            self.payloads[sid] = {"metadata": {"id": sid, "frequency_short": "M", "title": sid}, "observations": obs}

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
    return pd.DataFrame([{"series_id": sid, "date": obs["date"], "value_text": obs["value"]} for sid, source in client.payloads.items() for obs in source["observations"]])
