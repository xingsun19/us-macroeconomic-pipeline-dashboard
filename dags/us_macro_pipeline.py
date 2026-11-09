"""Daily end-to-end FRED update; task boundaries match auditable pipeline stages."""

from datetime import timedelta
import hashlib
import os
from pathlib import Path

import pendulum
from airflow.sdk import dag, task, get_current_context

from macro_pipeline.config import Settings
from macro_pipeline import pipeline


@dag(
    dag_id="us_macro_pipeline",
    description="Update FRED/SQLite, execute the EDA notebook, and publish HTML reports and charts",
    schedule="0 18 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "macro-research", "retries": 2, "retry_delay": timedelta(minutes=2), "execution_timeout": timedelta(minutes=10)},
    dagrun_timeout=timedelta(minutes=45),
    tags=["fred", "macroeconomics", "sqlite", "final-project"],
    doc_md="""Refresh all three monthly FRED series daily at 18:00 UTC, including historical revisions.
    The small full-history refresh is intentional. XCom carries only a run identifier.
    A failing extraction or validation leaves the previously published dataset intact.
    Run durations and quality results are also recorded in the application SQLite database.
    No API calls or database connections occur while importing this file.
    After read-back verification, an isolated Python environment executes every EDA cell.
    HTML, PNG figures, statistics, and findings are published only after successful analysis.
    """,
)
def macro_dag():
    @task
    def extract_api():
        context = get_current_context()
        # Stable across Airflow task retries; safe as a filename and database key.
        run_id = hashlib.sha256(context["run_id"].encode()).hexdigest()[:32]
        return pipeline.extract(Settings.from_env(), run_id=run_id)

    @task
    def store_raw(pipeline_run_id: str):
        return pipeline.store_raw(Settings.from_env(), pipeline_run_id)

    @task
    def clean_transform(pipeline_run_id: str):
        return pipeline.clean(Settings.from_env(), pipeline_run_id)

    @task
    def validate_quality(pipeline_run_id: str):
        return pipeline.validate(Settings.from_env(), pipeline_run_id)

    @task
    def publish_database(pipeline_run_id: str):
        return pipeline.publish(Settings.from_env(), pipeline_run_id)

    @task
    def verify_update(pipeline_run_id: str):
        pipeline.verify(Settings.from_env(), pipeline_run_id)
        return pipeline_run_id

    @task
    def generate_analysis(pipeline_run_id: str):
        from macro_pipeline.reporting import run_analysis_task
        return run_analysis_task(
            Settings.from_env(), pipeline_run_id,
            os.environ["MACRO_ANALYSIS_PYTHON"],
            Path("/opt/project/scripts/execute_notebook.py"),
        )

    generate_analysis(verify_update(publish_database(validate_quality(clean_transform(store_raw(extract_api()))))))


dag = macro_dag()

if __name__ == "__main__":
    dag.test()
