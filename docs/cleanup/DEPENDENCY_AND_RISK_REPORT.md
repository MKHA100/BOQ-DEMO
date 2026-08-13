# Dependency and Risk Report

## Shared dependencies resolved

- **Projects:** the original `ProjectService` performed PDF validation, metadata reading, storage writes, synchronous page rendering, and wall-type job queuing. It was rewritten as neutral project CRUD.
- **Database:** the original central schema mixed platform tables with all PDF/takeoff/BOQ tables. The clean schema retains only platform, project, and generic job tables. It creates a new database and does not destructively migrate the original database.
- **Navigation/dashboard:** old BOQ, template-package, saved-export, and workspace-step links were removed. The existing shell and styling remain.
- **Workers:** every old processor registration was removed. The retained worker is an empty registry that can accept future explicitly registered processors.
- **Storage:** local/R2 adapters remain; old rendered-page, crop, model-output, supporting-document, and export directories were replaced by generic `files`, `metadata`, and `temporary` directories.
- **Environment:** AI/CV/PDF/export provider variables are no longer active or required. Database, storage, auth, CORS, and generic worker settings remain.

## Database impact

Retained tables: users, auth sessions, subscription plans, organizations, organization memberships, subscriptions, billing history, invitations, profiles, account/organization settings, usage counters, audit logs, notifications, password-reset tokens, payment webhook events, projects, and background jobs.

Removed tables are listed exactly in `CHANGED_FILES_REPORT.md`. The project table is intentionally simplified; old PDF file/page/render columns are not part of the clean schema. Existing old databases are not automatically altered. Use a new database for this separate project.

## Main risks

1. **Existing-data compatibility — high:** old project records contain PDF-specific columns and related rows. The clean app is designed for a fresh database, not an in-place destructive migration.
2. **Authorization — medium:** local auth bypass remains available for development; production must set `AUTH_REQUIRED=true`, disable local bypass, and use a strong admin password.
3. **PostgreSQL concurrency — medium:** the generic job repository is retained, but new processor concurrency must be tested before production.
4. **Future PDF reuse — medium:** copying old orchestration services wholesale would recreate old schema and side effects. Reuse should occur only through small extracted adapters.
5. **Storage lifecycle — medium:** temporary and future generated files need a retention policy when the replacement workflow is defined.

## Confirmed clean-shell behavior

The PDF Generation component is server-rendered, has no client effect, imports no API service, and contains only the global authenticated platform shell plus an empty workspace section. No PDF-specific backend route exists in OpenAPI.
