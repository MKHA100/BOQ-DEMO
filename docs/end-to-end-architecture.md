# End-to-End Architecture Review

## Workflow

Upload PDF → Floor Plans → Schedules & Specifications → Scale → Model Review → Walls → Floors → Review → BOQ

The workflow uses one canonical project/floor domain. Pages do not keep independent copies of doors, windows, walls, rooms, relationships, quantities, or BOQ rows.

## Durable write contract

1. Authenticate the user and verify project ownership.
2. Save the canonical record in a database transaction.
3. Increment the relevant floor or project version.
4. Mark only dependent records stale.
5. create deterministic background jobs with the current input versions.
6. Return the saved result immediately.
7. Workers check current versions, save partial results, and publish only durable outputs.

## Dependency scenarios verified

- Door dimension → assigned wall opening relation → wall deduction/net area → Review → BOQ.
- Wall centerline/classification → touching rooms only → Review → BOQ.
- Room geometry/finish → room area and floor summary → Review → BOQ.
- Scale for one floor → measurement, walls, rooms, Review, and BOQ for that floor; detections remain unchanged.

## Worker reliability

- Deterministic keys prevent equivalent jobs for the same input versions.
- Floor-scoped task types require `floor_id`.
- Jobs are atomic and idempotent at the saved-record boundary.
- Leases, continuous heartbeats, retry limits, expired-lease recovery, and partial results are supported.
- Workers skip superseded heavy floor jobs but read-model jobs always refresh from the latest committed state.
- One floor or task failure does not block unrelated work.

## UI data flow

- TanStack Query owns saved server data.
- Small mutations update the selected entity optimistically and invalidate only dependent keys.
- Zustand retains temporary drawing state such as selected floor, zoom, pan, scroll, and unsaved points.
- Workflow pages own one consistent floor selector; the shared wrapper no longer renders a duplicate selector.
- Full-resolution drawings load only for the selected floor.
- Polling is active only while matching jobs are pending or running.
