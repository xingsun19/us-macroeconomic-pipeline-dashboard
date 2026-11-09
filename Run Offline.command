#!/usr/bin/env bash
# Replay the packaged data without contacting FRED.
exec bash "$(dirname "$0")/Run.command" --offline "$@"
