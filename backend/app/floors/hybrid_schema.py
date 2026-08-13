from __future__ import annotations

HYBRID_FLOOR_MIGRATION_VERSION = "20260716_015_hybrid_floor_rooms"

ROOM_COLUMNS: tuple[tuple[str, str], ...] = (
    ("detection_source", "TEXT NOT NULL DEFAULT 'wall_geometry'"),
    ("confidence", "REAL"),
    ("model_verified", "INTEGER NOT NULL DEFAULT 0"),
    ("comparison_status", "TEXT NOT NULL DEFAULT 'not_compared'"),
    ("excluded", "INTEGER NOT NULL DEFAULT 0"),
    ("exclusion_reason", "TEXT"),
    ("label_confidence", "REAL"),
    ("geometry_hash", "TEXT"),
)

ROOM_SUGGESTION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("class_name", "TEXT"),
    ("class_source", "TEXT"),
)

HYBRID_FLOOR_TABLES_SQL = r"""
CREATE TABLE IF NOT EXISTS room_segmentation_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  crop_id TEXT NOT NULL,
  crop_version INTEGER NOT NULL,
  model_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'processing',
  raw_response_json TEXT NOT NULL DEFAULT '{}',
  prediction_count INTEGER NOT NULL DEFAULT 0,
  image_width REAL,
  image_height REAL,
  error_message TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(project_id, floor_id, crop_version, model_id),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(crop_id) REFERENCES floor_crops(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_room_segmentation_scope
  ON room_segmentation_runs(project_id, floor_id, crop_version, model_id, status);

CREATE TABLE IF NOT EXISTS room_suggestions (
  id TEXT PRIMARY KEY,
  segmentation_run_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  polygon_json TEXT NOT NULL DEFAULT '{}',
  bounding_box_json TEXT NOT NULL DEFAULT '{}',
  confidence REAL,
  class_name TEXT,
  class_source TEXT,
  status TEXT NOT NULL DEFAULT 'new',
  matched_room_id TEXT,
  comparison_score REAL,
  geometry_hash TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(segmentation_run_id) REFERENCES room_segmentation_runs(id) ON DELETE CASCADE,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(matched_room_id) REFERENCES rooms(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_room_suggestions_scope
  ON room_suggestions(project_id, floor_id, status, confidence, comparison_score);
CREATE INDEX IF NOT EXISTS idx_room_suggestions_run
  ON room_suggestions(segmentation_run_id, status);

CREATE TABLE IF NOT EXISTS room_opening_relations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  room_id TEXT NOT NULL,
  element_id TEXT NOT NULL,
  relation_type TEXT NOT NULL DEFAULT 'virtual_closure',
  relation_version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(room_id, element_id, relation_type),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE,
  FOREIGN KEY(element_id) REFERENCES elements(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_room_opening_scope
  ON room_opening_relations(project_id, floor_id, element_id, room_id);

CREATE INDEX IF NOT EXISTS idx_rooms_hybrid_scope
  ON rooms(project_id, floor_id, excluded, comparison_status, detection_source, status);
"""
