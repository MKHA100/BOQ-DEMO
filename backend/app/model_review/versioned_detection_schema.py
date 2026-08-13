from __future__ import annotations

VERSIONED_DETECTION_MIGRATION_VERSION = "20260718_017_unified_versioned_floor_detection"

ELEMENT_DETECTION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("crop_id", "TEXT"),
    ("crop_version", "INTEGER"),
    ("detection_run_id", "TEXT"),
    ("generated_status", "TEXT NOT NULL DEFAULT 'current'"),
    ("detection_model_id", "TEXT"),
    ("detection_input_hash", "TEXT"),
    ("analysis_mode", "TEXT NOT NULL DEFAULT 'standard'"),
)

WALL_DETECTION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("source_crop_version", "INTEGER"),
    ("generated_status", "TEXT NOT NULL DEFAULT 'current'"),
)

ROOM_DETECTION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("source_crop_version", "INTEGER"),
    ("generated_status", "TEXT NOT NULL DEFAULT 'current'"),
)

VERSIONED_DETECTION_TABLES_SQL = r"""
CREATE TABLE IF NOT EXISTS floor_element_detection_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  crop_id TEXT NOT NULL,
  crop_version INTEGER NOT NULL,
  provider_name TEXT,
  model_id TEXT NOT NULL,
  input_hash TEXT NOT NULL,
  analysis_mode TEXT NOT NULL DEFAULT 'standard',
  raw_json TEXT NOT NULL DEFAULT '{}',
  prediction_count INTEGER NOT NULL DEFAULT 0,
  door_count INTEGER NOT NULL DEFAULT 0,
  window_count INTEGER NOT NULL DEFAULT 0,
  wall_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'processing',
  error_message TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(project_id, floor_id, crop_version, model_id, analysis_mode),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(crop_id) REFERENCES floor_crops(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_floor_element_runs_current
  ON floor_element_detection_runs(project_id, floor_id, crop_version, status, analysis_mode);
CREATE INDEX IF NOT EXISTS idx_elements_current_crop
  ON elements(project_id, floor_id, crop_version, generated_status, element_type, excluded, status);
CREATE INDEX IF NOT EXISTS idx_elements_detection_run
  ON elements(detection_run_id, generated_status);
CREATE INDEX IF NOT EXISTS idx_walls_current_crop
  ON walls(project_id, floor_id, source_crop_version, generated_status, status, is_stale);
CREATE INDEX IF NOT EXISTS idx_rooms_current_crop
  ON rooms(project_id, floor_id, source_crop_version, generated_status, status, is_stale);
"""
