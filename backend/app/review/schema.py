REVIEW_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS review_items (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  display_number TEXT,
  title TEXT NOT NULL,
  data_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'needs_review',
  critical INTEGER NOT NULL DEFAULT 0,
  is_stale INTEGER NOT NULL DEFAULT 0,
  source_version INTEGER NOT NULL DEFAULT 0,
  review_version INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(project_id, entity_type, entity_id),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_review_items_scope ON review_items(project_id, floor_id, entity_type, status, critical, review_version);
CREATE INDEX IF NOT EXISTS idx_review_items_stale ON review_items(project_id, is_stale, source_version);
"""
