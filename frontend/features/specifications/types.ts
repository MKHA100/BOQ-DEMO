export type SpecificationCategoryKey =
  | "door_schedule"
  | "window_schedule"
  | "wall_schedule"
  | "floor_schedule"
  | "specification"
  | "other";

export type SpecificationStatus = "ready" | "processing" | "needs_review" | "failed" | "skipped";
export type ScopeMode = "all" | "selected";

export type FloorOption = { id: string; name: string; level_index: number };
export type SourceJob = { id: string; task_type: string; status: string; progress: number };
export type ExtractedEntry = {
  id: string;
  category: SpecificationCategoryKey;
  entity_key: string;
  data: Record<string, unknown>;
  confidence: number | null;
  review_state: string;
  is_accepted: boolean;
};

export type SupportingSource = {
  id: string;
  category: SpecificationCategoryKey;
  source_type: "file" | "crop";
  document_id: string;
  file_name: string | null;
  mime_type: string | null;
  file_size: number;
  page_number: number | null;
  crop: Record<string, unknown> | null;
  scope_mode: ScopeMode;
  floor_ids: string[];
  status: SpecificationStatus;
  preview_url: string | null;
  active_job: SourceJob | null;
  entry_count: number;
  entries: ExtractedEntry[];
  created_at: string;
  updated_at: string;
};

export type SpecificationCategory = {
  key: SpecificationCategoryKey;
  label: string;
  description: string;
  status: SpecificationStatus;
  sources: SupportingSource[];
  entry_count: number;
};

export type PageOption = {
  id: string;
  document_id: string;
  page_number: number;
  page_label: string | null;
  width: number | null;
  height: number | null;
  thumbnail_url: string | null;
  preview_url: string | null;
};

export type DocumentOption = {
  id: string;
  file_name: string;
  page_count: number | null;
  is_primary: boolean;
  pages: PageOption[];
};

export type SpecificationsState = {
  project_id: string;
  project_name: string;
  categories: SpecificationCategory[];
  floors: FloorOption[];
  documents: DocumentOption[];
  can_continue: boolean;
  updated_at: string;
};

export type CropRect = { x: number; y: number; width: number; height: number };

export type CropSourcePayload = {
  category: SpecificationCategoryKey;
  replace_source_id?: string;
  document_id: string;
  document_page_id: string;
  page_number: number;
  original_page_width: number;
  original_page_height: number;
  crop: CropRect;
  scope_mode: ScopeMode;
  floor_ids: string[];
};
