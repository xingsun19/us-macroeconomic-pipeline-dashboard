#!/usr/bin/env bash
# Configure host-owned bind mounts and start the complete local Docker stack.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo "Created .env. Set FRED_API_KEY there, then run this script again."
  exit 1
fi
if ! grep -Eq '^FRED_API_KEY=[a-z0-9]{32}$' .env; then
  echo "Set a valid FRED_API_KEY in .env before starting."
  exit 1
fi
if ! grep -q '^LOCAL_UID=' .env; then
  printf '\nLOCAL_UID=%s\nLOCAL_GID=%s\n' "$(id -u)" "$(id -g)" >> .env
fi
chmod 600 .env
mkdir -p data reports
docker compose up --build -d
echo "Dashboard: http://localhost:8501"
echo "Airflow: http://localhost:8080 (username: admin)"
echo "Read the generated Airflow password locally:"
echo "docker compose exec airflow cat /opt/airflow/state/passwords.json"
