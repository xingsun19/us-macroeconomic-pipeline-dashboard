# U.S. Macroeconomic Data Pipeline & Dashboard

[![Test and reproduce](https://github.com/xingsun19/us-macroeconomic-pipeline-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/xingsun19/us-macroeconomic-pipeline-dashboard/actions/workflows/ci.yml)

**Northwestern University · Topics in Data Engineering · Fall 2026**

Our project examines U.S. unemployment, consumer prices, and monetary policy from 2000 onward, with unemployment by race and ethnicity from 2003 onward. We collect seven FRED series, validate and store them in SQLite, orchestrate the pipeline with Apache Airflow, and present the results in Jupyter and an independent Streamlit dashboard.

![U.S. macroeconomic history](reports/figures/historical_trends.png)

## Quick start: reproduce the included data

Git and Docker with Compose v2 are required. Recommended Docker resources: 4 CPUs, 8 GB RAM, and 10 GB free disk. Windows users should first follow the [WSL 2 setup guide](docs/windows.md).

**1. Download the project.**

```bash
git clone https://github.com/xingsun19/us-macroeconomic-pipeline-dashboard.git
cd us-macroeconomic-pipeline-dashboard
```

**2. Prepare the runtime once while connected to the internet.** No API key is needed for this mode.

```bash
bash scripts/run.sh --prepare-offline
```

**3. Reproduce the archived data and open the dashboard.** This step uses the included real FRED snapshot and makes no FRED requests.

```bash
bash scripts/run.sh --offline
```

On macOS, subsequent runs can use **Run Offline.command**. For report generation without opening the dashboard, add `--batch`.

**4. View the results, then stop.** The dashboard opens at [localhost:8501](http://localhost:8501). The HTML report is saved to `reports/offline/eda.html`. Press Return in the Run window when finished to stop project services. A Colima VM started by the launcher also stops when no other containers are running. The HTML report remains readable afterward.

## Refresh from FRED

For current data, obtain a [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html). Open the local `.env` file and fill in `FRED_API_KEY=`; on macOS, use `open -e .env`. If `.env` does not exist yet, copy `.env.example` to `.env` once. Save the file, then run:

```bash
bash scripts/run.sh
```

On macOS, double-clicking **Run.command** is equivalent. This executes all seven Airflow tasks, refreshes the database, and regenerates the notebook, HTML, figures, and tables. Live results are saved to `reports/eda.html` and `notebooks/01_macroeconomic_eda.ipynb`. Everything runs on demand; there is no recurring schedule. API keys and working databases are excluded from Git.

## What the dashboard shows

- Latest values and full-history trends for UNRATE, CPIAUCSL, and FEDFUNDS.
- Selectable original/derived indicators and standardized comparisons.
- Relationships, correlations, and outcome lags, with hover and zoom.
- Full-history CSV downloads and explicit data-quality flags.

The dashboard reads SQLite directly. Refreshing its display does not fetch new API data. Offline mode clearly labels the archived vintage and uses a separate database; it does not replace live data.

## Unemployment by Race & Ethnicity

Click **Open Unemployment by Race & Ethnicity** directly below the main dashboard title, or choose the page in the sidebar navigation. This separate page adds four latest-value cards, selectable trend lines, simple preset/custom date ranges, a Black–White gap chart, federal-funds comparisons, and CSV downloads. The original macroeconomic page retains its full-history display.

| Group | FRED series | Coverage / units |
|---|---|---|
| White | `LNS14000003` | January 2003 onward; monthly, seasonally adjusted percent |
| Black or African American | `LNS14000006` | Same |
| Asian | `LNS14032183` | Same |
| Hispanic or Latino | `LNS14000009` | Same |

**Hispanic/Latino is an ethnicity and may overlap with any race.** The groups are not mutually exclusive or exhaustive, and their unemployment rates must not be added. The Black–White gap is a same-month subtraction in percentage points. The notebook analyzes long-term trends, explicitly defined financial-crisis/pandemic windows, and policy-rate associations in levels and changes. These are descriptive findings, not causal estimates. See [methods and operation](docs/race_ethnicity.md) and [computed findings](reports/race/findings.md).

Run updates all seven series and publishes both modules in one database transaction, then generates the combined HTML report and the additional outputs under `reports/race/`. Existing databases are upgraded automatically. For the new offline module, rebuild once with `bash scripts/run.sh --prepare-offline`, then use `Run Offline.command`; its bundled archive includes all seven series.

## Key findings

The current analysis and default offline archive use the **2026-11-09 vintage**: **322 macroeconomic months (January 2000–October 2026)** and **286 demographic months (January 2003–October 2026)**. The original three-series November 8 archive remains available for historical reproduction.

- **The 2020 labor-market shock:** unemployment reached **14.8% in April 2020**, the largest value in this sample.
- **Inflation and policy moved on different timelines:** seasonally adjusted CPI YoY inflation peaked at **8.98% in June 2022**. The monthly effective federal funds rate was **1.21%** then, **4.10% in December 2022**, and **5.33% in August 2023**. This sequence describes timing; it does not identify a causal policy effect.
- **Missing data matter:** October 2025 unemployment and CPI observations are unavailable following the federal government shutdown. We preserve missing values and their flags, so calculations that depend on them remain unavailable. See the official [BLS unemployment](https://www.bls.gov/cps/methods/2025-federal-government-shutdown-impact-cps.htm) and [BLS CPI](https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm) explanations.

See the [executed notebook](notebooks/01_macroeconomic_eda.ipynb), [computed findings](reports/findings.md), and [verification record](reports/verification.md).

## Pipeline and reproducibility

`Extract → Store raw → Clean/transform → Validate → Publish SQLite → Verify → Execute analysis`

The repository includes a [checksummed raw-data snapshot](snapshots/manifest.json), pinned dependencies, base-image digests, and vendored Airflow constraints. Offline replay rebuilds SQLite and reruns the same cleaning, validation, and analysis code without an API key. Its processing container has networking disabled. Initial runtime installation requires internet access; retaining the prepared image enables later use without registries. See the [reproduction and archive guide](docs/reproducibility.md) for five-year preservation instructions.

## Project guide

| Location | Contents |
|---|---|
| `src/macro_pipeline/` | API client, pipeline, quality checks, SQLite, analysis, offline replay |
| `dags/` | Executable seven-task Airflow DAG |
| `dashboard/` | Streamlit + Plotly dashboard |
| `dashboard/pages/` | Independent race and ethnicity unemployment page |
| `notebooks/`, `reports/` | Executed EDA, findings, statistics, and figures |
| `snapshots/` | Versioned real FRED responses and provenance/checksum manifest |
| `tests/` | Pipeline, reporting, dashboard, launcher, and DAG checks |
| `Run.command`, `Run Offline.command` | macOS launchers |
| `docs/` | [Architecture](docs/architecture.md), [data dictionary](docs/data_dictionary.md), [operations](docs/operations.md), [Windows setup](docs/windows.md), and [assignment mapping](docs/requirements.md) |

Code is MIT licensed. Source data are attributed to BLS and the Federal Reserve through [FRED](https://fred.stlouisfed.org/); the code license does not replace source-data terms.
