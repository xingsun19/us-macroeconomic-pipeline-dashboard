#!/usr/bin/env bash
# Run the complete DAG only on request; keep only the dashboard open for viewing.
set -euo pipefail
cd "$(dirname "$0")/.."
batch=false
offline=false
prepare_offline=false
for option in "$@"; do
  case "$option" in
    --batch) batch=true ;;
    --offline) offline=true ;;
    --prepare-offline) prepare_offline=true ;;
    *) echo "Usage: bash scripts/run.sh [--offline] [--batch] [--prepare-offline]"; exit 2 ;;
  esac
done
if [ "$offline" = true ] && [ "$prepare_offline" = true ]; then
  echo "Prepare the offline runtime first, then run with --offline."
  exit 2
fi
offline_compose() { docker compose -p us-macro-offline -f compose.offline.yaml "$@"; }
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
    docker rm -f us-macro-offline-run >/dev/null 2>&1 || true
    docker compose stop airflow dashboard postgres >/dev/null 2>&1 || true
    offline_compose stop dashboard >/dev/null 2>&1 || true
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
  if [ "$offline" = false ] && [ "$prepare_offline" = false ]; then
    echo "Created .env. Set FRED_API_KEY there and run again."
    exit 1
  fi
fi
if [ "$offline" = false ] && [ "$prepare_offline" = false ] && ! grep -Eq '^FRED_API_KEY=[a-z0-9]{32}$' .env; then
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
offline_compose stop dashboard >> "$log" 2>&1
if [ "$prepare_offline" = true ]; then
  echo "Downloading and building the offline runtime (internet required once)..."
  docker compose build dashboard >> "$log" 2>&1
  echo "Offline runtime ready. Next time use Run Offline.command or bash scripts/run.sh --offline."
  exit 0
fi
if [ "$offline" = true ]; then
  if ! docker image inspect us-macro-app:1.0.0 >/dev/null 2>&1; then
    echo "Prepare the runtime while online first: bash scripts/run.sh --prepare-offline"
    exit 1
  fi
  echo "Replaying the archived FRED snapshot without API access..."
  offline_compose run --rm --no-deps --pull never --name us-macro-offline-run replay >> "$log" 2>&1
  report_path=reports/offline/eda.html
else
  echo "Preparing the project (the first run may take several minutes)..."
  docker compose build airflow dashboard >> "$log" 2>&1
  docker compose up -d --wait --wait-timeout 120 postgres >> "$log" 2>&1
  echo "Updating FRED data and generating the complete analysis..."
  docker compose run --rm --no-deps --name us-macro-manual-run airflow bash -c 'airflow db migrate && airflow dags reserialize && python /opt/project/scripts/run_dag_once.py' >> "$log" 2>&1
  docker compose stop postgres >> "$log" 2>&1
  report_path=reports/eda.html
fi
echo "Analysis complete: $report_path"
if [ "$batch" = true ]; then
  exit 0
fi
if [ "$offline" = true ]; then
  offline_compose up -d --no-deps --pull never --wait --wait-timeout 90 dashboard >> "$log" 2>&1
else
  docker compose up -d --no-deps --wait --wait-timeout 90 dashboard >> "$log" 2>&1
fi
echo "Dashboard: http://localhost:8501"
if [ "$(uname -s)" = Darwin ]; then
  open "$report_path" || true
  open http://localhost:8501 || true
fi
echo "The dashboard is available only while this Run window stays open."
echo "The HTML report remains available after all services stop."
read -r -p "When finished viewing, press Return to stop services and release resources. " _ || true
