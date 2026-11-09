#!/usr/bin/env bash
# Backward-compatible entry point for an on-demand run.
set -euo pipefail
exec bash "$(dirname "$0")/run.sh" "$@"
