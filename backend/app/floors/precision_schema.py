from __future__ import annotations

FLOOR_PRECISION_MIGRATION_VERSION = "20260718_017_floor_precision_editor"
FLOOR_INTERPRETATION_MIGRATION_VERSION = "20260719_018_floor_room_interpretation"

ROOM_PRECISION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("raw_geometry_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("regularized_geometry_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("confirmed_geometry_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("shape_type", "TEXT NOT NULL DEFAULT 'irregular'"),
    ("boundary_source", "TEXT NOT NULL DEFAULT 'unknown'"),
    ("precision_status", "TEXT NOT NULL DEFAULT 'pending'"),
    ("user_edited", "INTEGER NOT NULL DEFAULT 0"),
    ("geometry_version", "INTEGER NOT NULL DEFAULT 1"),
    ("edit_revision", "INTEGER NOT NULL DEFAULT 0"),
    ("validation_details_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("precision_updated_at", "TEXT"),
)

ROOM_INTERPRETATION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("wall_corrected_geometry_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("interpretation_status", "TEXT NOT NULL DEFAULT 'not_started'"),
    ("interpretation_warnings_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("interpretation_run_id", "TEXT"),
    ("dimension_status", "TEXT NOT NULL DEFAULT 'unknown'"),
    ("dimension_source", "TEXT NOT NULL DEFAULT 'unknown'"),
)

FLOOR_PRECISION_TABLES_SQL = r"""
CREATE TABLE IF NOT EXISTS room_geometry_revisions (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  room_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  action TEXT NOT NULL,
  geometry_json TEXT NOT NULL DEFAULT '{}',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(room_id, revision),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_room_geometry_revisions_scope
  ON room_geometry_revisions(project_id, floor_id, room_id, revision DESC);

CREATE TABLE IF NOT EXISTS room_cutouts (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  room_id TEXT NOT NULL,
  name TEXT,
  geometry_json TEXT NOT NULL DEFAULT '{}',
  area_m2 REAL,
  created_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_room_cutouts_scope
  ON room_cutouts(project_id, floor_id, room_id);

CREATE TABLE IF NOT EXISTS room_precision_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  crop_version INTEGER NOT NULL,
  wall_version INTEGER NOT NULL,
  scale_version INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'processing',
  room_count INTEGER NOT NULL DEFAULT 0,
  changed_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  UNIQUE(project_id, floor_id, crop_version, wall_version, scale_version),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_room_precision_runs_scope
  ON room_precision_runs(project_id, floor_id, crop_version, wall_version, scale_version, status);

CREATE INDEX IF NOT EXISTS idx_rooms_precision_scope
  ON rooms(project_id, floor_id, precision_status, shape_type, user_edited, geometry_version);
"""

FLOOR_INTERPRETATION_TABLES_SQL = r"""
CREATE TABLE IF NOT EXISTS room_interpretation_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  crop_version INTEGER NOT NULL,
  wall_version INTEGER NOT NULL,
  scale_version INTEGER NOT NULL,
  prompt_version TEXT NOT NULL,
  model TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'processing',
  input_hash TEXT NOT NULL,
  raw_response_json TEXT NOT NULL DEFAULT '{}',
  validated_response_json TEXT NOT NULL DEFAULT '{}',
  error_message TEXT,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT,
  UNIQUE(project_id, floor_id, crop_version, wall_version, scale_version, prompt_version, model),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_room_interpretation_runs_scope
  ON room_interpretation_runs(project_id, floor_id, crop_version, wall_version, scale_version, status);
CREATE INDEX IF NOT EXISTS idx_room_interpretation_runs_input
  ON room_interpretation_runs(project_id, floor_id, input_hash, prompt_version, model, status);

CREATE TABLE IF NOT EXISTS room_interpretation_results (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  room_id TEXT,
  suggestion_id TEXT,
  status TEXT NOT NULL DEFAULT 'validated',
  result_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(run_id, suggestion_id),
  FOREIGN KEY(run_id) REFERENCES room_interpretation_runs(id) ON DELETE CASCADE,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE SET NULL,
  FOREIGN KEY(suggestion_id) REFERENCES room_suggestions(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_room_interpretation_results_scope
  ON room_interpretation_results(project_id, floor_id, room_id, status);

CREATE INDEX IF NOT EXISTS idx_rooms_interpretation_scope
  ON rooms(project_id, floor_id, interpretation_status, dimension_status, boundary_source);
"""
