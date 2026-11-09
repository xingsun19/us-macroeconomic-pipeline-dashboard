"""Rebuild a validated database from a checksummed, archived FRED response."""

from dataclasses import replace
from datetime import date
from pathlib import Path
import copy
import hashlib
import json

from .config import SERIES, ALL_SERIES, RACE_SERIES, RACE_START_DATE, WARMUP_DATE
from .pipeline import run_pipeline
from .transform import QualityError


def load_snapshot(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text())
    name = manifest["file"]
    if Path(name).name != name:
        raise QualityError("The snapshot filename must be inside its archive directory.")
    content = (manifest_path.parent / name).read_bytes()
    if hashlib.sha256(content).hexdigest() != manifest["sha256"]:
        raise QualityError("Archived FRED snapshot checksum mismatch.")
    payload = json.loads(content)
    version = payload.get("schema_version")
    expected = ALL_SERIES if version == 2 else SERIES
    if (version not in (1, 2) or payload.get("as_of") != manifest["as_of"]
            or set(payload.get("series", {})) != set(expected)):
        raise QualityError("The snapshot metadata or series are inconsistent.")
    for sid in expected:
        source = payload["series"][sid]
        if (source["metadata"]["id"] != sid or source["metadata"]["frequency_short"] != "M"
                or len(source["observations"]) != manifest["observation_counts"][sid]):
            raise QualityError("The archived series metadata or row count is inconsistent.")
    date.fromisoformat(manifest["as_of"])
    return payload, manifest


class SnapshotClient:
    """Supply archived observations to the existing ingestion/validation stages."""

    def __init__(self, payload):
        self.payload = payload

    def fetch_series(self, series_id, start, end):
        expected_start = RACE_START_DATE if series_id in RACE_SERIES else WARMUP_DATE
        if start != expected_start or end != self.payload["as_of"]:
            raise QualityError("Offline replay must use the archived vintage.")
        return copy.deepcopy(self.payload["series"][series_id])


def restore_snapshot(settings, manifest_path):
    payload, manifest = load_snapshot(manifest_path)
    # Validate freshness against the historical vintage, not today's date.
    replay = replace(settings, api_key="", as_of=date.fromisoformat(manifest["as_of"]), include_demographics=payload["schema_version"] == 2)
    result = run_pipeline(replay, client=SnapshotClient(payload))
    return {**result, "mode": "offline", "snapshot_as_of": manifest["as_of"],
            "snapshot_sha256": manifest["sha256"], "source_fetched_at": payload["fetched_at"]}
