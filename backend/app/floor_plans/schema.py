"""Database additions for the multi-floor Floor Plans step."""

FLOOR_PLANS_SCHEMA = r"""
ALTER TABLE projects ADD COLUMN default_wall_height_mm REAL NOT NULL DEFAULT 2700;
ALTER TABLE projects ADD COLUMN measurement_unit TEXT NOT NULL DEFAULT 'mm';

ALTER TABLE floors ADD COLUMN uses_default_height INTEGER NOT NULL DEFAULT 1;
ALTER TABLE floors ADD COLUMN wall_height_mm REAL;
ALTER TABLE floors ADD COLUMN is_custom_name INTEGER NOT NULL DEFAULT 0;
ALTER TABLE floors ADD COLUMN source_document_id TEXT;
ALTER TABLE floors ADD COLUMN source_page_number INTEGER;
ALTER TABLE floors ADD COLUMN source_rotation INTEGER NOT NULL DEFAULT 0;

ALTER TABLE floor_crops ADD COLUMN source_page_number INTEGER;
ALTER TABLE floor_crops ADD COLUMN original_page_width REAL;
ALTER TABLE floor_crops ADD COLUMN original_page_height REAL;
ALTER TABLE floor_crops ADD COLUMN rotation INTEGER NOT NULL DEFAULT 0;
ALTER TABLE floor_crops ADD COLUMN render_dpi INTEGER NOT NULL DEFAULT 144;
ALTER TABLE floor_crops ADD COLUMN preview_asset_key TEXT;
ALTER TABLE floor_crops ADD COLUMN coordinate_space TEXT NOT NULL DEFAULT 'original_source';
ALTER TABLE floor_crops ADD COLUMN source_changed INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_floors_project_order
  ON floors(project_id, level_index, status);
CREATE INDEX IF NOT EXISTS idx_floors_source
  ON floors(project_id, source_document_id, source_page_number);
CREATE INDEX IF NOT EXISTS idx_floor_crops_source_page
  ON floor_crops(project_id, floor_id, document_id, source_page_number, crop_version);
"""
