SCALE_SCHEMA = r"""
ALTER TABLE calibrations ADD COLUMN source_document_id TEXT;
ALTER TABLE calibrations ADD COLUMN source_page_number INTEGER;
ALTER TABLE calibrations ADD COLUMN crop_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE calibrations ADD COLUMN real_distance_mm REAL;
ALTER TABLE calibrations ADD COLUMN mm_per_pixel REAL;
ALTER TABLE calibrations ADD COLUMN verification_points_json TEXT;
ALTER TABLE calibrations ADD COLUMN verification_expected_mm REAL;
ALTER TABLE calibrations ADD COLUMN verification_measured_mm REAL;
ALTER TABLE calibrations ADD COLUMN verification_difference_percent REAL;
ALTER TABLE calibrations ADD COLUMN input_unit TEXT;
CREATE INDEX IF NOT EXISTS idx_calibrations_floor_current
  ON calibrations(project_id, floor_id, scale_version, status);
CREATE INDEX IF NOT EXISTS idx_calibrations_source
  ON calibrations(project_id, source_document_id, source_page_number, crop_version);
"""
