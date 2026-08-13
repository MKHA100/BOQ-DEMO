# Database Model and Migration

## Migration

`backend/app/database/migrations.py` applies ordered, idempotent migrations, including:

```text
20260713_001_workflow_foundation
20260718_017_floor_precision_editor
20260719_018_floor_room_interpretation
```

The migration is portable across the project's SQLite and PostgreSQL adapters. Applied versions are stored in `schema_migrations`. Application initialization executes the retained platform schema, then ordered migrations, then platform seed data.

No destructive database operation is performed by this migration.

## Retained platform tables

Authentication and platform tables remain unchanged, including:

- `users`, `auth_sessions`
- `organizations`, `organization_memberships`
- `subscription_plans`, `subscriptions`, `billing_history`
- `user_invitations`, `user_profiles`
- `account_settings`, `organization_settings`
- `usage_counters`, `audit_logs`, `notifications`
- `password_reset_tokens`, `payment_webhook_events`
- `projects`

## Added workflow tables

| Table | Purpose | Scope/version |
|---|---|---|
| `project_versions` | Project-wide version counters | project |
| `floors` | Ordered building floors | project |
| `floor_versions` | Floor-specific dependency versions | project + floor |
| `documents` | Immutable source/supporting file records | project + document version |
| `document_pages` | Page manifest and preview references | project + document |
| `floor_crops` | Original-page crop coordinates | project + floor + crop version |
| `schedule_files` | Schedule source and extracted record | project, optional floor, schedule version |
| `specification_files` | Specification source and extracted record | project, optional floor, specification version |
| `calibrations` | Two-point floor calibration | project + floor + scale version |
| `elements` | Canonical doors/windows/other elements | project + floor + element version |
| `element_properties` | Prioritized typed element values and suggestions | project + floor + element version |
| `element_relations` | Opening/wall and other entity relationships | project + floor |
| `walls` | Canonical wall geometry and quantities | project + floor + wall version |
| `rooms` | Canonical room geometry and quantities | project + floor + room version |
| `room_geometry_revisions` | Reversible room-boundary edit history | room + revision |
| `room_cutouts` | Columns, shafts, and other quantity deductions | room |
| `room_precision_runs` | Versioned local precision results | crop + wall + scale version |
| `room_interpretation_runs` | Cached floor-level LLM requests and validated responses | crop + wall + scale + prompt + model |
| `room_interpretation_results` | Validated semantic evidence matched to saved rooms | interpretation run + room/suggestion |
| `review_issues` | Conflicts and validation findings | project, optional floor, review version |
| `quantity_snapshots` | Versioned derived quantities | project, optional floor |
| `boqs` | Saved BOQ aggregate | project + BOQ version |
| `boq_rows` | Entity-linked BOQ rows | project, optional floor, BOQ version |
| `job_runs` | Durable background job execution | project, optional floor, input versions |
| `outbox_events` | Transactional dependency/change events | project, optional floor |

## Index strategy

Indexes cover the expected hot queries:

- Project and floor scope.
- Entity type and workflow status.
- Current version and stale status.
- Active job claim and retry ordering.
- Lease expiry recovery.
- Review and BOQ entity lookup.
- Outbox publish ordering.
- Document hash and page lookup.

## Compatibility

- SQLite remains the official local mode.
- PostgreSQL remains the production mode.
- All workflow SQL uses the project's `?` placeholder abstraction and portable text/JSON serialization.
- Existing initialized databases may contain older unused tables; the active runtime reads and writes only `job_runs` for workflow jobs.
