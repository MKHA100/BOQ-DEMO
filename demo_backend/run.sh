#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
exec backend/.venv/bin/python -m uvicorn demo_backend.main:app --reload --host 0.0.0.0 --port 8000
