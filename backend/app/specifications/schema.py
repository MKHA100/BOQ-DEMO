"""Database additions for Schedules & Specifications."""

SPECIFICATIONS_SCHEMA = r"""
ALTER TABLE schedule_files ADD COLUMN source_type TEXT NOT NULL DEFAULT 'file';
ALTER TABLE schedule_files ADD COLUMN source_page_number INTEGER;
ALTER TABLE schedule_files ADD COLUMN file_name TEXT;
ALTER TABLE schedule_files ADD COLUMN mime_type TEXT;
ALTER TABLE schedule_files ADD COLUMN content_hash TEXT;
ALTER TABLE schedule_files ADD COLUMN size_bytes INTEGER NOT NULL DEFAULT 0;
ALTER TABLE schedule_files ADD COLUMN asset_key TEXT;
ALTER TABLE schedule_files ADD COLUMN preview_asset_key TEXT;
ALTER TABLE schedule_files ADD COLUMN scope_mode TEXT NOT NULL DEFAULT 'all';
ALTER TABLE schedule_files ADD COLUMN extraction_schema_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE schedule_files ADD COLUMN extraction_status TEXT NOT NULL DEFAULT 'processing';
ALTER TABLE schedule_files ADD COLUMN error_message TEXT;
ALTER TABLE schedule_files ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;

ALTER TABLE specification_files ADD COLUMN source_type TEXT NOT NULL DEFAULT 'file';
ALTER TABLE specification_files ADD COLUMN source_page_number INTEGER;
ALTER TABLE specification_files ADD COLUMN file_name TEXT;
ALTER TABLE specification_files ADD COLUMN mime_type TEXT;
ALTER TABLE specification_files ADD COLUMN content_hash TEXT;
ALTER TABLE specification_files ADD COLUMN size_bytes INTEGER NOT NULL DEFAULT 0;
ALTER TABLE specification_files ADD COLUMN asset_key TEXT;
ALTER TABLE specification_files ADD COLUMN preview_asset_key TEXT;
ALTER TABLE specification_files ADD COLUMN scope_mode TEXT NOT NULL DEFAULT 'all';
ALTER TABLE specification_files ADD COLUMN extraction_schema_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE specification_files ADD COLUMN extraction_status TEXT NOT NULL DEFAULT 'processing';
ALTER TABLE specification_files ADD COLUMN error_message TEXT;
ALTER TABLE specification_files ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS specification_category_states (
  project_id TEXT NOT NULL,
  category TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'needs_review',
  updated_at TEXT NOT NULL,
  PRIMARY KEY(project_id, category),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS supporting_file_floors (
  source_id TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(source_id, floor_id),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_supporting_file_floors_scope
  ON supporting_file_floors(project_id, floor_id, source_kind);

CREATE TABLE IF NOT EXISTS schedule_entries (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  category TEXT NOT NULL,
  entity_key TEXT NOT NULL,
  data_json TEXT NOT NULL,
  source_location_json TEXT NOT NULL DEFAULT '{}',
  extraction_method TEXT NOT NULL,
  confidence REAL,
  review_state TEXT NOT NULL DEFAULT 'needs_review',
  is_accepted INTEGER NOT NULL DEFAULT 0,
  source_priority INTEGER NOT NULL,
  extraction_version INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(source_id, entity_key, extraction_version),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_schedule_entries_project_category
  ON schedule_entries(project_id, category, entity_key, review_state, extraction_version);
CREATE INDEX IF NOT EXISTS idx_schedule_entries_source
  ON schedule_entries(source_id, source_kind, extraction_version);

CREATE TABLE IF NOT EXISTS schedule_extraction_cache (
  content_hash TEXT NOT NULL,
  category TEXT NOT NULL,
  schema_version INTEGER NOT NULL,
  result_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(content_hash, category, schema_version)
);

CREATE INDEX IF NOT EXISTS idx_schedule_files_fast
  ON schedule_files(project_id, schedule_type, extraction_status, is_active, updated_at);
CREATE INDEX IF NOT EXISTS idx_schedule_files_hash
  ON schedule_files(project_id, content_hash, schedule_type, extraction_schema_version);
CREATE INDEX IF NOT EXISTS idx_specification_files_fast
  ON specification_files(project_id, specification_type, extraction_status, is_active, updated_at);
CREATE INDEX IF NOT EXISTS idx_specification_files_hash
  ON specification_files(project_id, content_hash, specification_type, extraction_schema_version);
"""
