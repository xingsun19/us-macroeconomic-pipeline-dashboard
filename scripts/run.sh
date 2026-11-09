#!/usr/bin/env bash
# Run the complete DAG only on request; keep only the dashboard open for viewing.
set -euo pipefail
cd "$(dirname "$0")/.."
batch=false
if [ "${1:-}" = "--batch" ]; then
  batch=true
elif [ "$#" -ne 0 ]; then
  echo "Usage: bash scripts/run.sh [--batch]"
  exit 2
fi
mkdir -p data reports logs
lock=data/.run-lock
if ! mkdir "$lock" 2>/dev/null; then
  previous_pid=$(cat "$lock/pid" 2>/dev/null || true)
  if [ -n "$previous_pid" ] && ! kill -0 "$previous_pid" 2>/dev/null; then
    rm -f "$lock/pid"
    rmdir "$lock"
    mkdir "$lock"
  else
    echo "Another Run window is already open. Finish or close that window first."
    exit 1
  fi
fi
echo "$$" > "$lock/pid"
engine_ready=false
started_colima=false
cleanup() {
  result=$?
  trap - EXIT INT TERM HUP
  if [ "$engine_ready" = true ]; then
    echo "Stopping project services..."
    docker rm -f us-macro-manual-run >/dev/null 2>&1 || true
    docker compose stop airflow dashboard postgres >/dev/null 2>&1 || true
  fi
  # Never shut down a VM that was already running before this launcher, or one
  # that now has other running containers.
  if [ "$started_colima" = true ] && docker info >/dev/null 2>&1; then
    if containers=$(docker ps -q) && [ -z "$containers" ]; then
      colima stop >> "$log" 2>&1 || true
    else
      echo "Other containers are running; leaving their Docker VM available."
    fi
  fi
  rm -f "$lock/pid"
  rmdir "$lock" 2>/dev/null || true
  if [ "$result" -ne 0 ]; then
    echo "Run failed. Any previous successful reports remain available. See the log in logs/."
  fi
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
log="logs/run-$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee -a "$log") 2>&1
echo "U.S. Macroeconomic Pipeline - Run once"
echo "No timed or recurring jobs will be created."
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo "Created .env. Set FRED_API_KEY there and run again."
  exit 1
fi
if ! grep -Eq '^FRED_API_KEY=[a-z0-9]{32}$' .env; then
  echo "Set a valid FRED_API_KEY in .env before running."
  exit 1
fi
if ! grep -q '^LOCAL_UID=' .env; then
  printf '\nLOCAL_UID=%s\nLOCAL_GID=%s\n' "$(id -u)" "$(id -g)" >> .env
fi
chmod 600 .env
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Desktop or Docker with Colima first."
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Starting Docker..."
  context=$(docker context show)
  # Colima switches the Docker context back to default when it stops.
  if command -v colima >/dev/null 2>&1 && { [ "$context" = "colima" ] || [ "$context" = "default" ]; }; then
    started_colima=true
    colima start >> "$log" 2>&1
  elif [ "$(uname -s)" = Darwin ] && command -v open >/dev/null 2>&1; then
    open -g -a Docker
  else
    echo "Start your Docker engine and run again."
    exit 1
  fi
  attempts=0
  until docker info >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 60 ]; then
      echo "Docker did not become ready within two minutes."
      exit 1
    fi
    sleep 2
  done
fi
engine_ready=true
docker compose version >/dev/null
# Stop the previous persistent deployment before running the same DAG once.
docker compose stop airflow dashboard postgres >> "$log" 2>&1
echo "Preparing the project (the first run may take several minutes)..."
docker compose build airflow dashboard >> "$log" 2>&1
docker compose up -d --wait --wait-timeout 120 postgres >> "$log" 2>&1
echo "Updating FRED data and generating the complete analysis..."
docker compose run --rm --no-deps --name us-macro-manual-run airflow bash -c 'airflow db migrate && airflow dags reserialize && python /opt/project/scripts/run_dag_once.py' >> "$log" 2>&1
docker compose stop postgres >> "$log" 2>&1
echo "Analysis complete: reports/eda.html and notebooks/01_macroeconomic_eda.ipynb"
if [ "$batch" = true ]; then
  exit 0
fi
docker compose up -d --no-deps --wait --wait-timeout 90 dashboard >> "$log" 2>&1
echo "Dashboard: http://localhost:8501"
if [ "$(uname -s)" = Darwin ]; then
  open reports/eda.html || true
  open http://localhost:8501 || true
fi
echo "The dashboard is available only while this Run window stays open."
echo "The HTML report remains available after all services stop."
read -r -p "When finished viewing, press Return to stop services and release resources. " _ || true
