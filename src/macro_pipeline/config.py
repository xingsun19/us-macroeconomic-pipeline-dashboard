"""Runtime configuration; credentials never belong in source code."""

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import os

from dotenv import load_dotenv

SERIES = ("UNRATE", "CPIAUCSL", "FEDFUNDS")
RACE_SERIES = {
    "LNS14000003": "white", "LNS14000006": "black",
    "LNS14032183": "asian", "LNS14000009": "hispanic",
}
ALL_SERIES = (*SERIES, *RACE_SERIES)
RACE_START_DATE = "2003-01-01"
START_DATE = "2000-01-01"
WARMUP_DATE = "1999-01-01"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    api_key: str = field(default="", repr=False)
    db_path: Path = Path("data/macroeconomics.db")
    data_dir: Path = Path("data")
    as_of: date = field(default_factory=lambda: datetime.now(ZoneInfo("America/Chicago")).date())
    # False is reserved for replaying legacy three-series archives.
    include_demographics: bool = True

    @classmethod
    def from_env(cls):
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        # An installed wheel can also use a .env in the working directory.
        load_dotenv(Path.cwd() / ".env", override=False)
        data_dir = Path(os.getenv("MACRO_DATA_DIR", str(PROJECT_ROOT / "data"))).resolve()
        return cls(
            api_key=os.getenv("FRED_API_KEY", "").strip(),
            db_path=Path(os.getenv("MACRO_DB_PATH", str(data_dir / "macroeconomics.db"))).resolve(),
            data_dir=data_dir,
            as_of=date.fromisoformat(os.environ["MACRO_AS_OF"]) if os.getenv("MACRO_AS_OF") else datetime.now(ZoneInfo("America/Chicago")).date(),
        )
