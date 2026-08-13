FLOORS_SCHEMA = r"""
ALTER TABLE rooms ADD COLUMN friendly_number TEXT;
ALTER TABLE rooms ADD COLUMN room_type TEXT;
ALTER TABLE rooms ADD COLUMN floor_type_code TEXT;
ALTER TABLE rooms ADD COLUMN floor_finish TEXT;
ALTER TABLE rooms ADD COLUMN generated_geometry_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE rooms ADD COLUMN manual_area_override_m2 REAL;
ALTER TABLE rooms ADD COLUMN label_source TEXT;
ALTER TABLE rooms ADD COLUMN finish_source TEXT;
ALTER TABLE rooms ADD COLUMN geometry_status TEXT NOT NULL DEFAULT 'needs_review';

CREATE TABLE IF NOT EXISTS room_wall_relations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  room_id TEXT NOT NULL,
  wall_id TEXT NOT NULL,
  relation_type TEXT NOT NULL DEFAULT 'boundary',
  relation_version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(room_id, wall_id),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE,
  FOREIGN KEY(wall_id) REFERENCES walls(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_room_wall_scope ON room_wall_relations(project_id, floor_id, wall_id, room_id);

CREATE TABLE IF NOT EXISTS room_label_evidence (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  room_id TEXT NOT NULL,
  evidence_hash TEXT NOT NULL,
  label TEXT,
  room_type TEXT,
  finish TEXT,
  source TEXT NOT NULL,
  confidence REAL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(room_id, evidence_hash),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_rooms_scope_version ON rooms(project_id, floor_id, status, room_version, is_stale);
"""
