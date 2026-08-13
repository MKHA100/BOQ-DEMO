#!/bin/sh
set -eu

: "${PORT:=8000}"
exec uvicorn demo_backend.main:app --host 0.0.0.0 --port "$PORT"
