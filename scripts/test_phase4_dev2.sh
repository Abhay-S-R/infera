#!/usr/bin/env bash
# Phase 4 Dev 2 test runner — from repo root: ./scripts/test_phase4_dev2.sh [--live]
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PY:-.venv/bin/python}"
if [[ ! -x "$PY" ]]; then
  PY=python3
fi

echo "Using Python: $PY"
echo "Ensure Postgres is up: docker compose up -d"
echo ""

exec "$PY" scripts/test_phase4_dev2.py "$@"
