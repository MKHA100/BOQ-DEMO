import type { Point } from "@/features/drawing/types";

export type RoomStatus = "ready" | "needs_review" | "confirmed";

export type RoomCutout = {
  id: string;
  room_id: string;
  name: string | null;
  geometry: { points: Point[] };
  area_m2: number | null;
};

export type GeometryRevision = {
  id: string;
  room_id: string;
  revision: number;
  action: string;
  geometry: { points: Point[] };
  metadata: Record<string, unknown>;
  created_at: string;
};

export type Room = {
  id: string;
  project_id: string;
  floor_id: string;
  friendly_number: string;
  name: string | null;
  room_type: string | null;
  geometry: { points: Point[] };
  generated_geometry: { points?: Point[] };
  area_m2: number | null;
  perimeter_m: number | null;
  floor_type_code: string | null;
  floor_finish: string | null;
  status: RoomStatus;
  geometry_status: string;
  user_confirmed: boolean;
  room_version: number;
  wall_ids: string[];
  opening_ids: string[];
  detection_source: "wall_geometry" | "roboflow" | "hybrid" | "user" | string;
  confidence: number | null;
  model_verified: boolean;
  comparison_status: string;
  excluded: boolean;
  exclusion_reason: string | null;
  space_kind: "internal" | "external" | "circulation" | "void" | string;
  measurement_status: "correct" | "check" | "missing_scale" | "invalid" | string;
  measured_width_m: number | null;
  measured_length_m: number | null;
  printed_width_mm: number | null;
  printed_length_mm: number | null;
  dimension_difference_percent: number | null;
  include_in_boq: boolean;
  parent_room_id: string | null;
  is_finish_zone: boolean;
  open_plan: boolean;
  label_candidates: string[];
  raw_geometry: { points?: Point[] };
  wall_corrected_geometry: { points?: Point[] };
  regularized_geometry: { points?: Point[] };
  confirmed_geometry: { points?: Point[] };
  shape_type: string;
  boundary_source: string;
  precision_status: string;
  user_edited: boolean;
  geometry_version: number;
  edit_revision: number;
  validation_details: { status?: string; issues?: string[]; [key: string]: unknown };
  precision_updated_at: string | null;
  model_polygon: { points?: Point[] };
  wall_corrected_polygon: { points?: Point[] };
  regularized_polygon: { points?: Point[] };
  confirmed_polygon: { points?: Point[] };
  display_polygon: { points?: Point[] };
  processing_stage: "detected" | "interpreting" | "correcting" | "corrected" | "check" | "confirmed" | string;
  interpretation_status: "not_started" | "processing" | "ready" | "needs_review" | "failed" | "skipped" | "confirmed" | string;
  interpretation_warnings: string[];
  interpretation_run_id: string | null;
  dimension_status: "exact" | "partial" | "unknown" | string;
  dimension_source: "drawing" | "llm_verified" | "unknown" | string;
  point_count: number;
  cutouts: RoomCutout[];
};

export type RoomSuggestion = {
  id: string;
  floor_id: string;
  polygon: { points: Point[] };
  confidence: number | null;
  status: "new" | "matched" | "accepted" | "rejected" | "superseded";
  matched_room_id: string | null;
  comparison_score: number | null;
};

export type DimensionSuggestion = {
  id: string;
  label_text: string;
  value_mm: number;
  point_a: Point;
  point_b: Point;
  confidence: number;
  suggested_mm_per_pixel: number;
};

export type RoomFloor = {
  id: string;
  name: string;
  level_index: number;
  crop_version: number;
  scale_version: number;
  element_version: number;
  wall_version: number;
  room_version: number;
  mm_per_pixel: number | null;
  scale_verified: boolean;
  room_count: number;
  finish_zone_count: number;
  dimension_suggestions: DimensionSuggestion[];
  needs_review_count: number;
  confirmed_count: number;
  area_total_m2: number;
  drawing_url: string | null;
  drawing_width: number;
  drawing_height: number;
  analysis_status: "processing" | "detected" | "interpreting" | "correcting" | "ready" | "not_ready";
  interpretation_status: "not_started" | "processing" | "ready" | "failed" | string;
  active_jobs: Array<{ id: string; status: string; task_type: string }>;
};

export type FloorsState = {
  project_id: string;
  floors: RoomFloor[];
  selected_floor_id: string | null;
  rooms: Room[];
  suggestions: RoomSuggestion[];
};

export type FloorInterpretationStatus = {
  project_id: string;
  floor_id: string;
  status: "not_started" | "processing" | "ready" | "failed" | string;
  run_id: string | null;
  model: string | null;
  prompt_version: string | null;
  updated_at: string | null;
  room_statuses: Array<{ room_id: string; status: string; warnings: string[] }>;
};

export type AutoFixPreview = {
  room_id: string;
  original: { points: Point[] };
  proposed: { points: Point[] };
  changed: boolean;
  shape_type: string;
  original_vertex_count: number;
  proposed_vertex_count: number;
  area_change_percent: number;
  source: string;
  seed_score: number | null;
  model_overlap: number | null;
  warnings: string[];
};

export type RoomPatch = {
  points?: Point[];
  name?: string | null;
  room_type?: string | null;
  floor_type_code?: string | null;
  floor_finish?: string | null;
  review_status?: RoomStatus;
  manual_area_override_m2?: number | null;
  space_kind?: "internal" | "external" | "circulation" | "void" | null;
  include_in_boq?: boolean;
  open_plan?: boolean;
};
