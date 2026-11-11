#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
if [ ! -x .venv/bin/python ]; then
  echo 'Install uv, then run: uv sync --python 3.12'
  exit 1
fi
exec .venv/bin/python -m streamlit run app.py "$@"
