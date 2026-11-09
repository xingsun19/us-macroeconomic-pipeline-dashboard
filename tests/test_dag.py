from pathlib import Path
import inspect
import subprocess
import sys
import pytest

pytestmark = pytest.mark.airflow


def test_report_task_import_keeps_analysis_dependencies_isolated():
    subprocess.run([sys.executable, "-c", "import sys; import macro_pipeline.reporting; assert 'matplotlib' not in sys.modules; assert 'nbconvert' not in sys.modules"], check=True)


def test_dag_import_and_dependency_graph():
    pytest.importorskip("airflow")
    from airflow.models import DagBag
    folder = Path("/opt/airflow/dags")
    bag = DagBag(dag_folder=str(folder), include_examples=False)
    assert not bag.import_errors
    dag = bag.dags["us_macro_pipeline"]
    expected = ["extract_api", "store_raw", "clean_transform", "validate_quality", "publish_database", "verify_update", "generate_analysis"]
    assert set(dag.task_ids) == set(expected)
    for upstream, downstream in zip(expected, expected[1:]):
        assert dag.get_task(upstream).downstream_task_ids == {downstream}
    assert dag.max_active_runs == 1
    assert not dag.catchup
    assert dag.schedule is None
    from airflow.timetables.simple import NullTimetable
    assert isinstance(dag.timetable, NullTimetable)
    assert dag.get_task("generate_analysis").trigger_rule == "all_success"
    for task in dag.tasks:
        # Airflow context names cannot also be positional TaskFlow parameters.
        assert 'run_id' not in inspect.signature(task.python_callable).parameters
