"""Execute the real seven-task Airflow DAG once, without a persistent scheduler."""

import importlib.util
import json
from pathlib import Path


def main():
    path = Path("/opt/airflow/dags/us_macro_pipeline.py")
    spec = importlib.util.spec_from_file_location("macro_manual_run", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Airflow's local DAG runner executes real operators and retains their audit
    # records. Production retry/timeout settings remain in effect.
    run = module.dag.test()
    states = {ti.task_id: str(ti.state) for ti in run.get_task_instances()}
    print(json.dumps({"run_id": run.run_id, "state": str(run.state), "tasks": states}, indent=2))
    if str(run.state) != "success" or len(states) != 7 or set(states.values()) != {"success"}:
        raise RuntimeError("The complete data and analysis run did not succeed.")


if __name__ == "__main__":
    main()
