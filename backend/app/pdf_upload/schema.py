"""Database additions for the Upload PDF and background-ingestion step."""

PDF_UPLOAD_SCHEMA = r"""
ALTER TABLE documents ADD COLUMN original_file_name TEXT;
ALTER TABLE documents ADD COLUMN is_primary INTEGER NOT NULL DEFAULT 0;
ALTER TABLE documents ADD COLUMN validation_status TEXT NOT NULL DEFAULT 'ready';
ALTER TABLE documents ADD COLUMN validation_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE documents ADD COLUMN manifest_status TEXT NOT NULL DEFAULT 'not_ready';
ALTER TABLE documents ADD COLUMN ingestion_status TEXT NOT NULL DEFAULT 'not_ready';
ALTER TABLE documents ADD COLUMN manifest_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE documents ADD COLUMN duplicate_of_document_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_project_hash_unique
  ON documents(project_id, content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_project_primary
  ON documents(project_id, document_type, is_primary, created_at);
CREATE INDEX IF NOT EXISTS idx_documents_ingestion_status
  ON documents(project_id, manifest_status, ingestion_status, version);

ALTER TABLE document_pages ADD COLUMN page_label TEXT;
ALTER TABLE document_pages ADD COLUMN media_box_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE document_pages ADD COLUMN metadata_status TEXT NOT NULL DEFAULT 'not_ready';
ALTER TABLE document_pages ADD COLUMN thumbnail_status TEXT NOT NULL DEFAULT 'not_ready';
ALTER TABLE document_pages ADD COLUMN preview_status TEXT NOT NULL DEFAULT 'not_ready';
ALTER TABLE document_pages ADD COLUMN text_status TEXT NOT NULL DEFAULT 'not_ready';
ALTER TABLE document_pages ADD COLUMN classification_status TEXT NOT NULL DEFAULT 'not_ready';
ALTER TABLE document_pages ADD COLUMN classification TEXT;
ALTER TABLE document_pages ADD COLUMN classification_confidence REAL;
ALTER TABLE document_pages ADD COLUMN vector_text_available INTEGER NOT NULL DEFAULT 0;
ALTER TABLE document_pages ADD COLUMN text_char_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE document_pages ADD COLUMN thumbnail_width INTEGER;
ALTER TABLE document_pages ADD COLUMN thumbnail_height INTEGER;
ALTER TABLE document_pages ADD COLUMN preview_width INTEGER;
ALTER TABLE document_pages ADD COLUMN preview_height INTEGER;
ALTER TABLE document_pages ADD COLUMN error_message TEXT;

CREATE INDEX IF NOT EXISTS idx_document_pages_manifest
  ON document_pages(project_id, document_id, metadata_status, page_number);
CREATE INDEX IF NOT EXISTS idx_document_pages_classification
  ON document_pages(project_id, document_id, classification, classification_status, page_number);

CREATE TABLE IF NOT EXISTS extraction_records (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  floor_id TEXT,
  document_id TEXT NOT NULL,
  document_page_id TEXT NOT NULL,
  extraction_type TEXT NOT NULL,
  entity_key TEXT NOT NULL,
  data_json TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_location_json TEXT NOT NULL DEFAULT '{}',
  extraction_method TEXT NOT NULL,
  confidence REAL,
  quality_signal TEXT,
  review_state TEXT NOT NULL DEFAULT 'needs_review',
  extraction_version INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(document_id, extraction_type, entity_key, extraction_version),
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(floor_id) REFERENCES floors(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY(document_page_id) REFERENCES document_pages(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_extraction_records_scope
  ON extraction_records(project_id, floor_id, extraction_type, review_state, extraction_version);
CREATE INDEX IF NOT EXISTS idx_extraction_records_source
  ON extraction_records(document_id, document_page_id, extraction_type, extraction_version);
"""
