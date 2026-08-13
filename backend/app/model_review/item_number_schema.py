MODEL_REVIEW_ITEM_NUMBER_SCHEMA = """
ALTER TABLE elements ADD COLUMN item_number INTEGER;
ALTER TABLE walls ADD COLUMN source_element_id TEXT;
ALTER TABLE walls ADD COLUMN item_number INTEGER;

CREATE UNIQUE INDEX IF NOT EXISTS idx_elements_project_item_number
  ON elements(project_id, item_number);
CREATE INDEX IF NOT EXISTS idx_elements_project_type_item
  ON elements(project_id, element_type, item_number);
CREATE INDEX IF NOT EXISTS idx_walls_project_item_number
  ON walls(project_id, item_number);
CREATE INDEX IF NOT EXISTS idx_walls_source_element
  ON walls(project_id, floor_id, source_element_id);
"""
