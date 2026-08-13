# Reusable Reference Inventory

The supplied Construction Plan Extractor archive remains the reference for selected implementation ideas. The files below are not active in the new workflow foundation.

| Original path | Capability | Coupling | Reuse potential | Dependencies and risk | Recommended future extraction |
|---|---|---|---|---|---|
| `backend/app/pdf_processing/pdf_metadata_reader.py` | Reads PDF page metadata | Moderate | High | Assumes former schemas and PDF library behavior | Extract a pure metadata adapter returning `DocumentPage` inputs |
| `backend/app/pdf_processing/pdf_renderer.py` | Renders PDF pages to images | Moderate | High | Former storage paths, status fields, and render options | Wrap behind a new render processor and object-key contract |
| `backend/app/pdf_processing/pdf_page_service.py` | Coordinates page records and render assets | Tight | Medium | Coupled to former project repositories and route flow | Reuse algorithms only; write new `document_pages` repository integration |
| `backend/app/storage/storage_service.py` | Local/R2 storage abstraction | Low | High | Path conventions may differ | Keep the current retained storage service and port only missing capabilities |
| `backend/app/jobs/job_repository.py` | Database job claiming/status | Moderate | Medium | Former job schema and processor names | Compare retry/locking edge cases against the new `job_runs` repository |
| `backend/app/jobs/worker.py` | Python worker loop | Moderate | Medium | Former task registrations are tightly coupled | Port only proven shutdown/heartbeat patterns when required |
| `backend/app/scale/scale_service.py` | Scale calculations | Moderate | High | Former crop and measurement records | Extract pure point-distance/unit conversion functions and test independently |
| `backend/app/wall_takeoff/` | Wall centerline, area, opening logic | Tight | High | Depends on former element/wall models and NRM services | Isolate geometry and quantity functions; adapt to canonical `Wall`/`ElementRelation` records |
| `backend/app/floor_takeoff/` | Room polygons and floor areas | Tight | High | Depends on former wall outputs, Shapely, and workflow state | Extract deterministic geometry functions; keep LLM out of area calculation |
| `backend/app/boq/` | BOQ grouping, descriptions, templates, exports | Tight | High | Broad former service/repository graph | Reintroduce template and formatting modules after `BOQRow` derivation is stable |
| `frontend/shared/hooks/useJobPolling.ts` | Polls active jobs | Moderate | Medium | Former endpoint/status contract | Compare stop conditions with the new TanStack Query active-only polling hook |
| `frontend/shared/hooks/useProjectStatus.ts` | Project status cache | Tight | Low | Former project-wide processing model | Do not restore project-wide polling; retain only useful cache behavior |
| `frontend/features/view-mapping/` | Canvas mapping interactions | Tight | Medium | Former page state and domain types | Extract generic zoom/pan/selection components only after page specifications are final |
| `frontend/features/boq/` | BOQ table and template UI patterns | Tight | Medium | Former BOQ APIs and data shape | Reuse visual interaction ideas, not persisted state or API contracts |

## Reuse rules

- Reuse pure calculations before orchestration code.
- Adapt to the new canonical IDs, project/floor scope, and version inputs.
- Add idempotency and confirmed-value tests before activating a processor.
- Do not import an old page, route, repository, or worker registration directly.
- Keep PDF rendering, geometry, AI extraction, and BOQ generation behind explicit task processors.
