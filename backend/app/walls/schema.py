WALLS_SCHEMA = r"""
ALTER TABLE walls ADD COLUMN friendly_number TEXT;
ALTER TABLE walls ADD COLUMN centerline_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE walls ADD COLUMN generated_centerline_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE walls ADD COLUMN length_mm REAL;
ALTER TABLE walls ADD COLUMN height_source TEXT;
ALTER TABLE walls ADD COLUMN height_override_mm REAL;
ALTER TABLE walls ADD COLUMN side_1_finish TEXT;
ALTER TABLE walls ADD COLUMN side_2_finish TEXT;
ALTER TABLE walls ADD COLUMN boundary_role TEXT;

CREATE TABLE IF NOT EXISTS wall_openings (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  wall_id TEXT NOT NULL,
  element_id TEXT NOT NULL,
  opening_type TEXT NOT NULL,
  width_mm REAL,
  height_mm REAL,
  opening_area_m2 REAL,
  deduction_area_m2 REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'needs_review',
  relation_version INTEGER NOT NULL DEFAULT 1,
  created_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(project_id, floor_id, element_id),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(wall_id) REFERENCES walls(id) ON DELETE CASCADE,
  FOREIGN KEY(element_id) REFERENCES elements(id) ON DELETE CASCADE,
  FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_wall_openings_wall
  ON wall_openings(project_id, floor_id, wall_id, status);
CREATE INDEX IF NOT EXISTS idx_walls_geometry_scope
  ON walls(project_id, floor_id, classification, wall_type, status, wall_version);
"""
