#!/usr/bin/env bash
set -euo pipefail

cd backend
export PYTHONPATH=.
pytest
