"""Bounded, paginated FRED requests with sanitized failures."""

from datetime import date
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .config import RACE_SERIES

BASE_URL = "https://api.stlouisfed.org/fred"


class FredError(RuntimeError):
    """A safe error that deliberately excludes request URLs and response bodies."""


class FredClient:
    def __init__(self, api_key: str, session=None):
        if not re.fullmatch(r"[a-z0-9]{32}", api_key):
            raise FredError("Configure a valid 32-character FRED_API_KEY in .env.")
        self._api_key = api_key
        self.session = session or requests.Session()
        retry = Retry(total=4, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"], respect_retry_after_header=True)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _get(self, endpoint, **params):
        params.update(api_key=self._api_key, file_type="json")
        try:
            response = self.session.get(f"{BASE_URL}/{endpoint}", params=params, timeout=(10, 60))
        except requests.RequestException:
            raise FredError("FRED network request failed after bounded retries.") from None
        if response.status_code != 200:
            raise FredError(f"FRED returned HTTP {response.status_code}; check credentials and service availability.")
        try:
            payload = response.json()
        except (ValueError, requests.RequestException):
            raise FredError("FRED returned invalid JSON.") from None
        if not isinstance(payload, dict) or "error_code" in payload:
            raise FredError("FRED returned an invalid response envelope.")
        return payload

    def fetch_series(self, series_id: str, start: str, end: str):
        # Use the same vintage date for every series and page in a run.
        date.fromisoformat(start)
        date.fromisoformat(end)
        vintage = {"realtime_start": end, "realtime_end": end}
        meta = self._get("series", series_id=series_id, **vintage).get("seriess", [])
        if len(meta) != 1 or meta[0].get("id") != series_id or meta[0].get("frequency_short") != "M":
            raise FredError(f"Unexpected monthly series metadata for {series_id}.")
        if series_id in RACE_SERIES and (meta[0].get("seasonal_adjustment_short") != "SA" or meta[0].get("units") != "Percent"):
            raise FredError(f"Expected seasonally adjusted percent data for {series_id}.")
        rows, offset = [], 0
        while True:
            page = self._get("series/observations", series_id=series_id, observation_start=start, observation_end=end,
                             sort_order="asc", limit=1000, offset=offset, **vintage)
            batch = page.get("observations")
            count = page.get("count")
            if not isinstance(batch, list) or not isinstance(count, int) or count < 1 or count > 100_000:
                raise FredError(f"Invalid observations envelope for {series_id}.")
            rows.extend(batch)
            offset += len(batch)
            if offset == count:
                break
            if not batch or offset > count:
                raise FredError(f"Incomplete or inconsistent pagination for {series_id}.")
        return {"metadata": meta[0], "observations": rows}
