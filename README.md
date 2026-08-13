# AutoBOQ

AutoBOQ is a Next.js and FastAPI application foundation for connected construction drawing review, quantity takeoff, and BOQ workflows.

## Workflow

```text
Upload PDF
→ Floor Plans
→ Schedules & Specifications
→ Scale
→ Model Review
→ Walls
→ Floors
→ Review
→ BOQ
```

This repository currently contains the shared application and workflow foundation. It includes the versioned domain model, project- and floor-scoped APIs, deterministic Python job orchestration, durable dependency events, shared frontend cache/state, common workspace controls, and lightweight route shells. Page-specific drawing, extraction, geometry, BOQ, and export implementations are intentionally deferred to later feature work.

## Technology

- Frontend: Next.js 14, React 18, TypeScript, TanStack Query, Zustand, Tailwind CSS
- Backend: FastAPI, Python, Pydantic
- Database: SQLite for local development and PostgreSQL for production
- Storage: local object storage for development and Cloudflare R2-compatible storage for production
- Background work: database-backed Python workers with deterministic job keys, leases, retries, heartbeats, and partial results

## Local setup

### Backend

```powershell
cd backend
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Worker

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.jobs.worker
```

### Frontend

```powershell
cd frontend
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`.

## Verification

```powershell
cd backend
python -m compileall app
pytest
python -m app.jobs.worker --once

cd ..\frontend
npm run typecheck
npm run lint
npm run build
```

Detailed architecture and contracts are available in `docs/`.
