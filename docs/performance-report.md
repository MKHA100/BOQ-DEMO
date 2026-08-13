# Performance Report

## Local API benchmark

Environment: local SQLite, FastAPI TestClient, warmed application, one project and one floor.

| Endpoint | Samples | Median | P95 | Maximum | Median SQL statements |
|---|---:|---:|---:|---:|---:|
| Workflow summary | 20 | 7.08 ms | 8.76 ms | 8.98 ms | 27 |
| Element property update | 10 | 18.84 ms | 20.43 ms | 20.92 ms | 32 |

The API now returns `X-Process-Time-Ms`, `X-DB-Query-Count`, `X-Request-ID`, and `Server-Timing` headers for measurement and tracing.

## Speed safeguards

- Upload returns after durable storage and job creation.
- Page opening does not start vision, geometry, or extraction work.
- Background work is deduplicated by task, scope, entity, and input versions.
- Scale and geometry jobs are floor-scoped.
- Read models refresh from canonical data and do not rerun upstream processing.
- High-resolution drawings are selected-floor only.
- Export artifacts are cached by BOQ/template/version/format/floor mode.

## Query observations

The workflow summary is fast locally but uses 27 SQL statements because it assembles version, floor, document, and status summaries from normalized tables. This remains a future optimization target for production-scale projects through a prepared project-summary read model.
