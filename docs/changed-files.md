# Changed Files — Background Floor Room Analysis

Compared with the supplied `auto-boq(2).zip` source:

- Added: 15 source/test files.
- Modified: 45 source, configuration, test, and documentation files.
- Removed: 0.
- Generated environments, caches, build output, and runtime data are not part of the deliverable archive.

## Added

### Floor interpretation and quantity safety

- `backend/app/floors/llm_room_prompt.py`
- `backend/app/floors/llm_room_schema.py`
- `backend/app/floors/llm_room_context_service.py`
- `backend/app/floors/llm_room_cache.py`
- `backend/app/floors/room_area_resolver.py`
- `backend/app/floors/room_result_validator.py`

### Regression tests

- `backend/app/tests/test_floor_llm_prompt.py`
- `backend/app/tests/test_floor_llm_schema.py`
- `backend/app/tests/test_floor_llm_context.py`
- `backend/app/tests/test_floor_llm_cache.py`
- `backend/app/tests/test_floor_llm_result_validation.py`
- `backend/app/tests/test_floor_llm_dimension_matching.py`
- `backend/app/tests/test_floor_llm_fast_background_flow.py`
- `backend/app/tests/test_floor_llm_failure_fallback.py`
- `backend/app/tests/test_floor_llm_review_boq.py`

## Modified areas

- Configuration: `.env.example`, `backend/.env.example`, and `backend/app/core/config.py`.
- Persistence: `backend/app/database/migrations.py` and `backend/app/floors/precision_schema.py`.
- Room pipeline: floor repository/service/routes/schemas, segmentation, labels, semantics, dimensions, vector filtering, free space, precision, and floor jobs.
- Orchestration: job priorities, lane execution, worker startup, workflow task registration/dependencies/status.
- Walls: geometry context and opening/room-facing relations.
- Review and BOQ: provisional-room filtering, interpretation warnings, boundary provenance, and separated external quantities.
- Frontend: saved Floors state/API/types, room analysis actions/statuses, inspector/list geometry state, retained query caching, and Floor Plans polling behavior.
- Documentation: database model, environment variables, worker topology, and final verification.

Protected model-review, BOQ exporter/template, storage, authentication, dashboard, and platform files remain unchanged.
