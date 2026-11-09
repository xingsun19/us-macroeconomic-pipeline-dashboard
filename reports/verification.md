# Verification record

Verified on **November 8, 2026 (America/Chicago)**. Container/audit timestamps use UTC and therefore extend into November 9. FRED data vintage: **2026-11-08**.

| Check | Observed outcome |
|---|---|
| Native Python application tests | 35 passed, 1 Airflow-specific test deselected; Python 3.13.5 |
| Linux Docker application tests | 35 passed, 1 Airflow-specific test deselected; Python 3.11.18 |
| Application coverage | 95% statement coverage (457 statements, 24 not covered) |
| Airflow import/dependency graph | 1 passed in the Apache Airflow 3.1.8 container |
| Real `dag.test()` execution | All six tasks succeeded, with live FRED API requests and SQLite publication |
| Real scheduler/LocalExecutor execution | Run `verification_scheduler`: SUCCESS; all six tasks SUCCESS |
| Notebook | All 11 code cells executed without errors, natively and in Docker; HTML and figures exported |
| Browser UI | Latest metrics, standardized comparison, relationship tab, zoom/reset, quality table, and download inspected |
| Browser CSV download | 322 rows; six selected value/quality columns plus date; values match SQLite using a DataFrame equality check |
| Streamlit interactions | AppTest verifies date filtering, indicator filtering, standardization, lag/changes controls, empty selection, short windows, missing database |
| Docker readiness | Dashboard, PostgreSQL, Airflow API, scheduler, DAG processor, and triggerer healthy |

The published data have **322 monthly rows (2000-01 through 2026-10)**. The latest values are UNRATE **4.1%** (2026-10), CPIAUCSL **336.298** (2026-09), and FEDFUNDS **3.88%** (2026-10). October 2025 UNRATE/CPI and unreleased October 2026 CPI are retained as null with explicit flags.

The suite exercises pagination, rate-limit retries, sanitized HTTP/timeout errors, duplicate conflicts, source missingness, missing-month rejection, release-date differences, warm-up inflation, invalid values, stale data, derived identities, raw-checksum tampering, idempotent reruns, historical revisions, transaction rollback, rejected updates preserving the prior publication, CLI exports, and analysis artifacts.

## Issues found and resolved

- The first live validation exposed an actual October 2025 source gap. Official BLS documentation confirmed it. Explicit source-missing observations now remain null with warnings and a documented 5% threshold; omitted payload months still fail.
- The first Docker test invocation passed all tests but failed to write coverage into the image's root-owned working directory. Coverage and pytest caches now use writable `/tmp` paths; rerunning exited successfully.
- The first live Airflow run revealed that `run_id` is a reserved TaskFlow context argument. Task parameters were renamed `pipeline_run_id`; a graph regression check covers this, and both direct and scheduler-driven full DAG runs succeeded.
- Earlier runs interrupted or superseded during development are retained as failed audit records. No failed or older snapshot replaced the final successful publication.

Minor dependency deprecation warnings were emitted by Matplotlib's parser integration; the official Airflow base also emits a Requests optional-detection dependency warning. They did not prevent execution. No tests are marked xfail, and no live DAG task was skipped.

## Scope and evidence

The executed notebook, generated statistics/figures, findings, and this report are repository artifacts. Raw JSON, SQLite files, temporary logs, and credentials remain local. The CI template uses offline fixtures and checks DAG structure without a FRED secret; live end-to-end verification was performed locally with the configured key. Remote CI is not claimed: GitHub rejected active workflow publication because the current OAuth credential lacks `workflow` scope. The complete configuration is retained as `.github/ci-template.yml` for optional activation after authorization.

This is a local Docker deployment. The daily schedule is enabled, but the host must stay on. No claim is made about five years of uninterrupted third-party service availability. PowerPoint, group/API approval, and classroom presentation are outside the completed technical scope.
