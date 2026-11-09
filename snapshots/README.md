# Archived FRED observations

This directory preserves the real source observations used for the submitted analysis, including the 1999 warm-up needed to calculate year-over-year inflation beginning in 2000. The working database remains excluded from Git; this public archive is sufficient to rebuild it.

The manifest records the raw file's checksum, vintage, retrieval time, source links, capture run, and observation counts. Keep the JSON file and manifest together. Offline replay checks their consistency before writing data.

Sources: [UNRATE](https://fred.stlouisfed.org/series/UNRATE) and [CPIAUCSL](https://fred.stlouisfed.org/series/CPIAUCSL) from BLS; [FEDFUNDS](https://fred.stlouisfed.org/series/FEDFUNDS) from the Board of Governors of the Federal Reserve System, distributed through FRED. Preserve source attribution when sharing the data.

See [offline reproduction](../docs/reproducibility.md). Working SQLite databases, API keys, and per-run local outputs are not included in this archive.
