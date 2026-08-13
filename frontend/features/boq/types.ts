export type BoqSourceItem = {
  id: string;
  display_number: string | null;
  item_number?: number | null;
  element_type: string;
  type_code?: string | null;
  floor_id?: string | null;
  floor?: string | null;
  width_mm?: number | null;
  height_mm?: number | null;
  material?: string | null;
  quantity?: number | null;
  finish?: string | null;
};

export type BoqRow = {
  id: string;
  floor_id: string | null;
  entity_type: string | null;
  section: string | null;
  item_code: string | null;
  boq_item_number?: string | null;
  bill_no?: string | null;
  bill_name?: string | null;
  subcategory_code?: string | null;
  subcategory_name?: string | null;
  description: string;
  quantity: number;
  unit: string;
  rate: number | null;
  amount: number | null;
  status: "ready" | "needs_review" | string;
  source_ids: string[];
  source_items: BoqSourceItem[];
  floor_ids: string[];
  floor_names: string[];
  missing_fields: string[];
  manual: boolean;
  protected_description: boolean;
  protected_rate?: boolean;
  excluded: boolean;
  sort_order: number;
};

export type BoqExport = {
  id: string;
  format: "pdf" | "xlsx" | "csv";
  floor_mode: "combined" | "floor_breakdown" | "selected_floor";
  floor_id: string | null;
  filename: string;
  status: "processing" | "ready" | "failed";
  error_message?: string | null;
  boq_version: number;
  template_version: number;
  setup_version?: number;
  created_at: string;
};

export type BoqSummary = {
  rows: number;
  ready: number;
  needs_review: number;
  manual: number;
  doors: number;
  windows: number;
  walls: number;
  floors: number;
  subtotal?: number;
};

export type BoqDocumentSetup = {
  id: string;
  project_id: string;
  project_name: string;
  client_name: string;
  consultant_name: string;
  location: string;
  boq_title: string;
  currency: string;
  vat_percentage: number;
  include_rates: boolean;
  include_amounts: boolean;
  include_preliminaries: boolean;
  include_provisional_sums: boolean;
  include_signature_section: boolean;
  format_style: "quantity_takeoff" | "formal_tender" | "lot_based" | "standard_construction";
  item_numbering_format: "source_item_number" | "section_sequence" | "simple_sequence";
  measurement_unit_style: "metric" | "imperial" | "mixed";
  description_style: "standard" | "detailed" | "short";
  section_order: string[];
  setup_version: number;
};

export type BoqConditionalRule = {
  field: string;
  operator: "exists" | "missing" | "equals" | "not_equals" | "contains";
  value?: string;
  prefix?: string;
  suffix?: string;
  description_template?: string;
};

export type BoqTemplateMode = "standard" | "conditional";
export type BoqConditionValueType = "number" | "string";
export type BoqConditionOperator = "<" | "<=" | ">" | ">=" | "=" | "==" | "!=";
export type BoqFormulaOperation = "value" | "multiply" | "sum" | "subtract" | "divide" | "count";
export type BoqConditionalBranchType = "if" | "elseif" | "else";

export type BoqTemplateCondition = {
  variable: string;
  operator: BoqConditionOperator;
  value: string | number;
  value_type: BoqConditionValueType;
};

export type BoqAmountFormula = {
  operation: BoqFormulaOperation;
  variables: string[];
  constant?: number | null;
};

export type BoqConditionalBranchOutput = {
  description_template: string;
  unit: string;
  amount_formula: BoqAmountFormula;
};

export type BoqConditionalBranch = {
  id?: string | null;
  branch_type: BoqConditionalBranchType;
  conditions: BoqTemplateCondition[];
  output: BoqConditionalBranchOutput;
};

export type BoqConditionalRules = {
  branches: BoqConditionalBranch[];
};

export type BoqTemplateItem = {
  id: string;
  template_id: string;
  name: string;
  element_type: "door" | "window" | "wall_external" | "wall_internal" | "floor" | "manual";
  section_code: string | null;
  section_name: string;
  unit: string;
  description_template: string;
  keywords: string[];
  template_mode: BoqTemplateMode;
  conditional_rules: BoqConditionalRule[] | BoqConditionalRules;
  formula: BoqAmountFormula | Record<string, unknown>;
  sort_order: number;
  is_active: boolean;
};

export type BoqTemplatePackage = {
  id: string;
  name: string;
  description: string | null;
  category: string;
  version: number;
  is_default: boolean;
  is_builtin: boolean;
  is_active: boolean;
  items: BoqTemplateItem[];
};

export type BoqPlaceholder = { key: string; label: string; example: string };
export type BoqTemplateLibrary = { packages: BoqTemplatePackage[]; selected_template_id: string; placeholders: BoqPlaceholder[] };

export type FormalBoqReport = {
  title?: string;
  project_name?: string;
  template_name?: string;
  currency?: string;
  vat_percentage?: number;
  summary?: { subtotal?: number; vat?: number; grand_total?: number; bill_count?: number; row_count?: number };
};

export type BoqState = {
  project_id: string;
  boq: {
    id: string;
    name: string;
    status: string;
    boq_version: number;
    template_version: number;
    setup_version: number;
    generated_at: string | null;
    report_hash?: string | null;
  };
  setup: BoqDocumentSetup;
  template: BoqTemplatePackage;
  templates: BoqTemplatePackage[];
  rows: BoqRow[];
  report: FormalBoqReport;
  floors: Array<{ id: string; name: string; level_index: number }>;
  stale: boolean;
  summary: BoqSummary;
  active_jobs: Array<{ id: string; category: string; status: string; task_type?: string }>;
  exports: BoqExport[];
};
