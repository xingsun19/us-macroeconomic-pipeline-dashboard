# Unemployment by Race & Ethnicity

## Source and coverage

The module uses BLS Current Population Survey unemployment rates distributed by FRED:

| Group | Series | Unit / frequency / adjustment |
|---|---|---|
| White | [LNS14000003](https://fred.stlouisfed.org/series/LNS14000003) | Percent / monthly / seasonally adjusted |
| Black or African American | [LNS14000006](https://fred.stlouisfed.org/series/LNS14000006) | Same |
| Asian | [LNS14032183](https://fred.stlouisfed.org/series/LNS14032183) | Same |
| Hispanic or Latino | [LNS14000009](https://fred.stlouisfed.org/series/LNS14000009) | Same |

All requests start at January 2003 and use the same FRED vintage as UNRATE, CPIAUCSL, and FEDFUNDS. We use the source's seasonal adjustment and validate its metadata rather than estimating a second adjustment. Month-start dates identify observation months, not release dates. CPS classification changes in January 2003 motivate the common comparison period; see [BLS definitions](https://www.bls.gov/cps/definitions.htm#hispanic).

## Categories and interpretation

Hispanic/Latino is an ethnicity, and people of that ethnicity may identify with any race. The White, Black, and Asian series include Hispanic people. The categories overlap and omit other race groups. They must not be summed, averaged into a national rate without appropriate labor-force weights, or treated as population shares. Each rate measures unemployed people as a percentage of that group's civilian labor force, age 16+.

The **Black–White gap** equals `black - white` in percentage points. For example, 6.6% minus 3.7% is 2.9 pp. A positive gap indicates a higher Black unemployment rate; it does not explain the gap's cause. Both values must belong to the same observed month.

Group estimates have sampling uncertainty, and group averages do not characterize every individual. These four aggregate series do not supply uncertainty intervals or identify effects of race, ethnicity, the pandemic, or monetary policy. Correlations can reflect policy responses, common shocks, occupational composition, autocorrelation, and omitted variables.

## Ingestion and database

Run executes the existing seven-task DAG once. Every refresh fetches the full requested history of all seven series, capturing historical revisions. Raw metadata and observation JSON retain provenance. The original macroeconomic table remains unchanged; schema version 2 adds `staged_race_unemployment` and `race_unemployment`. Both curated tables and the publication pointer are updated in one transaction only after both modules pass validation.

FRED `.` remains null with `source_missing`. Trailing absent releases use `not_released`; omitted internal months fail. Exact duplicates are collapsed and conflicting duplicates fail. Rates outside 0–100, invalid dates, infinite values, excessive source missingness (>5%), stale series (>95 days relative to the vintage), or a mismatched gap prevent publication. Missing values are never imputed. The October 2025 gap remains visible in all four source series.

## Analysis methods

- **Long-term trends:** common percentage scale, descriptive statistics, annual means with observed-month counts, and Black–White gap history. Partial years remain explicitly identifiable by counts.
- **Financial crisis:** December 2007 baseline; January 2008–December 2010 peak search, allowing for delayed labor-market responses.
- **Pandemic:** February 2020 baseline; March 2020–December 2021 peak search.
- **Crisis comparison:** each group's baseline, peak rate/month, peak-minus-baseline change, last observed rate/month, and sample count. The windows are stated descriptive choices, not official recession dates or causal estimates.
- **Policy relationship:** FEDFUNDS is joined by calendar month from the same publication. Levels and monthly changes are analyzed separately. Positive lags of 0, 6, and 12 pair the rate at t with a group's unemployment or the gap at t+k. Changes and shifts occur before nulls are removed, and paired sample counts accompany coefficients. Lag searches are exploratory, without causal inference or adjusted significance tests.

The combined notebook contains a dedicated demographic section. Its charts and tables are exported to `reports/race/`, and the combined HTML remains `reports/eda.html`. Report hashes include the demographic artifacts; failed notebook execution or a missing required figure preserves the previous complete report set.

## Dashboard and operation

Open [localhost:8501](http://localhost:8501) after Run, then click **Open Unemployment by Race & Ethnicity** directly below the main title. The page is also available through the sidebar navigation. Latest cards use the full dataset and display each observation month. Charts, selected-period statistics, gap summaries, and CSV downloads use the selected range. Choose full history, the last five years, a crisis preset, or custom dates; custom dates include the entire selected calendar months. Group selection controls the trend lines and downloaded rate columns. The gap always compares Black and White rates. The expandable crisis table uses fixed analysis windows, independent of chart filtering.

The original macroeconomic page retains all its features and full-history behavior. Both pages read SQLite directly; Refresh database reloads local data rather than contacting FRED. Run updates the source data and regenerates analysis. The DAG still has no timed schedule.

Rebuild the offline image once with `bash scripts/run.sh --prepare-offline` after upgrading. `Run Offline.command` then reproduces the bundled seven-series archive without a key or FRED access. The legacy November 8 three-series archive remains replayable using `python scripts/run_offline.py --snapshot snapshots/manifest-macro-2026-11-08.json`; it intentionally has no demographic observations.

## Verification

Tests cover metadata rejection, dates and numeric values, missing/unreleased propagation, duplicate conflicts, historical revisions, schema upgrades, cross-module rollback, gap identities, crisis baselines, calendar-preserving lags, offline replay, and page interactions. See the [verification record](../reports/verification.md) for observed execution results.
