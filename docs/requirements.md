# Assignment and implementation mapping

Assignment: **Topics in Data Engineering — Final Project — Northwestern University Fall 2026**.

| Technical requirement | Implementation evidence |
|---|---|
| Read API data | Authenticated FRED metadata and paginated observations; live verification runs |
| Store API data in a database | SQLite raw JSON, normalized observations, staging, curated tables, and audit records |
| DAG covering and measuring the full pipeline | Seven Airflow tasks, status/duration, retries/timeouts, validation, read-back, and notebook/HTML/chart generation |
| Easy-to-run repository | English README, live/offline launchers, configuration template, dependency locks, Docker Compose, Windows/WSL instructions, and tests |
| EDA with key insights | Executed notebook, descriptive statistics, trends, correlations/lags, figures, findings, and limitations |
| Reproducibility over time | Checksummed real FRED snapshot, offline database reconstruction, pinned dependencies, vendored constraints, image digests, and runtime-archive instructions |

The pipeline covers UNRATE, CPIAUCSL, and FEDFUNDS from 2000 onward, with a 1999 warm-up for inflation calculations. The independent Streamlit/Plotly dashboard reads SQLite and provides full-history displays, selectable indicators, comparisons, relationships, zoom, and data downloads.

The added race/ethnicity module covers LNS14000003, LNS14000006, LNS14032183, and LNS14000009 from 2003 onward. It shares the pipeline, database publication, DAG, and notebook, and has an independent dashboard page with time-range selection, group comparisons, latest rates, and the Black–White gap. Analysis reports explicit crisis windows and policy-rate correlations with noncausal and overlapping-category caveats.

Execution is on demand: the DAG uses `schedule=None`, with no catchup or automatic container restart. Run executes the complete live pipeline; Run Offline reproduces the included vintage without FRED access. Report generation and validation remain automated within each run. Current-data and archived-data outputs are stored separately.
