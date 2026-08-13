"""Portable SQLite/PostgreSQL schema for the shared AutoBOQ workflow domain."""

WORKFLOW_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS project_versions (
  project_id TEXT PRIMARY KEY,
  document_version INTEGER NOT NULL DEFAULT 0,
  schedule_version INTEGER NOT NULL DEFAULT 0,
  specification_version INTEGER NOT NULL DEFAULT 0,
  review_version INTEGER NOT NULL DEFAULT 0,
  boq_version INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS floors (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  level_index INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'not_ready',
  created_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(project_id, level_index),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_floors_project_status ON floors(project_id, status, level_index);

CREATE TABLE IF NOT EXISTS floor_versions (
  floor_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  crop_version INTEGER NOT NULL DEFAULT 0,
  schedule_version INTEGER NOT NULL DEFAULT 0,
  scale_version INTEGER NOT NULL DEFAULT 0,
  element_version INTEGER NOT NULL DEFAULT 0,
  wall_version INTEGER NOT NULL DEFAULT 0,
  room_version INTEGER NOT NULL DEFAULT 0,
  review_version INTEGER NOT NULL DEFAULT 0,
  boq_version INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_floor_versions_project ON floor_versions(project_id, updated_at);

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_type TEXT NOT NULL DEFAULT 'source',
  file_name TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  storage_key TEXT NOT NULL,
  content_hash TEXT,
  size_bytes INTEGER NOT NULL DEFAULT 0,
  page_count INTEGER,
  status TEXT NOT NULL DEFAULT 'not_ready',
  version INTEGER NOT NULL DEFAULT 1,
  created_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(project_id, storage_key),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_project_type_status ON documents(project_id, document_type, status, version);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(project_id, content_hash);

CREATE TABLE IF NOT EXISTS document_pages (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  page_number INTEGER NOT NULL,
  width_points REAL,
  height_points REAL,
  rotation INTEGER NOT NULL DEFAULT 0,
  thumbnail_key TEXT,
  preview_key TEXT,
  text_layer_key TEXT,
  status TEXT NOT NULL DEFAULT 'not_ready',
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(document_id, page_number),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_document_pages_project_status ON document_pages(project_id, status, page_number);

CREATE TABLE IF NOT EXISTS floor_crops (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  document_page_id TEXT NOT NULL,
  coordinates_json TEXT NOT NULL DEFAULT '{}',
  source_width REAL,
  source_height REAL,
  crop_asset_key TEXT,
  crop_version INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'not_ready',
  is_current INTEGER NOT NULL DEFAULT 1,
  created_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(project_id, floor_id, crop_version),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY(document_page_id) REFERENCES document_pages(id) ON DELETE CASCADE,
  FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_floor_crops_project_floor_current ON floor_crops(project_id, floor_id, is_current, crop_version);

CREATE TABLE IF NOT EXISTS schedule_files (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT,
  document_id TEXT NOT NULL,
  schedule_type TEXT NOT NULL,
  source_crop_json TEXT,
  extracted_data_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'not_ready',
  schedule_version INTEGER NOT NULL,
  created_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_schedule_files_scope_type_status ON schedule_files(project_id, floor_id, schedule_type, status, schedule_version);

CREATE TABLE IF NOT EXISTS specification_files (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT,
  document_id TEXT NOT NULL,
  specification_type TEXT NOT NULL DEFAULT 'general',
  source_crop_json TEXT,
  extracted_data_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'not_ready',
  specification_version INTEGER NOT NULL,
  created_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_specification_files_scope_status ON specification_files(project_id, floor_id, status, specification_version);

CREATE TABLE IF NOT EXISTS calibrations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  point_a_json TEXT NOT NULL,
  point_b_json TEXT NOT NULL,
  pixel_distance REAL NOT NULL,
  real_distance REAL NOT NULL,
  unit TEXT NOT NULL,
  units_per_pixel REAL NOT NULL,
  source_crop_version INTEGER NOT NULL,
  scale_version INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'confirmed',
  confirmed_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(project_id, floor_id, scale_version),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(confirmed_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_calibrations_project_floor_status ON calibrations(project_id, floor_id, status, scale_version);

CREATE TABLE IF NOT EXISTS elements (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  element_type TEXT NOT NULL,
  type_code TEXT,
  geometry_json TEXT NOT NULL DEFAULT '{}',
  source TEXT NOT NULL DEFAULT 'model',
  confidence REAL,
  status TEXT NOT NULL DEFAULT 'needs_review',
  excluded INTEGER NOT NULL DEFAULT 0,
  user_confirmed INTEGER NOT NULL DEFAULT 0,
  measurement_status TEXT NOT NULL DEFAULT 'not_ready',
  element_version INTEGER NOT NULL,
  source_versions_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  crop_id TEXT,
  crop_version INTEGER,
  detection_run_id TEXT,
  generated_status TEXT NOT NULL DEFAULT 'current',
  detection_model_id TEXT,
  detection_input_hash TEXT,
  analysis_mode TEXT NOT NULL DEFAULT 'standard',
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_elements_project_floor_type_status ON elements(project_id, floor_id, element_type, status, element_version);
CREATE INDEX IF NOT EXISTS idx_elements_floor_measurement ON elements(project_id, floor_id, measurement_status, excluded);

CREATE TABLE IF NOT EXISTS element_properties (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  element_id TEXT NOT NULL,
  property_name TEXT NOT NULL,
  value_json TEXT NOT NULL,
  unit TEXT,
  source TEXT NOT NULL,
  source_priority INTEGER NOT NULL,
  is_confirmed INTEGER NOT NULL DEFAULT 0,
  suggestion_value_json TEXT,
  suggestion_source TEXT,
  element_version INTEGER NOT NULL,
  created_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(element_id, property_name),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(element_id) REFERENCES elements(id) ON DELETE CASCADE,
  FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_element_properties_scope_name ON element_properties(project_id, floor_id, property_name, source, element_version);

CREATE TABLE IF NOT EXISTS element_relations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  source_element_id TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'confirmed',
  version INTEGER NOT NULL DEFAULT 1,
  created_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(source_element_id, target_type, target_id, relation_type),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(source_element_id) REFERENCES elements(id) ON DELETE CASCADE,
  FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_element_relations_target ON element_relations(project_id, floor_id, target_type, target_id, relation_type);

CREATE TABLE IF NOT EXISTS walls (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  geometry_json TEXT NOT NULL DEFAULT '{}',
  wall_type TEXT,
  classification TEXT,
  thickness_mm REAL,
  height_mm REAL,
  gross_area_m2 REAL,
  deduction_area_m2 REAL,
  net_area_m2 REAL,
  status TEXT NOT NULL DEFAULT 'not_ready',
  is_stale INTEGER NOT NULL DEFAULT 1,
  user_confirmed INTEGER NOT NULL DEFAULT 0,
  wall_version INTEGER NOT NULL,
  source_versions_json TEXT NOT NULL DEFAULT '{}',
  source_crop_version INTEGER,
  generated_status TEXT NOT NULL DEFAULT 'current',
  created_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_walls_project_floor_type_status ON walls(project_id, floor_id, wall_type, status, wall_version);
CREATE INDEX IF NOT EXISTS idx_walls_floor_stale ON walls(project_id, floor_id, is_stale);

CREATE TABLE IF NOT EXISTS rooms (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT NOT NULL,
  name TEXT,
  geometry_json TEXT NOT NULL DEFAULT '{}',
  area_m2 REAL,
  perimeter_m REAL,
  finish_code TEXT,
  status TEXT NOT NULL DEFAULT 'not_ready',
  is_stale INTEGER NOT NULL DEFAULT 1,
  user_confirmed INTEGER NOT NULL DEFAULT 0,
  room_version INTEGER NOT NULL,
  source_versions_json TEXT NOT NULL DEFAULT '{}',
  source_crop_version INTEGER,
  generated_status TEXT NOT NULL DEFAULT 'current',
  created_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_rooms_project_floor_status ON rooms(project_id, floor_id, status, room_version);
CREATE INDEX IF NOT EXISTS idx_rooms_floor_stale ON rooms(project_id, floor_id, is_stale);

CREATE TABLE IF NOT EXISTS review_issues (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT,
  entity_type TEXT NOT NULL,
  entity_id TEXT,
  issue_type TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT,
  severity TEXT NOT NULL DEFAULT 'medium',
  status TEXT NOT NULL DEFAULT 'needs_review',
  suggestion_json TEXT,
  source TEXT,
  review_version INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  resolved_at TEXT,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_review_issues_scope_status ON review_issues(project_id, floor_id, status, entity_type, review_version);

CREATE TABLE IF NOT EXISTS quantity_snapshots (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT,
  entity_type TEXT NOT NULL,
  entity_id TEXT,
  quantity_type TEXT NOT NULL,
  value REAL NOT NULL,
  unit TEXT NOT NULL,
  source_versions_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'ready',
  version INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_quantity_snapshots_scope_type ON quantity_snapshots(project_id, floor_id, entity_type, quantity_type, status, version);

CREATE TABLE IF NOT EXISTS boqs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL DEFAULT 'Bill of Quantities',
  template_id TEXT,
  status TEXT NOT NULL DEFAULT 'not_ready',
  is_stale INTEGER NOT NULL DEFAULT 1,
  boq_version INTEGER NOT NULL,
  source_versions_json TEXT NOT NULL DEFAULT '{}',
  generated_at TEXT,
  created_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_boqs_project_status ON boqs(project_id, status, is_stale, boq_version);

CREATE TABLE IF NOT EXISTS boq_rows (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT,
  boq_id TEXT NOT NULL,
  entity_type TEXT,
  entity_id TEXT,
  section TEXT,
  item_code TEXT,
  description TEXT NOT NULL,
  quantity REAL NOT NULL DEFAULT 0,
  unit TEXT NOT NULL,
  rate REAL,
  amount REAL,
  status TEXT NOT NULL DEFAULT 'not_ready',
  is_stale INTEGER NOT NULL DEFAULT 1,
  source_versions_json TEXT NOT NULL DEFAULT '{}',
  boq_version INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(boq_id) REFERENCES boqs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_boq_rows_scope_status ON boq_rows(project_id, floor_id, entity_type, status, is_stale, boq_version);
CREATE INDEX IF NOT EXISTS idx_boq_rows_entity ON boq_rows(project_id, entity_type, entity_id);

CREATE TABLE IF NOT EXISTS job_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT,
  floor_id TEXT,
  category TEXT NOT NULL,
  task_type TEXT NOT NULL,
  job_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'pending',
  progress INTEGER NOT NULL DEFAULT 0,
  message TEXT,
  payload_json TEXT NOT NULL DEFAULT '{}',
  input_versions_json TEXT NOT NULL DEFAULT '{}',
  result_json TEXT NOT NULL DEFAULT '{}',
  error_message TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  retry_at TEXT,
  locked_by TEXT,
  lease_expires_at TEXT,
  heartbeat_at TEXT,
  created_by TEXT,
  started_at TEXT,
  finished_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_job_runs_claim ON job_runs(status, retry_at, created_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_scope_task ON job_runs(project_id, floor_id, category, task_type, status, created_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_lease ON job_runs(status, lease_expires_at);

CREATE TABLE IF NOT EXISTS outbox_events (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT,
  event_type TEXT NOT NULL,
  entity_type TEXT,
  entity_id TEXT,
  dedupe_key TEXT NOT NULL UNIQUE,
  payload_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  available_at TEXT NOT NULL,
  locked_by TEXT,
  locked_at TEXT,
  published_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_outbox_events_publish ON outbox_events(status, available_at, created_at);
CREATE INDEX IF NOT EXISTS idx_outbox_events_project ON outbox_events(project_id, floor_id, event_type, created_at);
"""
