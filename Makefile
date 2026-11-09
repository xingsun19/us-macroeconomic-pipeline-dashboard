.PHONY: up down update test eda notebook dag-test status
up:
	bash scripts/start.sh
down:
	docker compose down
update:
	docker compose run --rm pipeline macro-pipeline update
test:
	docker compose run --rm --no-deps tests
eda:
	docker compose run --rm --no-deps notebook python scripts/execute_notebook.py
notebook:
	docker compose --profile tools up -d notebook
dag-test:
	docker compose exec airflow python /opt/project/scripts/test_dag_run.py
status:
	docker compose ps
	docker compose run --rm --no-deps pipeline macro-pipeline status
