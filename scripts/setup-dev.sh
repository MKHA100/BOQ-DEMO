#!/usr/bin/env bash
set -euo pipefail

python -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
cd frontend
npm install
