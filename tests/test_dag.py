from pathlib import Path
import inspect
import pytest

pytestmark = pytest.mark.airflow


def test_dag_import_and_dependency_graph():
    pytest.importorskip("airflow")
    from airflow.models import DagBag
    folder = Path("/opt/airflow/dags")
    bag = DagBag(dag_folder=str(folder), include_examples=False)
    assert not bag.import_errors
    dag = bag.dags["us_macro_pipeline"]
    expected = ["extract_api", "store_raw", "clean_transform", "validate_quality", "publish_database", "verify_update"]
    assert set(dag.task_ids) == set(expected)
    for upstream, downstream in zip(expected, expected[1:]):
        assert dag.get_task(upstream).downstream_task_ids == {downstream}
    assert dag.max_active_runs == 1
    assert not dag.catchup
    for task in dag.tasks:
        # Airflow context names cannot also be positional TaskFlow parameters.
        assert 'run_id' not in inspect.signature(task.python_callable).parameters
