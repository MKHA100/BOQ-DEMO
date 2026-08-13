# Inspection Summary

## Current application

The current AutoBOQ project is a two-service application:

- `frontend/`: Next.js 14 App Router application with React, TypeScript, Tailwind CSS, authentication guards, dashboard, project library, organization/admin pages, project workspace routes, and a shared API client.
- `backend/`: FastAPI application with authentication, project ownership, organization/platform services, SQLite/PostgreSQL database adapters, local/R2 storage, and a database-backed Python worker.

The existing dashboard, authentication, project creation, project library, organization features, global layout, navigation, database connection, storage connection, and platform APIs remain in their established modules.

## Existing foundation before this task

The project already provided:

- User sessions and project ownership checks.
- Platform and organization records.
- Project CRUD endpoints.
- Local SQLite and production PostgreSQL connection handling.
- Local filesystem and Cloudflare R2-compatible storage adapters.
- A generic FastAPI router and API client.
- A small Python worker registry.
- Dashboard, project library, project creation, and a project overview page.
- A minimal global PDF Generation entry.

It did not yet contain a connected multi-floor workflow domain, per-layer versions, dependency-scoped invalidation, canonical element/wall/room/BOQ records, deterministic job runs, durable outbox events, server-data caching, or project-scoped workflow routes.

## Reference inspection

The supplied Construction Plan Extractor reference was inspected for reusable implementation patterns. Relevant areas include PDF metadata/rendering, storage, Python job handling, status polling, scale calibration, wall takeoff, floor geometry, review summaries, and BOQ services. These implementations remain reference material only; no former page workflow or tightly coupled processing service is activated in this foundation.

## Resulting shared foundation

The new foundation adds:

- A canonical relational workflow domain shared by every later page.
- Project and floor version boundaries.
- Central value-priority and confirmed-value protection rules.
- Targeted dependency planning for element, scale, wall, room, review, and BOQ updates.
- Deterministic, idempotent Python job records with retries, leases, heartbeats, and partial results.
- Durable outbox records written with canonical mutations.
- Authenticated project-scoped workflow APIs.
- Shared TanStack Query cache and optimistic mutation helpers.
- Persisted selected-floor and drawing-view state, with temporary canvas points kept local only.
- Common AutoBOQ workspace controls and professional statuses.
- Lightweight routes for all nine workflow steps without implementing page-specific processing interfaces.

## Intentional stopping point

The following are not implemented in this task:

- Full upload, crop, schedule, scale, model-review, wall, floor, review, or BOQ page interfaces.
- PDF page rendering processors.
- AI extraction or vision processors.
- Wall or room geometry processors.
- BOQ calculation, templates, or exports.
- A project event stream.

The domain, APIs, jobs, cache, state, and route shells are ready for those later features.
