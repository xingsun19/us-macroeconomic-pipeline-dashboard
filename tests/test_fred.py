import requests
import pytest
import responses

from macro_pipeline.fred import FredClient, FredError, BASE_URL

KEY = "x" * 32


@responses.activate
def test_metadata_pagination_and_vintage():
    responses.get(f"{BASE_URL}/series", json={"seriess": [{"id": "UNRATE", "frequency_short": "M"}]})
    responses.get(f"{BASE_URL}/series/observations", json={"count": 2, "observations": [{"date": "2000-01-01", "value": "4.0"}]})
    responses.get(f"{BASE_URL}/series/observations", json={"count": 2, "observations": [{"date": "2000-02-01", "value": "."}]})
    result = FredClient(KEY).fetch_series("UNRATE", "1999-01-01", "2024-07-15")
    assert len(result["observations"]) == 2
    assert "offset=1" in responses.calls[2].request.url
    assert "realtime_start=2024-07-15" in responses.calls[0].request.url


@responses.activate
def test_rate_limit_retry():
    responses.get(f"{BASE_URL}/series", status=429, headers={"Retry-After": "0"})
    responses.get(f"{BASE_URL}/series", json={"seriess": [{"id": "UNRATE", "frequency_short": "M"}]})
    responses.get(f"{BASE_URL}/series/observations", json={"count": 1, "observations": [{"date": "2000-01-01", "value": "4.0"}]})
    assert FredClient(KEY).fetch_series("UNRATE", "1999-01-01", "2024-07-15")
    assert len(responses.calls) == 3


@responses.activate
@pytest.mark.parametrize("status", [400, 401, 403])
def test_http_errors_do_not_expose_key(status):
    responses.get(f"{BASE_URL}/series", status=status, body=f"invalid api_key={KEY}")
    with pytest.raises(FredError) as exc:
        FredClient(KEY).fetch_series("UNRATE", "1999-01-01", "2024-07-15")
    assert KEY not in str(exc.value)


@responses.activate
def test_timeout_does_not_expose_url():
    responses.get(f"{BASE_URL}/series", body=requests.Timeout(f"https://example.com?api_key={KEY}"))
    with pytest.raises(FredError) as exc:
        FredClient(KEY).fetch_series("UNRATE", "1999-01-01", "2024-07-15")
    assert KEY not in str(exc.value)


@responses.activate
def test_empty_page_rejected():
    responses.get(f"{BASE_URL}/series", json={"seriess": [{"id": "UNRATE", "frequency_short": "M"}]})
    responses.get(f"{BASE_URL}/series/observations", json={"count": 2, "observations": []})
    with pytest.raises(FredError, match="pagination"):
        FredClient(KEY).fetch_series("UNRATE", "1999-01-01", "2024-07-15")


def test_missing_key_rejected_without_display():
    with pytest.raises(FredError, match="FRED_API_KEY"):
        FredClient("")
