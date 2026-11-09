FROM apache/airflow:3.1.8-python3.11@sha256:cf1ea4e3406c0f36d90471f341447d3425ddf4149fd98b1307f0b2de2f1abf72
USER root
RUN mkdir -p /opt/airflow/state && chown airflow:root /opt/airflow/state && chmod 2775 /opt/airflow/state
USER airflow
WORKDIR /opt/project
COPY --chown=airflow:root docker/airflow-constraints.txt /opt/project/airflow-constraints.txt
RUN pip install "apache-airflow==3.1.8" "pandas==2.3.3" "python-dotenv==1.2.2" "requests==2.32.5" "pytest==8.4.2" --constraint /opt/project/airflow-constraints.txt
COPY --chown=airflow:root pyproject.toml README.md ./
COPY --chown=airflow:root src ./src
RUN pip install --no-deps .
COPY --chown=airflow:root dags /opt/airflow/dags
COPY --chown=airflow:root tests /opt/project/tests
COPY --chown=airflow:root scripts /opt/project/scripts
WORKDIR /opt/airflow
