BOQ_SCHEMA = r"""
ALTER TABLE boqs ADD COLUMN template_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE boqs ADD COLUMN grouping_mode TEXT NOT NULL DEFAULT 'item';
ALTER TABLE boqs ADD COLUMN floor_filter_json TEXT NOT NULL DEFAULT '[]';

ALTER TABLE boq_rows ADD COLUMN group_key TEXT;
ALTER TABLE boq_rows ADD COLUMN source_ids_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE boq_rows ADD COLUMN floor_ids_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE boq_rows ADD COLUMN template_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE boq_rows ADD COLUMN manual INTEGER NOT NULL DEFAULT 0;
ALTER TABLE boq_rows ADD COLUMN protected_description INTEGER NOT NULL DEFAULT 0;
ALTER TABLE boq_rows ADD COLUMN excluded INTEGER NOT NULL DEFAULT 0;
ALTER TABLE boq_rows ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0;
ALTER TABLE boq_rows ADD COLUMN source_version_hash TEXT;

CREATE TABLE IF NOT EXISTS boq_templates (
  id TEXT PRIMARY KEY,
  project_id TEXT,
  name TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  is_default INTEGER NOT NULL DEFAULT 0,
  definition_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(project_id, name, version),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_boq_templates_scope ON boq_templates(project_id, is_default, version);

CREATE TABLE IF NOT EXISTS export_files (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  boq_id TEXT NOT NULL,
  format TEXT NOT NULL,
  floor_mode TEXT NOT NULL DEFAULT 'combined',
  floor_id TEXT,
  boq_version INTEGER NOT NULL,
  template_version INTEGER NOT NULL,
  cache_key TEXT NOT NULL UNIQUE,
  object_key TEXT,
  filename TEXT,
  status TEXT NOT NULL DEFAULT 'processing',
  error_message TEXT,
  created_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(boq_id) REFERENCES boqs(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE SET NULL,
  FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_exports_scope ON export_files(project_id, boq_id, status, format, boq_version, template_version);
CREATE UNIQUE INDEX IF NOT EXISTS idx_boq_rows_group ON boq_rows(boq_id, group_key) WHERE manual = 0;
"""
