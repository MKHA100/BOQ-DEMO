from __future__ import annotations

FLOOR_ACCURACY_MIGRATION_VERSION = "20260716_016_floor_accuracy_and_zones"

ROOM_ACCURACY_COLUMNS: tuple[tuple[str, str], ...] = (
    ("space_kind", "TEXT NOT NULL DEFAULT 'internal'"),
    ("measurement_status", "TEXT NOT NULL DEFAULT 'missing_scale'"),
    ("measured_width_m", "REAL"),
    ("measured_length_m", "REAL"),
    ("printed_width_mm", "REAL"),
    ("printed_length_mm", "REAL"),
    ("dimension_difference_percent", "REAL"),
    ("include_in_boq", "INTEGER NOT NULL DEFAULT 1"),
    ("parent_room_id", "TEXT"),
    ("is_finish_zone", "INTEGER NOT NULL DEFAULT 0"),
    ("open_plan", "INTEGER NOT NULL DEFAULT 0"),
    ("label_candidates_json", "TEXT NOT NULL DEFAULT '[]'"),
)

FLOOR_ACCURACY_TABLES_SQL = r"""
CREATE TABLE IF NOT EXISTS floor_dimension_observations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  crop_version INTEGER NOT NULL,
  label_text TEXT NOT NULL,
  value_mm REAL NOT NULL,
  orientation TEXT,
  point_a_json TEXT NOT NULL DEFAULT '{}',
  point_b_json TEXT NOT NULL DEFAULT '{}',
  drawing_distance REAL,
  suggested_mm_per_pixel REAL,
  confidence REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'suggested',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(project_id, floor_id, crop_version, label_text, point_a_json, point_b_json),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_floor_dimension_observations_scope
  ON floor_dimension_observations(project_id, floor_id, crop_version, status, confidence);

CREATE TABLE IF NOT EXISTS floor_geometry_cache (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  crop_version INTEGER NOT NULL,
  wall_version INTEGER NOT NULL,
  scale_version INTEGER NOT NULL,
  cache_key TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(project_id, floor_id, cache_key),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_floor_geometry_cache_versions
  ON floor_geometry_cache(project_id, floor_id, crop_version, wall_version, scale_version);

CREATE INDEX IF NOT EXISTS idx_rooms_floor_measurement
  ON rooms(project_id, floor_id, is_finish_zone, parent_room_id, space_kind, measurement_status, include_in_boq);
"""
