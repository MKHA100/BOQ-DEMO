# API Contract Summary

All workflow routes require an authenticated user and verify project ownership before reading or mutating data.

Base path:

```text
/api/v1/projects/{project_id}/workflow
```

## Summary and floors

| Method | Route | Purpose |
|---|---|---|
| GET | `/summary` | Small project/floor/version/step/job summary |
| GET | `/floors` | List project floors |
| POST | `/floors` | Create the next or requested floor |

Floor names are generated consistently from `level_index` when no name is supplied: Ground Floor, First Floor, Second Floor, and subsequent numbered floors.

## Documents and source files

| Method | Route | Purpose |
|---|---|---|
| GET | `/documents` | List saved project documents |
| POST | `/documents` | Store PDF/image metadata and enqueue ingest/render jobs |
| POST | `/floor-crops` | Save original-page crop coordinates for one floor |
| POST | `/schedule-files` | Register a schedule source and enqueue extraction |
| POST | `/specification-files` | Register a specification source and enqueue extraction |

Uploads validate type and configured size, calculate SHA-256, use deterministic storage paths, and reuse an existing project document when the same content hash is already saved.

## Elements, walls, calibration, and rooms

| Method | Route | Purpose |
|---|---|---|
| POST | `/elements` | Create a canonical floor element |
| PATCH | `/elements/{element_id}/properties/{property_name}` | Update one prioritized element property |
| POST | `/element-relations` | Connect an element to a wall or another target |
| POST | `/walls` | Create a canonical wall |
| PUT | `/floors/{floor_id}/calibration` | Save confirmed two-point calibration |
| POST | `/rooms` | Create a canonical room |
| PATCH | `/rooms/{room_id}/geometry` | Update one room polygon |

Mutation responses include:

- Updated canonical record.
- Whether an incoming value was protected as a suggestion.
- Whether the canonical value changed.
- Current relevant versions.
- Public job summaries for only the dependent work.

## Saved read models

Large floor-scoped collections are paginated with `limit` and `offset` so later pages can virtualize rows without loading the full project.

| Method | Route | Purpose |
|---|---|---|
| GET | `/documents/{document_id}/pages` | Read saved page manifest records |
| GET | `/floors/{floor_id}/crop` | Read the current saved floor crop |
| GET | `/floors/{floor_id}/calibration` | Read the latest floor calibration |
| GET | `/schedule-files` | Read project or floor schedule sources |
| GET | `/specification-files` | Read project or floor specification sources |
| GET | `/floors/{floor_id}/elements` | Read canonical elements with prioritized properties |
| GET | `/floors/{floor_id}/walls` | Read canonical walls |
| GET | `/floors/{floor_id}/rooms` | Read canonical rooms |
| GET | `/review-issues` | Read project or floor review issues |
| GET | `/quantities` | Read versioned quantity snapshots |
| GET | `/boq` | Read the latest saved BOQ and paginated rows |

## Job status

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/v1/projects/{project_id}/jobs` | List project/floor jobs; supports `active_only` |
| GET | `/api/v1/jobs/{job_id}` | Read one job after ownership verification |

Normal UI responses expose professional task labels and status, not worker IDs, leases, raw payload internals, or stack traces.
