# Production Runbook

## Local development

Backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Worker in a second terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.jobs.worker
```

Frontend in a third terminal:

```powershell
cd frontend
npm config set registry https://registry.npmjs.org/
npm install
npm run dev
```

## Production checks

```powershell
cd backend
python -m compileall -q app
pytest -q
python -m app.jobs.worker --once

cd ..\frontend
npm run typecheck
npm run lint
npm run build
```

## Health endpoints

- `/health` — process health.
- `/health/ready` — database readiness and current pending/running/failed job counts.

Run the FastAPI application, at least one Python worker, and the Next.js application as separate services. Increase worker count by workload only after validating database and storage limits. Do not run multiple workers against local SQLite for production use.
