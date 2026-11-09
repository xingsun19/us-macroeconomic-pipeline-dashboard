# Data dictionary

`monthly_indicators` contains one row per calendar month from 2000-01-01. FRED's month-start date identifies the observation month, not its release date. The publication's vintage and fetch timestamps are recorded separately.

| Column | Type / unit | Definition |
|---|---|---|
| `date` | TEXT, YYYY-MM-01; primary key | Observation month |
| `unrate` | REAL, percent | Civilian unemployment rate, seasonally adjusted |
| `cpiaucsl` | REAL, index 1982–1984 = 100 | All-items urban CPI, seasonally adjusted |
| `fedfunds` | REAL, percent | Monthly mean effective federal funds rate, not seasonally adjusted |
| `cpi_yoy` | REAL, percent | `100 * (CPI[t] / CPI[t-12] - 1)` |
| `cpi_mom` | REAL, percent | `100 * (CPI[t] / CPI[t-1] - 1)` |
| `unrate_change_pp` | REAL, percentage points | `UNRATE[t] - UNRATE[t-1]` |
| `fedfunds_change_pp` | REAL, percentage points | `FEDFUNDS[t] - FEDFUNDS[t-1]` |
| `real_rate_proxy` | REAL, percentage points | `FEDFUNDS[t] - CPI_YOY[t]`; ex-post, not expectations-based |
| `unrate_status` | TEXT | Unemployment quality flag |
| `cpiaucsl_status` | TEXT | CPI quality flag |
| `fedfunds_status` | TEXT | Federal funds quality flag |

Flags: `observed` (numeric source value), `source_missing` (explicit FRED `.`), `not_released` (trailing month absent), `missing_month` (unexpected omission; rejected before publication). Missing values are never changed to zero, forward-filled, or interpolated. Summaries skip nulls per column; correlations use paired complete months. Lags are computed before dropping nulls.

The 1999 warm-up is retained in raw tables. Metadata JSON preserves title, units, frequency, seasonal adjustment, last-updated information, and other FRED fields. `realtime_start`/`realtime_end` describe availability/vintage semantics; `date` describes the observation month. See [FRED real-time periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

Run status progresses through RUNNING → EXTRACTED → RAW_STORED → CLEANED → VALIDATED → SUCCESS, with FAILED on an exception. Successful extraction snapshots are reused by retries. `pipeline_steps` summarizes the latest stage attempt; Airflow retains full task-attempt history. The publication pointer and monthly table change in one transaction.
