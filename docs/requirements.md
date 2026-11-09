# Assignment and scope mapping

Source: user-provided **Final Project (2).ipynb**, *Topics in Data Engineering — Final Project — Northwestern University Fall 2026*. It contains one Markdown cell. Requirements are paraphrased below; instructor scheduling/group instructions do not authorize contacting anyone.

| Requirement | Evidence |
|---|---|
| Read API data | Authenticated FRED metadata and paginated observations; verified live runs |
| Store API data in a database | SQLite raw JSON, normalized observations, staging, curated tables, and audit records |
| DAG covering/measuring the full pipeline | Seven Airflow tasks, status/duration, retries/timeouts, validation, read-back, and automatic notebook/HTML/chart generation |
| Easy-to-run repository | English README, example config, dependency lock, Docker Compose, double-click Run launcher, executed tests, optional CI template |
| EDA with key insights | Executed notebook, statistics, trends, correlations/lags, figures, computed findings and limitations |
| Reproducible now and years later | Pins/hashes, vendored constraints, image digests, explicit vintages, raw checksums, archive guidance; external availability cannot be guaranteed |
| GitHub code repository | Complete project and instructions |
| PowerPoint | Deferred explicitly at the user's request |
| Week 10 classroom presentation | Student/team responsibility; not completed by this implementation |
| Team of 4–5 and Week 6 membership/API approval | Course coordination to confirm with the instructor; no message was sent |

Additional user requirements implemented: three specified series, 2000–present analysis, explicit missing-value handling, derived variables, SQLite updates, executable Apache Airflow, a separate Streamlit/Plotly dashboard reading SQLite, flexible dates/indicators, comparisons/zoom/download, real execution/testing, English code/docs/UI, and no committed API key.

All five core technical requirements are addressed. This delivery does not claim the course coordination, slide submission, or classroom presentation has occurred.

At the user's request, execution is now on demand: `schedule=None`, no catchup, and no automatic container restart. Clicking Run executes the complete seven-task DAG and regenerates analysis; pressing Return after viewing stops services. The Airflow DAG and audit records remain part of the project, without a recurring background workload.
