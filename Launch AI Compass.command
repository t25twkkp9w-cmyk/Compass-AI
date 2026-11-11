#!/usr/bin/env bash
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
export COMPASS_WEB_RUNTIME="$APP_DIR/.runtime-browser"
exec ./run-web.sh --port 8601
