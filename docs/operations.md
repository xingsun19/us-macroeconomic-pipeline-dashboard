# Operations and maintenance

## EDA and testing

```bash
# Optional report-only rerun; the Run launcher already performs this step
docker compose run --rm --no-deps notebook python scripts/execute_notebook.py

# Interactive JupyterLab; use the generated token from the local logs
docker compose --profile tools up -d notebook
docker compose logs notebook
# Open http://localhost:8888 with that token

# Offline tests; no API requests or key required
docker compose run --rm --no-deps tests

# Airflow import and dependency graph
docker compose run --rm --no-deps airflow python -m pytest /opt/project/tests/test_dag.py -q

# Real seven-task smoke test, including report generation
# Wait for any active Run window to finish before this isolated smoke test
docker compose up -d --wait postgres
docker compose run --rm --no-deps airflow db migrate
docker compose run --rm --no-deps airflow python /opt/project/scripts/test_dag_run.py
docker compose stop postgres

# Complete on-demand run with production retries; clean up afterward
bash scripts/run.sh --batch
```

The smoke test calls the live FRED API and skips no tasks. It disables retries only in its own process to fail promptly. Production tasks retain two retries, a two-minute delay, and ten-minute task timeouts; the DAG timeout is 45 minutes. The included CI template runs deterministic synthetic fixtures and separately checks the real DAG; fixtures are never used by production ingestion.

The Run launcher initializes/migrates Airflow's metadata database, then uses Airflow's local `dag.test()` execution mode with the real operators, FRED API, SQLite publication, production retries, and persistent PostgreSQL audit records. The temporary container is removed after execution; it does not launch a recurring scheduler. For optional UI inspection, explicitly start `docker compose up -d --build airflow` and open [http://localhost:8080](http://localhost:8080) as `admin`. Read its local password with `docker compose exec airflow cat /opt/airflow/state/passwords.json`. Stop it afterward using `docker compose stop airflow postgres`. Even in UI mode, `schedule=None` disables timed runs.


The executed notebook contains descriptive statistics, trends, annual summaries/counts, level/change correlations, pair counts, subperiod comparisons, rolling correlations, lead–lag analysis, and computed findings. The executed `.ipynb`, PNG figures, CSV summaries, and [findings](../reports/findings.md) are tracked. `reports/eda.html` is generated locally and ignored by Git.

## Native Python alternative

Python 3.11 is the reference runtime; the application is also tested locally on Python 3.13. Keep Airflow isolated in its container.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
python -m pip install --no-deps -e .
cp .env.example .env  # Skip if already configured; edit your own key
macro-pipeline update
macro-pipeline validate
python scripts/execute_notebook.py
streamlit run dashboard/app.py
```

Stop the Docker dashboard first if using the same port. Local tests: `pytest -m 'not airflow and not live'`. For offline Docker tests on a fresh clone, create `.env` from the example (an empty key is sufficient), build the image, and run the test command with `--no-deps`.

## Updates and historical reproduction

```bash
docker compose run --rm pipeline macro-pipeline update
docker compose run --rm --no-deps pipeline macro-pipeline validate
docker compose run --rm --no-deps pipeline macro-pipeline export --output /app/reports
docker compose run --rm --no-deps pipeline macro-pipeline analyze --output /app/reports
docker compose down  # Data and named volumes persist

# Reproduce the submitted vintage in a separate database
docker compose run --rm --no-deps \
  -e MACRO_DB_PATH=/app/data/vintage-2026-11-08.db \
  pipeline macro-pipeline update --as-of 2026-11-08
```

Point `MACRO_DB_PATH` at the separate database when analyzing that historical snapshot. A vintage snapshot is not a look-ahead-free real-time backtest. Do not set `MACRO_AS_OF` permanently when requesting current data.

## Troubleshooting, security, and maintenance

- **API key:** edit `.env`; never commit it. Errors are sanitized. Do not share raw request URLs or unfiltered Airflow logs, which may contain generated login credentials.
- **Compose missing:** install Docker Desktop or the official plugin. Homebrew Docker/Colima users can install `docker-compose` and follow its plugin-directory instructions.
- **Permissions:** the startup script sets `LOCAL_UID`/`LOCAL_GID`. Update these in `.env` if moving the checkout to another host.
- **Colima bind mounts:** keep the checkout in a shared writable location such as the macOS home directory. Temporary folders outside Colima's shared paths can appear as root-owned directories inside containers.
- **Airflow startup:** allow up to two minutes for migrations. Check `docker compose ps` and task logs.
- **Exit code 137 or builds running out of space:** check the Docker VM's memory and disk, not only the host's free resources. Allocate the recommended resources above. Colima users can stop the VM and restart it with `colima start --cpu 4 --memory 8 --disk 30`; restarting interrupts other containers on that VM.
- **Validation failure:** inspect SQLite run/step records and retained raw JSON. Fix the source/configuration issue and rerun; do not silently fill data or relax checks.
- **Old dashboard:** finish the current Run window, then click Run again to fetch current data and regenerate all outputs. A browser refresh alone does not fetch FRED data.
- **Backups:** back up `data/` and the Airflow PostgreSQL volume. Use SQLite's backup API while writers are running instead of copying only the `.db` file and omitting its WAL.
- **Long-term reproduction:** Python dependencies are version/hash locked; Airflow constraints are vendored; Python/Airflow base images use digests. Archive Docker images, raw JSON, SQLite backups, and a Git release together. External APIs and registries cannot be guaranteed in five years. Regenerate the lock and rerun all tests after intentional dependency upgrades.
