FROM apache/airflow:3.1.8-python3.11@sha256:cf1ea4e3406c0f36d90471f341447d3425ddf4149fd98b1307f0b2de2f1abf72
USER root
RUN mkdir -p /opt/airflow/state && chown airflow:root /opt/airflow/state && chmod 2775 /opt/airflow/state
RUN python -m venv /opt/analysis-venv && chown -R airflow:root /opt/analysis-venv
USER airflow
WORKDIR /opt/project
COPY --chown=airflow:root requirements-analysis.lock /opt/project/requirements-analysis.lock
RUN /opt/analysis-venv/bin/pip install --no-cache-dir --require-hashes -r /opt/project/requirements-analysis.lock \
    && /opt/analysis-venv/bin/python -m ipykernel install --sys-prefix --name macro-analysis --display-name "Python (macro analysis)"
COPY --chown=airflow:root docker/airflow-constraints.txt /opt/project/airflow-constraints.txt
RUN pip install "apache-airflow==3.1.8" "pandas==2.3.3" "python-dotenv==1.2.2" "requests==2.32.5" "pytest==8.4.2" --constraint /opt/project/airflow-constraints.txt
COPY --chown=airflow:root pyproject.toml README.md ./
COPY --chown=airflow:root src ./src
RUN pip install --no-deps .
RUN /opt/analysis-venv/bin/pip install --no-deps .
COPY --chown=airflow:root dags /opt/airflow/dags
COPY --chown=airflow:root tests /opt/project/tests
COPY --chown=airflow:root scripts /opt/project/scripts
COPY --chown=airflow:root notebooks /opt/project/notebooks
WORKDIR /opt/airflow
