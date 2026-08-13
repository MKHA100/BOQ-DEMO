from __future__ import annotations

FORMAL_BOQ_TABLES_SQL = r"""
CREATE TABLE IF NOT EXISTS boq_document_setups (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL UNIQUE,
  project_name TEXT NOT NULL DEFAULT '',
  client_name TEXT NOT NULL DEFAULT '',
  consultant_name TEXT NOT NULL DEFAULT '',
  location TEXT NOT NULL DEFAULT '',
  boq_title TEXT NOT NULL DEFAULT 'Bill of Quantities',
  currency TEXT NOT NULL DEFAULT 'Rs',
  vat_percentage REAL NOT NULL DEFAULT 0,
  include_rates INTEGER NOT NULL DEFAULT 0,
  include_amounts INTEGER NOT NULL DEFAULT 0,
  include_preliminaries INTEGER NOT NULL DEFAULT 1,
  include_provisional_sums INTEGER NOT NULL DEFAULT 0,
  include_signature_section INTEGER NOT NULL DEFAULT 1,
  format_style TEXT NOT NULL DEFAULT 'formal_tender',
  item_numbering_format TEXT NOT NULL DEFAULT 'section_sequence',
  measurement_unit_style TEXT NOT NULL DEFAULT 'metric',
  description_style TEXT NOT NULL DEFAULT 'standard',
  section_order_json TEXT NOT NULL DEFAULT '[]',
  setup_version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_boq_document_setups_project_version
ON boq_document_setups(project_id, setup_version);

CREATE TABLE IF NOT EXISTS boq_template_items (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  template_id TEXT NOT NULL,
  name TEXT NOT NULL,
  element_type TEXT NOT NULL,
  section_code TEXT,
  section_name TEXT NOT NULL,
  unit TEXT NOT NULL,
  description_template TEXT NOT NULL,
  keywords_json TEXT NOT NULL DEFAULT '[]',
  template_mode TEXT NOT NULL DEFAULT 'standard',
  conditional_rules_json TEXT NOT NULL DEFAULT '[]',
  formula_json TEXT NOT NULL DEFAULT '{}',
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(template_id) REFERENCES boq_templates(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_boq_template_items_scope
ON boq_template_items(project_id, template_id, element_type, is_active, sort_order);
"""
