# Verification record

## Race and ethnicity extension — November 9, 2026

The current notebook and report artifacts use FRED vintage **2026-11-09** and successful data run `fa9ca85fd0b5501e5a1da453d0f6ef62`. Analysis completed at **2026-11-09 17:14:20 UTC**. This section supersedes the earlier three-series counts retained below as development history.

| Check | Observed outcome |
|---|---|
| Live FRED extraction | All seven series fetched; the four new series are monthly, seasonally adjusted percentages from January 2003 |
| SQLite | 322 original macroeconomic months and 286 demographic months; both modules published under one run ID; integrity check passed |
| Linux Docker application suite | **71 passed**, 2 Airflow-specific tests deselected; Python 3.11.18 |
| Native application suite | **71 passed**; Python 3.13.5 (before adding the separate Airflow import-isolation regression) |
| Application coverage | **95%** statement coverage: 825 statements, 43 not covered |
| Airflow container tests | **2 passed**: dependency graph/manual schedule and report-task dependency isolation |
| Real Airflow execution | All seven tasks succeeded, including live requests, validation, transactional publication, and analysis; run `manual__2026-11-09T17:14:04.092534+00:00` |
| Notebook/report generation | **15 code cells** executed without errors; **23 artifacts** plus the executed notebook; every hash matches `report_manifest.json` |
| Offline Docker replay | No API key; replay configured with `network_mode: none`; 15 cells and 23 artifacts rebuilt from the seven-series archive |
| Live/offline equivalence | Both reconstructed tables match the live publication within `1e-12` numerical tolerance; live outputs remain separate |
| Original dashboard regression | Original three metrics, full-history display, indicator controls, comparisons, and existing tests preserved |
| New dashboard tests | Three AppTest cases cover latest values, four/two/zero selected groups, five-year/custom ranges, calendar gaps, policy changes, legacy databases, and offline labeling |
| Browser verification | Four latest cards, four trend lines, 60-month five-year selection, Black–White gap metrics/chart, policy tab, and CSV download rendered successfully |
| Browser download | Downloaded 60 rows for November 2021–October 2026; every exported value/flag matches the selected SQLite data |
| Figures | All four new PNGs visually inspected; eight figures in the combined report |
| Operating schedule | `schedule=None` remains in effect; each requested Run updates all seven series and generates analysis automatically |

The new rates are **3.7% White, 6.6% Black, 2.8% Asian, and 4.7% Hispanic/Latino**, all observed in October 2026. The same-month Black–White gap is **2.90 percentage points**. Each demographic series has 286 calendar rows and 285 observed values; October 2025 remains explicitly source-missing. No missing values were interpolated.

Additional regression cases exercise conflicting duplicates, omitted calendar months, nonfinite/out-of-range values, incompatible source units/seasonal adjustment, stale/missing observations, gap arithmetic, historical revisions, migration of existing databases, and a deliberately failed second-table write. Both published modules remain unchanged when validation or the shared transaction fails. Legacy three-series archives still execute the combined notebook with an explicit demographic-data-unavailable message.

The first extended Airflow execution exposed an early Matplotlib import in the main Airflow environment. Moving analysis imports into the isolated execution path resolved it. A regression now checks that importing the report task does not load Matplotlib or nbconvert; the subsequent real seven-task execution passed. The failed attempt remains in the local audit history and did not overwrite the previously successful reports.

The current default archive contains all seven public FRED responses and a verified SHA-256 manifest. It was captured earlier on the same vintage date; replay produces the same observation values as the final live run. The original November 8 archive and its manifest remain available. Working databases, API credentials, local HTML, and offline outputs remain excluded from Git.

The Docker dashboard was healthy on port 8501 after verification. The temporary Airflow execution finished and PostgreSQL was stopped; no recurring scheduler was started. The dashboard remains available in the existing viewing session.

Minor dependency warnings did not prevent execution. Native Windows was not tested; Windows instructions continue to use WSL 2 and Docker. Offline reproduction requires the prepared runtime image; initial installation and live refresh require internet access.

## Historical verification — original three-series version

The following records describe the earlier implementation and its original 11-cell/12-artifact report. They are retained for traceability; current extension counts and provenance are listed above.

### Previous report reconciliation


The committed notebook and report artifacts correspond to successful data run `334862dbc55e2f824ea7f53d9914f484`, with analysis generated at **2026-11-09 15:13:24 UTC**. The existing outputs were checked against the local SQLite publication before submission; no new API ingestion was needed for this reconciliation.

- All seven audit stages are `SUCCESS`; SQLite integrity and the source raw-bundle checksum passed.
- All 12 report artifact hashes and the executed notebook hash match `report_manifest.json`. This includes the locally generated HTML, which remains excluded from Git and can be regenerated with Run.
- All 11 notebook code cells have successful execution counts and no error outputs. Notebook source cells are unchanged from the previous commit.
- The 322-row CSV matches SQLite. Descriptive statistics, level/change correlations, lag correlations, and written findings match calculations from that publication.
- All four PNGs were visually reviewed and match the images embedded in the notebook. The HTML displays the matching vintage and database publication timestamp.
- Observation values are unchanged from the previous published analysis. Correlation-export differences are below `1e-15`, consistent with floating-point arithmetic across execution environments.
- The focused analysis/reporting suite passed: **5 tests**, including real notebook execution, revision refresh, and failed-report preservation.

## Deployment and application verification

| Check | Observed outcome |
|---|---|
| Native Python application tests | 53 passed, 1 Airflow-specific test deselected; Python 3.13.5 |
| Linux Docker application tests | 53 passed, 1 Airflow-specific test deselected; Python 3.11.18 |
| Application coverage | 94% statement coverage (582 statements, 33 not covered) |
| GitHub Actions | Both jobs passed on GitHub-hosted Ubuntu: 53 application tests, 1 Airflow graph test, and real archived-data reproduction; no API credentials |
| Airflow import/dependency graph | 1 passed in the Apache Airflow 3.1.8 container |
| Real `dag.test()` execution | All seven tasks succeeded, including live FRED requests, SQLite publication, and notebook/report generation |
| Earlier scheduler/LocalExecutor verification | Run `verification_daily_analysis`: SUCCESS; all seven tasks SUCCESS; the current deployment uses on-demand execution |
| On-demand Run launcher | All seven tasks succeeded in a temporary Airflow container; HTML/dashboard opened; pressing Return stopped project services |
| Fresh Airflow metadata | Initialized a separate empty PostgreSQL database, executed all seven tasks successfully, and confirmed paused DAG with no next scheduled run |
| Notebook | All 11 code cells executed without errors, natively and by Airflow's isolated Docker analysis environment |
| Report provenance | All 12 report artifact hashes and the executed notebook hash match the manifest; report run ID matches SQLite publication |
| Report failure isolation | Deliberate cell failure and missing PNG reject publication; previous HTML/artifacts remain unchanged; failed analysis is audited without invalidating published data |
| No automatic schedule | DAG uses `schedule=None` and `NullTimetable`; graph regression test passes; no persistent Airflow scheduler is needed |
| Browser UI | Latest metrics, standardized comparison, relationship tab, zoom/reset, quality table, and download inspected |
| Browser CSV download | 322 rows; six selected value/quality columns plus date; values match SQLite using a DataFrame equality check |
| Streamlit interactions | After removing date controls, all 4 AppTest tests passed: full-history chart/table data, no date picker or timeline slider, indicator filtering, standardization, lag/changes controls, empty/single selection, missing database, and archived-vintage labeling |
| Docker lifecycle | PostgreSQL healthy during execution, dashboard healthy during viewing; project services stopped afterward |

The published data have **322 monthly rows (2000-01 through 2026-10)**. The latest values are UNRATE **4.1%** (2026-10), CPIAUCSL **336.298** (2026-09), and FEDFUNDS **3.88%** (2026-10). October 2025 UNRATE/CPI and unreleased October 2026 CPI are retained as null with explicit flags.

The suite exercises pagination, rate-limit retries, sanitized HTTP/timeout errors, duplicate conflicts, source missingness, missing-month rejection, release-date differences, warm-up inflation, invalid values, stale data, derived identities, raw-checksum tampering, idempotent reruns, historical revisions, transaction rollback, rejected updates preserving the prior publication, CLI exports, and analysis artifacts. Reporting integration tests execute real Jupyter kernels, verify refreshed exports after a historical revision, reject a mismatched run ID, and exercise failed-cell/missing-figure preservation.

Nine launcher tests cover interactive completion/cleanup, failed-run cleanup without opening the dashboard, starting/stopping an owned Colima VM from either the `colima` or `default` Docker context, preserving other running containers, rejecting duplicate Run windows, preparing the offline runtime, and replaying without a key/build/PostgreSQL. They use isolated command doubles; the real launcher was also executed against Docker and the live FRED API.

The interactive Run verification published data run `8fdcf9538f1f79ea43175d3e9fe47b9e`. All 12 artifact hashes and the executed notebook hash were checked against its manifest, and all seven SQLite audit stages were SUCCESS. The outputs comprise one HTML report, four PNG figures, five CSV tables/data exports, findings Markdown, and a JSON analysis summary, plus the executed notebook and checksum manifest. Later verification runs can refresh these artifacts; `reports/report_manifest.json` identifies the latest published analysis.

The final cold-start Run verification began with Colima stopped, started Docker, migrated/reserialized Airflow metadata, and published data run `1eb927118675684d0aff359cbc85af2d` with matching analysis at **2026-11-09 02:54:40 UTC**. All seven tasks, 11 notebook code cells, and 12 report artifact checks passed. Reserialization explicitly recorded `next_dagrun=None` and `run_after=None`. The dashboard was healthy during viewing, and both persistent containers had restart policy `no`. Pressing Return exited successfully, removed the launcher lock, stopped project services, and shut down the Colima VM; its stopped state was independently confirmed.

## Issues found and resolved

- The first live validation exposed an actual October 2025 source gap. Official BLS documentation confirmed it. Explicit source-missing observations now remain null with warnings and a documented 5% threshold; omitted payload months still fail.
- The first Docker test invocation passed all tests but failed to write coverage into the image's root-owned working directory. Coverage and pytest caches now use writable `/tmp` paths; rerunning exited successfully.
- The first live Airflow run revealed that `run_id` is a reserved TaskFlow context argument. Task parameters were renamed `pipeline_run_id`; a graph regression check covers this, and both direct and scheduler-driven full DAG runs succeeded.
- Adding the notebook runtime exposed the original Docker VM's 10 GB disk limit. The Airflow image now installs a minimal, separately hash-locked analysis environment instead of the entire dashboard/JupyterLab stack. The local VM disk was expanded to 30 GB.
- Running kernel integration tests alongside the live DAG exhausted the original 2 GB Docker VM memory and interrupted a smoke test (exit 137). The VM now has 4 CPUs and 8 GB RAM. The interrupted run remains recorded as failed; rerunning the complete seven-task smoke test and the scheduler-driven DAG succeeded.
- Earlier runs interrupted or superseded during development are retained as failed audit records. No failed or older snapshot replaced the final successful publication.
- The first cold-start launcher check found that stopping Colima resets Docker's context to `default`. The launcher now handles both `default` and `colima` contexts, with regression tests. A subsequent real cold-start run succeeded.

Minor dependency warnings were emitted by Matplotlib/Jupyter; the official Airflow base also emits a Requests optional-detection dependency warning. They did not prevent execution. No tests are marked xfail, and no task was skipped in either successful full DAG verification run.

## Scope and evidence

The executed notebook, generated statistics/figures, findings, and this report are repository artifacts. Working SQLite files, per-run raw history, temporary logs, and credentials remain local; a reviewed raw-data archive is included under `snapshots/`. Live end-to-end verification was performed locally with the configured key. The active [GitHub Actions workflow](../.github/workflows/ci.yml) uses no FRED secret. [Run 42559034886](https://github.com/xingsun19/us-macroeconomic-pipeline-dashboard/actions/runs/42559034886), at commit `3481ee2`, passed both jobs: 53 application tests with 94% coverage, one Airflow graph test, and archived-data reconstruction yielding 322 rows and 11 executed notebook code cells. CI runs on pushes and pull requests, separately from the on-demand local deployment.

This is a local, on-demand Docker deployment. The daily schedule has been removed. The host only needs to be available while running or viewing the dashboard; HTML reports remain usable with Docker stopped. No claim is made about five years of uninterrupted third-party service availability.

## Archived-data reproduction verification

- Preserved the real FRED response bundle for vintage 2026-11-08 (112,353 bytes, 1,001 source observations including the warm-up year), with a SHA-256 and provenance manifest.
- Executed `scripts/run.sh --offline --batch` from a separate clean checkout configuration with an empty API key. Docker inspection confirmed the replay container's network mode was `none`.
- Rebuilt 322 published months matching the current database within floating-point tolerance; executed all 11 notebook code cells and verified hashes for all 12 report artifacts plus the exported notebook.
- Confirmed the offline database and reports were written only under `data/offline/` and `reports/offline/`. The live dashboard continued running during this isolated test.
- Started a separate dashboard on port 8502 using the rebuilt database on a read-only mount, with no API key. Its health endpoint returned `ok`; AppTest verified three metrics, all 322 rows, an archived-vintage banner, and no runtime errors. The preview container was stopped after verification.
- A container test exposed notebook file permissions inherited from locally generated outputs. The application image now makes its bundled notebook readable to the runtime user; the full Linux suite and offline replay passed after rebuilding.
- Windows instructions follow the official WSL 2 and Docker documentation. No Windows host was available, so native Windows execution is not claimed.
