# Environment Variables

No secret values are included here.

## Core

- `APP_MODE`: `local` or `production`.
- `ENVIRONMENT`: `development`, `test`, or `production`.
- `DEBUG`
- `CORS_ORIGINS`
- `AUTH_REQUIRED`
- `ALLOW_LOCAL_AUTH_BYPASS`
- `SUPER_ADMIN_EMAIL`
- `SUPER_ADMIN_PASSWORD`
- `SUPER_ADMIN_NAME`
- `SYNC_SUPER_ADMIN_ON_STARTUP`

## Database and storage

- `LOCAL_DATABASE_PATH`
- `LOCAL_STORAGE_ROOT`
- `DATABASE_URL`
- `DIRECT_DATABASE_URL`
- `STORAGE_BACKEND`
- `R2_ENDPOINT_URL`
- `R2_BUCKET_NAME`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_PUBLIC_BASE_URL`
- `R2_PRESIGNED_URL_TTL_SECONDS`

## Upload, PDF, and workers

- `MAX_UPLOAD_MB`
- `PDF_THUMBNAIL_WIDTH`
- `PDF_PREVIEW_WIDTH`
- `WORKER_MAX_ATTEMPTS`
- `WORKER_POLL_INTERVAL_SECONDS`
- `WORKER_LEASE_SECONDS`

## Optional extraction and detection

- `OPENAI_API_KEY`
- `OPENAI_EXTRACTION_MODEL`
- `OPENAI_EXTRACTION_TIMEOUT_SECONDS`
- `OPENAI_EXTRACTION_MAX_PAGES`
- `ROBOFLOW_API_KEY`
- `ROBOFLOW_MODEL_ID`
- `ROBOFLOW_API_BASE_URL`
- `ROBOFLOW_TIMEOUT_SECONDS`
- `ROBOFLOW_FLOOR_ENABLED`: enables optional room-segmentation verification.
- `ROBOFLOW_FLOOR_MODEL_ID`: defaults to `room-segmentation-o7iga/4`.
- `ROBOFLOW_FLOOR_CONFIDENCE`: minimum accepted room prediction confidence.
- `ROBOFLOW_FLOOR_TIMEOUT_SECONDS`

## Background room analysis

- `MODEL_DETECTION_MAX_CONCURRENCY`: parallel room and floor-element detection workers; defaults to `2`.
- `ROOM_RESULTS_PUBLISH_EARLY`: publishes saved model rooms before interpretation/precision; defaults to `true`.
- `ROOM_FAST_PASS_ENABLED`: enables provisional model-room publication; defaults to `true`.
- `ROOM_PRECISION_PASS_ENABLED`: enables local wall/dimension precision correction; defaults to `true`.
- `ROOM_PRECISION_MAX_CONCURRENCY`: precision lane concurrency; defaults to `1`.
- `ROOM_LLM_ENABLED`
- `ROOM_LLM_BACKGROUND_ENABLED`
- `ROOM_LLM_ONLY_WHEN_AMBIGUOUS`
- `ROOM_LLM_MODEL`: defaults to `gpt-5.5`.
- `ROOM_LLM_TIMEOUT_SECONDS`: defaults to `60`.
- `ROOM_LLM_MAX_FLOOR_CALLS`: defaults to one normal floor request.
- `ROOM_LLM_MAX_ROOM_CROPS`: upper bound reserved for ambiguous-room crops; defaults to `4`.
- `ROOM_LLM_CONFIDENCE_THRESHOLD`: below this value, interpretation is marked for review.

## Frontend

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_MAX_UPLOAD_MB`

# Unified multi-class floor detection
MODEL_DETECTION_MAX_CONCURRENCY=2
ROBOFLOW_DOOR_CONFIDENCE=0.35
ROBOFLOW_WINDOW_CONFIDENCE=0.35
ROBOFLOW_WALL_CONFIDENCE=0.30
ROBOFLOW_DEEP_ANALYSIS_ENABLED=true
ROBOFLOW_DEEP_ANALYSIS_TILE_OVERLAP=0.15
