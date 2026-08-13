# Shared Architecture

## Single source of truth

Every workflow page reads and writes the same canonical backend records. Pages do not own private persisted copies of doors, windows, walls, rooms, review items, quantities, or BOQ rows.

Canonical records:

```text
Project
Document → DocumentPage
Floor → FloorCrop → Calibration
ScheduleFile / SpecificationFile
Element → ElementProperty → ElementRelation
Wall
Room
ReviewIssue
QuantitySnapshot
BOQ → BOQRow
JobRun
OutboxEvent
```

The frontend server-data cache is only a synchronized view of these records. Zustand stores only selected floor, filters, zoom, pan, scroll position, and temporary canvas points.

## Version boundaries

Project versions:

- `document_version`
- `schedule_version`
- `specification_version`
- `review_version`
- `boq_version`

Floor versions:

- `crop_version`
- `schedule_version`
- `scale_version`
- `element_version`
- `wall_version`
- `room_version`
- `review_version`
- `boq_version`

Jobs receive only the relevant version set. Their deterministic key combines project, optional floor, task, optional entity, and normalized input versions.

## Write contract

A dependent edit follows this order:

1. Verify authenticated project ownership.
2. Begin one database transaction.
3. Read and validate the canonical record and floor scope.
4. Apply value-priority and confirmed-value protection rules.
5. Save the canonical record.
6. Increment the relevant version boundary.
7. Mark only dependent records stale.
8. Insert a durable outbox event.
9. Commit.
10. Enqueue only the dependency-scoped jobs for the committed versions.
11. Return the updated record, versions, and public job statuses.

## Value priority

All property writes use this priority:

```text
user_confirmed
schedule
specification
drawing_note
model or calculated
default
```

A lower-priority value cannot replace a user-confirmed value. The new value is stored as a suggestion and a `Needs Review` issue is created.

## Backend boundaries

- `app/workflow/routes.py`: authenticated HTTP contract.
- `app/workflow/schemas.py`: request and response types.
- `app/workflow/service.py`: transaction and dependency orchestration.
- `app/workflow/repo.py`: canonical SQL persistence.
- `app/workflow/dependencies.py`: targeted invalidation/job plan.
- `app/workflow/files.py`: document and supporting-file registration.
- `app/workflow/jobs.py`: job task registry.
- `app/jobs/*`: generic durable job runtime.
- `app/database/migrations.py`: ordered schema changes.

## Frontend boundaries

- `features/workflow/api.ts` and `readApi.ts`: shared mutation and paginated read calls.
- `features/workflow/queryKeys.ts`: stable cache scopes.
- `features/workflow/hooks/`: summary/detail queries and optimistic floor, element, calibration, and room mutations.
- `features/workflow/state/drawingStore.ts`: small drawing interaction state.
- `features/workflow/components/`: common workflow controls and route shell.
- `features/<step>/components/`: lightweight feature entry components.
- `app/workspace/[projectId]/<step>/`: project-scoped routes.

## Performance rules

- Saved summary data is shown from the client cache immediately when available.
- Summary polling runs only while a real active job exists and stops after completion or failure.
- Small edits patch only the affected cache record and invalidate only relevant summary scopes.
- The next workflow route is prefetched from the current route.
- Selected floor and drawing view are preserved by project/scope.
- Large drawing assets are not part of the shared summary and will be loaded only for the selected floor by later page implementations.
- Route-level loading keeps the application shell visible and does not block the full page.
