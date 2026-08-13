MODEL_REVIEW_SCHEMA = r"""
ALTER TABLE elements ADD COLUMN friendly_number TEXT;
ALTER TABLE elements ADD COLUMN tag_text TEXT;
ALTER TABLE elements ADD COLUMN assigned_schedule_entry_id TEXT;
ALTER TABLE elements ADD COLUMN detection_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE elements ADD COLUMN is_manual INTEGER NOT NULL DEFAULT 0;
ALTER TABLE elements ADD COLUMN provider_name TEXT;

CREATE TABLE IF NOT EXISTS floor_detection_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  crop_id TEXT NOT NULL,
  crop_version INTEGER NOT NULL,
  provider_name TEXT,
  raw_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'ready',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(project_id, floor_id, crop_version),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(crop_id) REFERENCES floor_crops(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_detection_runs_floor_version
  ON floor_detection_runs(project_id, floor_id, crop_version, status);
CREATE INDEX IF NOT EXISTS idx_elements_review_scope
  ON elements(project_id, floor_id, element_type, excluded, status, detection_version);
"""
