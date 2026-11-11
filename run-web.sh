#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
exec .venv/bin/python -m uvicorn webapp:app --host 127.0.0.1 --port 8600 "$@"
