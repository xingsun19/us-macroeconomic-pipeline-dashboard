"""Daily end-to-end FRED update; task boundaries match auditable pipeline stages."""

from datetime import timedelta
import hashlib

import pendulum
from airflow.sdk import dag, task, get_current_context

from macro_pipeline.config import Settings
from macro_pipeline import pipeline


@dag(
    dag_id="us_macro_pipeline",
    description="Extract FRED, persist raw data, transform, validate, and atomically publish SQLite",
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
        return pipeline.verify(Settings.from_env(), pipeline_run_id)

    verify_update(publish_database(validate_quality(clean_transform(store_raw(extract_api())))))


dag = macro_dag()

if __name__ == "__main__":
    dag.test()
