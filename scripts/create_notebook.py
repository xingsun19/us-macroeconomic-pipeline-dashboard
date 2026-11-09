"""Build the readable, executable analysis notebook from an explicit cell outline."""

from pathlib import Path
import nbformat as nbf

root = Path(__file__).resolve().parents[1]
md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell
nb = nbf.v4.new_notebook()
nb.metadata = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python", "version": "3.11"}}
nb.cells = [
    md("""# U.S. Macroeconomic Data Pipeline & Dashboard
## Northwestern University · Topics in Data Engineering · Fall 2026

**Research question:** How have unemployment, consumer prices, and the federal funds rate evolved since 2000, and how stable are their descriptive relationships?

This notebook reads the **validated SQLite database**, performs reproducible exploratory analysis, and exports figures and findings. It does not call an API or contain credentials. The Run launcher executes the Airflow DAG once, including this notebook after successful data publication. There is no recurring schedule. For separate manual analysis, run `macro-pipeline update` first, then execute this notebook from top to bottom. All values and conclusions below are calculated from the database snapshot.

The deliverable covers API ingestion, database storage, an executable end-to-end Airflow DAG, a reproducible GitHub repository, and EDA. The interactive Streamlit dashboard is a separate application.
"""),
    md("""### 1. Sources, units, and design choices

| Series | Meaning | Units | Adjustment |
|---|---|---|---|
| [UNRATE](https://fred.stlouisfed.org/series/UNRATE) | Civilian unemployment rate (BLS) | Percent | Seasonally adjusted |
| [CPIAUCSL](https://fred.stlouisfed.org/series/CPIAUCSL) | All-items urban consumer price index (BLS) | 1982–84 = 100 | Seasonally adjusted |
| [FEDFUNDS](https://fred.stlouisfed.org/series/FEDFUNDS) | Effective federal funds rate (Federal Reserve) | Percent, monthly average of daily figures | Not seasonally adjusted |

The published analysis begins in January 2000. Raw ingestion also retrieves 1999 to provide a twelve-month warm-up for inflation. API requests specify the same FRED real-time/vintage date for all seven series. A full-history refresh on each requested run captures revisions. Raw JSON, checksums, metadata, run statuses, and stage durations are retained locally.

**Missing data policy:** preserve explicit FRED `.` as null; distinguish it from unreleased trailing months. Reject omitted calendar months, implausible values, stale series, and source-missing shares above 5%. Never forward-fill or interpolate observations. Percentage changes explicitly disable implicit filling. Each statistic excludes only the nulls relevant to that calculation.
"""),
    code("""from pathlib import Path
import json
import sqlite3
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown, Image
from macro_pipeline.config import Settings
from macro_pipeline.db import read_dataset, connect, VALUE_COLUMNS
from macro_pipeline.transform import validate_monthly
from macro_pipeline.analysis import LABELS, ECONOMIC_COLUMNS, findings, lag_correlations, write_analysis

settings = Settings.from_env()
root = Path.cwd() if (Path.cwd() / 'pyproject.toml').exists() else Path.cwd().parent
report_dir = Path(os.getenv('MACRO_REPORT_DIR', str(root / 'reports'))).resolve()
df, run = read_dataset(settings.db_path)
validation = validate_monthly(df.reset_index(), run['as_of'])
display(Markdown("**Archived snapshot reproduction — no live API update.**")) if os.getenv("MACRO_OFFLINE") == "1" else None
display(Markdown(f"**FRED vintage:** {run['as_of']} · **Rows:** {len(df)} · **Published:** {run['published_at']}"))
display(df.tail(8))"""),
    md("### 2. Audit the database and data quality"),
    code("""with connect(settings.db_path, readonly=True) as conn:
    tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", conn)
    stages = pd.read_sql_query('SELECT stage, status, duration_seconds FROM pipeline_steps WHERE run_id=? AND stage != ? ORDER BY started_at', conn, params=(run['run_id'], 'generate_analysis'))
    raw_counts = pd.read_sql_query('SELECT series_id, COUNT(*) AS raw_observations FROM raw_observations WHERE run_id=? GROUP BY series_id', conn, params=(run['run_id'],))
display(tables)
display(raw_counts)
display(stages)
assert df.index.is_unique and df.index.is_monotonic_increasing
assert len(df) == validation['rows']
assert stages.status.eq('SUCCESS').all()
display(pd.DataFrame(validation['series']).T)"""),
    code("""missing = pd.DataFrame({'missing_count': df[VALUE_COLUMNS].isna().sum(), 'missing_pct': df[VALUE_COLUMNS].isna().mean() * 100})
display(missing)
display(df.loc[df[['unrate', 'cpiaucsl', 'fedfunds']].isna().any(axis=1)])
display(Markdown('\\n'.join('- ' + w for w in validation['warnings'])))"""),
    md("""**An actual data-engineering edge case:** October 2025 unemployment and CPI are absent in the source because the federal government shutdown interrupted data collection. See the [BLS CPS explanation](https://www.bls.gov/cps/methods/2025-federal-government-shutdown-impact-cps.htm) and [BLS CPI explanation](https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm). The missing observation is retained. Consequently, month-over-month growth touching the gap and year-over-year growth using it as the denominator are also missing. A missing value does not mean zero inflation or zero unemployment.

The latest CPI month may lag the latest unemployment/rate month because release calendars differ. Latest-value comparisons therefore show each observation's date, while scatter plots and correlations pair matching months.
"""),
    md("### 3. Derived variables and descriptive statistics\n\n`CPI YoY = 100 × (CPI[t] / CPI[t−12] − 1)`; `CPI MoM = 100 × (CPI[t] / CPI[t−1] − 1)`. Rate changes are percentage-point differences. The ex-post real-rate proxy is `FEDFUNDS − CPI YoY`; it is not an expected real interest rate."),
    code("""stats = df[VALUE_COLUMNS].describe(percentiles=[.05, .25, .5, .75, .95]).T
display(stats.round(3))
peaks = pd.DataFrame([{'indicator': LABELS[c], 'minimum': df[c].min(), 'minimum_month': df[c].idxmin().strftime('%Y-%m'), 'maximum': df[c].max(), 'maximum_month': df[c].idxmax().strftime('%Y-%m')} for c in ['unrate', 'cpi_yoy', 'fedfunds']])
display(peaks)"""),
    md("### 4. Historical trends\n\nThe first figure uses separate axes because a price index and percentage rates have different units. The second compares inflation and the policy rate in percent; their difference is measured in percentage points. Gaps in the charts are intentional."),
    code("""analysis = write_analysis(df, run, report_dir)
display(Image(filename=str(report_dir / 'figures/historical_trends.png')))
display(Image(filename=str(report_dir / 'figures/inflation_and_policy.png')))"""),
    code("""annual = df[ECONOMIC_COLUMNS].resample('YS').agg(['mean', 'count'])
display(annual.tail(8).round(3))
display(Markdown('Annual averages use available months only; counts disclose missing and partial years. They should not be interpreted as full-year averages when fewer than 12 months are observed.'))"""),
    md("### 5. Correlation and transformation sensitivity\n\nA trending price level can produce misleading correlations. We use inflation, unemployment, and the policy rate for the main relationship analysis and compare levels with monthly changes. Counts are reported because pairwise-complete samples can differ."),
    code("""levels = df[ECONOMIC_COLUMNS]
changes = levels.diff()
display(levels.corr().round(3))
display(changes.corr().round(3))
pair_counts = levels.notna().astype(int).T.dot(levels.notna().astype(int))
display(pair_counts)
display(Image(filename=str(report_dir / 'figures/correlations.png')))"""),
    md("### 6. Stability across time\n\nA scatter plot colored by year and a 60-month rolling correlation expose changes that a full-sample coefficient can hide. Rolling windows require all 60 paired observations; official missing months create gaps. The subperiods below are descriptive calendar partitions, not a formal recession classification."),
    code("""display(Image(filename=str(report_dir / 'figures/relationship_stability.png')))
periods = [('2000–2007', '2000-01-01', '2007-12-01'), ('2008–2019', '2008-01-01', '2019-12-01'), ('2020 onward', '2020-01-01', df.index.max())]
period_summary = []
for label, start, end in periods:
    part = df.loc[start:end, ECONOMIC_COLUMNS]
    pair = part[['unrate', 'cpi_yoy']].dropna()
    period_summary.append({'period': label, 'paired_months': len(pair), 'unemployment_mean': part.unrate.mean(), 'inflation_mean': part.cpi_yoy.mean(), 'fedfunds_mean': part.fedfunds.mean(), 'unemployment_inflation_r': pair.unrate.corr(pair.cpi_yoy)})
display(pd.DataFrame(period_summary).round(3))"""),
    md("### 7. Exploratory lag relationships\n\nPositive lag k means the federal funds rate at t is paired with the outcome at t+k. Shifts happen on the complete monthly calendar before nulls are dropped, so a missing month cannot shorten a lag. A policy response to the economy creates endogeneity: this is not a causal estimate of monetary policy. Searching 25 lags also introduces multiple-comparison risk."),
    code("""lag_table = lag_correlations(df)
display(lag_table.pivot(index='lag_months', columns='outcome', values='pearson_r').round(3))
ax = lag_table.pivot(index='lag_months', columns='outcome', values='pearson_r').plot(figsize=(10, 4), color=['#008c95', '#d68b29'])
ax.set(xlabel='Outcome lag (months after federal funds observation)', ylabel='Pearson correlation', title='Exploratory lead–lag associations')
ax.axhline(0, color='#142c3a', lw=.7)
plt.tight_layout()
plt.show()
display(lag_table.groupby('outcome').agg(min_pairs=('n', 'min'), max_pairs=('n', 'max')))"""),
    md("### 8. Data-supported findings and limits"),
    code("""for number, item in enumerate(findings(df, run), 1):
    display(Markdown(f'**{number}.** {item}'))"""),
    md("""**Limitations and next steps.** This is a descriptive analysis of revised, monthly national aggregates. Autocorrelation, omitted variables, trends, and changes in economic regimes prevent causal interpretation of simple correlations. The analysis neither estimates policy effects nor forecasts the economy. A causal extension would require an identification strategy; a forecasting extension would require time-ordered validation and vintage-aware data. The simple ex-post real-rate proxy uses realized inflation, not expectations. Seasonally adjusted CPI YoY may differ from headline inflation based on the unadjusted series.

**Reproducibility.** `requirements.lock` pins Python dependencies and hashes; Docker fixes base-image digests. Every refresh stores the requested FRED vintage and raw checksum. Use a new database path with `macro-pipeline update --as-of YYYY-MM-DD` for a separate historical snapshot; the publication guard prevents older snapshots overwriting newer data. The CSV reports and executed notebook preserve this run's visible results. External APIs, registry availability, and future provider changes cannot be guaranteed indefinitely, so archive release artifacts for long-term reproducibility.

**Project components:** `src/macro_pipeline/`, `dags/us_macro_pipeline.py`, `dashboard/app.py`, `tests/`, `compose.yaml`, `Run.command`, and the English `README.md`. The DAG runs extraction → raw storage → cleaning/transformation → validation → publication → read-back verification → notebook execution and report generation. The analysis task uses a frozen database snapshot and stages outputs before publishing the HTML, figures, tables, findings, and executed notebook. It runs only when requested.
"""),
    code("""expected = ['descriptive_statistics.csv', 'correlation_levels.csv', 'correlation_changes.csv', 'lag_correlations.csv', 'analysis_summary.json', 'findings.md', 'monthly_indicators.csv']
assert all((report_dir / item).is_file() for item in expected)
display(Markdown(f'**Execution complete:** {len(df)} monthly rows analyzed. Reports and figures are available in `reports/`.'))"""),
]

# Keep the original macroeconomic analysis intact and add a dedicated module.
nb.cells[-1:-1] = [
    md("""### 9. Unemployment by Race & Ethnicity

Four monthly, seasonally adjusted BLS CPS rates are aligned from January 2003: [White](https://fred.stlouisfed.org/series/LNS14000003), [Black or African American](https://fred.stlouisfed.org/series/LNS14000006), [Asian](https://fred.stlouisfed.org/series/LNS14032183), and [Hispanic or Latino](https://fred.stlouisfed.org/series/LNS14000009). January 2003 provides a common starting point after CPS classification changes.

**Hispanic/Latino is an ethnicity, not an exclusive race category.** Hispanic people may be of any race and are included in the race series. These overlapping group rates must not be added or treated as shares. Rates use each group's civilian labor force, age 16+, as denominator. See [BLS definitions](https://www.bls.gov/cps/definitions.htm#hispanic). Official seasonal adjustment is supplied by BLS; we verify the metadata and do not adjust the rates again.

The Black–White gap is the Black rate minus the White rate, in **percentage points**. Both observations must be available for the same month. All missing observations remain null.
"""),
    code("""from macro_pipeline.db import read_race_dataset, has_race_data, RACE_COLUMNS
from macro_pipeline.demographics import CATEGORY_NOTE, CAUSAL_NOTE, validate_race_monthly
from macro_pipeline.race_analysis import write_race_analysis, crisis_comparison, annual_summary, policy_correlations
race = pd.DataFrame()
if has_race_data(settings.db_path):
    race, race_run = read_race_dataset(settings.db_path)
    assert race_run['run_id'] == run['run_id']
    race_quality = validate_race_monthly(race.reset_index(), run['as_of'])
    race_analysis = write_race_analysis(race, run, report_dir)
    display(Markdown(CATEGORY_NOTE))
    display(pd.DataFrame(race_quality['series']).T)
    display(race[RACE_COLUMNS + ['black_white_gap_pp']].describe().T.round(3))
else:
    display(Markdown('This legacy snapshot contains the original macroeconomic series only. Run the updated pipeline or replay the current seven-series archive for the demographic module.'))"""),
    md("""#### Long-term trends and the Black–White gap

We compare rates on a common percent scale and report the gap in percentage points. Annual means exclude nulls and show observed-month counts; incomplete years are not full-year averages. A sample average does not describe every person or explain why a disparity exists.
"""),
    code("""if not race.empty:
    display(Image(filename=str(report_dir / 'race/figures/trends.png')))
    display(Image(filename=str(report_dir / 'race/figures/black_white_gap.png')))
    display(annual_summary(race).tail(20).round(3))
    display(race[['black_white_gap_pp']].describe().T.round(3))"""),
    md("""#### The 2008 financial crisis and the 2020 pandemic

For the financial crisis, the baseline is **December 2007**, and the peak search spans **January 2008–December 2010**, including the lagging labor-market aftermath. For the pandemic, the baseline is **February 2020**, and the peak search spans **March 2020–December 2021**. These stated comparison windows are not official recession dates. Each group's peak can occur in a different month; a baseline-to-peak change is descriptive, not a causal estimate of an event's effect.
"""),
    code("""if not race.empty:
    display(crisis_comparison(race).round(3))
    display(Image(filename=str(report_dir / 'race/figures/crisis_comparison.png')))"""),
    md("""#### Relationships with the federal funds rate

The rate is joined from the same SQLite publication by observation month. We compare levels with monthly changes and report 0-, 6-, and 12-month outcome lags with paired sample sizes. Positive lag k pairs federal funds at t with the group's unemployment or gap at t+k. Differences and shifts are computed before dropping nulls. FEDFUNDS is a monthly average and is not seasonally adjusted.

Policy responds to economic conditions, and the series exhibit autocorrelation and structural changes. These associations cannot identify the effect of monetary policy on any group. Lag searches are exploratory. CPS sampling uncertainty is not estimated from these aggregate series.
"""),
    code("""if not race.empty:
    display(policy_correlations(race).round(3))
    display(Image(filename=str(report_dir / 'race/figures/policy_relationships.png')))
    for item in race_analysis['findings']:
        display(Markdown(item))
    display(Markdown(CAUSAL_NOTE))"""),
]

dest = root / "notebooks/01_macroeconomic_eda.ipynb"
dest.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, dest)
print(f"Created {len(nb.cells)} notebook cells.")
