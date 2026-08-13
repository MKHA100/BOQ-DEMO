#!/usr/bin/env bash
set -euo pipefail

cd backend
export PYTHONPATH=.
.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
