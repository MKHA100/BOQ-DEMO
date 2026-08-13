#!/usr/bin/env bash
set -euo pipefail

cd backend
export PYTHONPATH=.
python -m app.jobs.worker
