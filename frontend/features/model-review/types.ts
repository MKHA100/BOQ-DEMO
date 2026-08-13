import type { Point, Rect } from "@/features/drawing/types";

export type ElementType = "door" | "window" | "wall";
export type ReviewStatus = "ready" | "needs_review" | "confirmed";
export type LabelMode = "smart" | "all" | "selected";

export type ElementProperty = {
  id: string;
  property_name: string;
  value: unknown;
  unit: string | null;
  source: string;
  is_confirmed: boolean;
  suggestion_value?: unknown;
};

export type ReviewElement = {
  id: string;
  project_id: string;
  floor_id: string;
  item_number: number;
  display_number: string;
  friendly_number: string | null;
  element_type: ElementType;
  type_code: string | null;
  geometry: Rect & { rotation?: number };
  source: string;
  confidence: number | null;
  status: ReviewStatus;
  excluded: boolean;
  user_confirmed: boolean;
  tag_text: string | null;
  assigned_schedule_entry_id: string | null;
  element_version: number;
  properties: ElementProperty[];
  resolved_data: Record<string, unknown>;
  resolved_sources: Record<string, string>;
  confirmed_fields: Record<string, boolean>;
  missing_fields: string[];
  detail_missing_fields?: string[];
  schedule_match: { id: string; category: string; entity_key: string; source_kind: string; review_state: string } | null;
  drawing_detail: { record_id: string; document_id: string; page_id: string; confidence: number | null; source_location: Record<string, unknown> } | null;
};

export type ReviewFloor = {
  id: string;
  name: string;
  level_index: number;
  crop_version: number;
  scale_version: number;
  element_version: number;
  drawing_url: string | null;
  drawing_width: number;
  drawing_height: number;
  element_count: number;
  needs_review_count: number;
  confirmed_count: number;
  active_jobs: Array<{ id: string; status: string; task_type: string }>;
  detection_status: "not_ready" | "processing" | "results_available" | "ready" | "failed";
  results_available: boolean;
};

export type ScheduleEntry = {
  id: string;
  category: ElementType;
  entity_key: string;
  data: Record<string, unknown>;
  review_state: string;
};

export type ModelReviewState = {
  project_id: string;
  floors: ReviewFloor[];
  selected_floor_id: string | null;
  elements: ReviewElement[];
  schedule_entries: ScheduleEntry[];
};

export type ElementInput = {
  element_type: ElementType;
  geometry: Rect & { rotation?: number };
  type_code?: string | null;
};

export type ElementPatch = {
  geometry?: Rect & { rotation?: number };
  type_code?: string | null;
  review_status?: ReviewStatus;
  excluded?: boolean;
  tag_text?: string | null;
};

export type DrawDraft = { start: Point; end: Point };
