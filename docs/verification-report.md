# Verification Report

Verification was run against the completed shared foundation on July 13, 2026.

## Backend

| Command/check | Result |
|---|---|
| `python -m compileall -q app` | Passed |
| `pytest -q` | Passed: 12 tests |
| Clean SQLite initialization | Passed |
| Migration version check | `20260713_001_workflow_foundation` applied |
| Clean schema table count | 38 application tables |
| Active job table | `job_runs` present; `background_jobs` absent |
| `python -m app.jobs.worker --once` | Passed with exit code 0 |
| Uvicorn startup | Passed |
| `GET /health` | HTTP 200, `{"status":"ok"}` |
| OpenAPI generation | Passed: 49 paths |
| Local project creation | Passed |
| Ground Floor creation | Passed |
| Canonical element creation | Passed |
| Floor-scoped element read | Passed; total 1 |

Targeted backend tests cover:

- Project and floor version increments.
- Deterministic job deduplication by input versions.
- Protection of user-confirmed values.
- Conflicting suggestion creation as a review issue.
- Floor isolation.
- Element-to-wall dependency refresh.
- Room-to-review/BOQ dependency refresh.
- Saved read-model floor isolation.
- Project ownership.
- Canonical schema creation.
- Worker registry behavior.

## Frontend

| Command/check | Result |
|---|---|
| `npm install --no-audit --no-fund` | Passed |
| `npm run typecheck` | Passed |
| `npm run lint` | Passed with no warnings or errors |
| `npm run build` | Passed |
| Next.js app manifest | 35 routes |
| `npm run start -- -p 3012` | Passed; ready in approximately 1.1 seconds |
| `GET /login` | HTTP 200 |
| `GET /workspace/{projectId}/upload` | HTTP 200 |

The production build compiled all workflow routes:

- Upload PDF
- Floor Plans
- Schedules & Specifications
- Scale
- Model Review
- Walls
- Floors
- Review
- BOQ

## Known warnings

`npm install` reports deprecation warnings from transitive packages used by the current Next.js/ESLint toolchain. These warnings do not cause typecheck, lint, or build failures. No dependency was force-upgraded because this task does not change the accepted framework version.

## Not tested

- Live PostgreSQL/Neon connectivity.
- Live Cloudflare R2 connectivity.
- Production billing provider/webhook behavior.
- Full browser-driven production authentication.
- Heavy PDF rendering, AI extraction, vision, geometry, BOQ, and export processors, because they are intentionally outside this foundation task.
- Project event streaming, because the current foundation uses active-job polling and prepares durable outbox records for a later stream/relay implementation.
