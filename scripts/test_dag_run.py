"""Execute all real Airflow tasks against the configured FRED/SQLite environment."""

import importlib.util
import json
from pathlib import Path

path = Path("/opt/airflow/dags/us_macro_pipeline.py")
spec = importlib.util.spec_from_file_location("macro_dag_test", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
# Keep the production retry policy, but fail immediately in this smoke-test process.
for task in module.dag.tasks:
    task.retries = 0
run = module.dag.test()
states = {ti.task_id: str(ti.state) for ti in run.get_task_instances()}
print(json.dumps({"dag_id": run.dag_id, "state": str(run.state), "tasks": states}, indent=2))
assert str(run.state) == "success", "The real DAG run did not succeed."
assert len(states) == 6 and set(states.values()) == {"success"}
