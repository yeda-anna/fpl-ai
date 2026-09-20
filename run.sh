#!/usr/bin/env bash
# Start the local FPL Copilot app.
set -e
cd "$(dirname "$0")"
PORT="${PORT:-8787}"
exec ./.venv/bin/uvicorn main:app --app-dir backend --host 127.0.0.1 --port "$PORT" "$@"
