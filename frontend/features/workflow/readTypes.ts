import type { ValueSource, VersionSet, WorkflowStatus } from "./types";

export type PagedResult<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type DocumentPageRecord = {
  id: string;
  project_id: string;
  document_id: string;
  page_number: number;
  width_points: number | null;
  height_points: number | null;
  rotation: number;
  thumbnail_key: string | null;
  preview_key: string | null;
  text_layer_key: string | null;
  status: WorkflowStatus;
  version: number;
};

export type FloorCropRecord = {
  id: string;
  project_id: string;
  floor_id: string;
  document_id: string;
  document_page_id: string;
  coordinates: Record<string, unknown>;
  crop_asset_key: string | null;
  crop_version: number;
  status: WorkflowStatus;
  is_current: boolean;
};

export type CalibrationRecord = {
  id: string;
  project_id: string;
  floor_id: string;
  point_a: { x: number; y: number };
  point_b: { x: number; y: number };
  pixel_distance: number;
  real_distance: number;
  unit: string;
  units_per_pixel: number;
  source_crop_version: number;
  scale_version: number;
  status: WorkflowStatus;
};

export type ElementPropertyRecord = {
  id: string;
  project_id: string;
  floor_id: string;
  element_id: string;
  property_name: string;
  value: unknown;
  unit: string | null;
  source: ValueSource;
  source_priority: number;
  is_confirmed: boolean;
  suggestion_value?: unknown;
  suggestion_source?: ValueSource | null;
  element_version: number;
};

export type ElementRecord = {
  id: string;
  project_id: string;
  floor_id: string;
  element_type: string;
  type_code: string | null;
  geometry: Record<string, unknown>;
  source: ValueSource;
  confidence: number | null;
  status: WorkflowStatus;
  excluded: boolean;
  user_confirmed: boolean;
  measurement_status: WorkflowStatus;
  element_version: number;
  source_versions: VersionSet;
  properties: ElementPropertyRecord[];
};

export type WallRecord = {
  id: string;
  project_id: string;
  floor_id: string;
  geometry: Record<string, unknown>;
  wall_type: string | null;
  classification: string | null;
  thickness_mm: number | null;
  height_mm: number | null;
  gross_area_m2: number | null;
  deduction_area_m2: number | null;
  net_area_m2: number | null;
  status: WorkflowStatus;
  is_stale: boolean;
  user_confirmed: boolean;
  wall_version: number;
  source_versions: VersionSet;
};

export type RoomRecord = {
  id: string;
  project_id: string;
  floor_id: string;
  name: string | null;
  geometry: Record<string, unknown>;
  area_m2: number | null;
  perimeter_m: number | null;
  finish_code: string | null;
  status: WorkflowStatus;
  is_stale: boolean;
  user_confirmed: boolean;
  room_version: number;
  source_versions: VersionSet;
};

export type ReviewIssueRecord = {
  id: string;
  project_id: string;
  floor_id: string | null;
  entity_type: string;
  entity_id: string | null;
  issue_type: string;
  title: string;
  detail: string | null;
  severity: string;
  status: WorkflowStatus;
  suggestion: Record<string, unknown> | null;
  source: string | null;
  review_version: number;
};

export type BoqRecord = {
  id: string;
  project_id: string;
  name: string;
  template_id: string | null;
  status: WorkflowStatus;
  is_stale: boolean;
  boq_version: number;
  source_versions: VersionSet;
};

export type BoqRowRecord = {
  id: string;
  project_id: string;
  floor_id: string | null;
  boq_id: string;
  entity_type: string | null;
  entity_id: string | null;
  section: string | null;
  item_code: string | null;
  description: string;
  quantity: number;
  unit: string;
  rate: number | null;
  amount: number | null;
  status: WorkflowStatus;
  is_stale: boolean;
  source_versions: VersionSet;
  boq_version: number;
};

export type BoqView = PagedResult<BoqRowRecord> & { boq: BoqRecord | null };
