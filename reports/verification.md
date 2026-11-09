# Verification record

Verified on **November 8, 2026 (America/Chicago)**. Container/audit timestamps use UTC and therefore extend into November 9. FRED data vintage: **2026-11-08**.

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
