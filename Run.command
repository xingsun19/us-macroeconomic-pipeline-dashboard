#!/usr/bin/env bash
# Finder launches this file in Terminal on macOS.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$(dirname "$0")" || exit 1
status=0
bash scripts/run.sh "$@" || status=$?
if [ "$status" -ne 0 ] && [ -t 0 ]; then
  read -r -p "Run failed. Review the message above, then press Return to close. " _ || true
fi
exit "$status"
