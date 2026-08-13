export type WorkflowStatus = "ready" | "results_available" | "processing" | "needs_review" | "confirmed" | "failed" | "not_ready";

export type Rect = { x: number; y: number; width: number; height: number };

export type FloorPlanJob = {
  id: string;
  floor_id: string | null;
  task_type: string;
  status: string;
  progress: number;
};

export type FloorPlanPage = {
  id: string;
  document_id: string;
  page_number: number;
  page_label: string | null;
  width: number | null;
  height: number | null;
  rotation: number;
  thumbnail_status: string;
  preview_status: string;
  thumbnail_url: string | null;
  preview_url: string | null;
};

export type FloorPlanDocument = {
  id: string;
  project_id: string;
  document_type: "source" | "floor_source" | string;
  file_name: string;
  mime_type: string;
  page_count: number | null;
  status: WorkflowStatus | string;
  is_primary: boolean;
  pages: FloorPlanPage[];
};

export type FloorCrop = {
  id: string;
  project_id: string;
  floor_id: string;
  document_id: string;
  document_page_id: string;
  source_page_number: number;
  original_page_width: number;
  original_page_height: number;
  rotation: 0 | 90 | 180 | 270;
  render_dpi: number;
  coordinates: {
    original_rect?: Rect;
    normalized_display_rect?: Rect;
    coordinate_space?: string;
  };
  crop_version: number;
  status: WorkflowStatus | string;
  crop_asset_url: string | null;
  preview_asset_url: string | null;
  created_at: string;
  updated_at: string;
};

export type FloorPlanFloor = {
  id: string;
  project_id: string;
  name: string;
  level_index: number;
  status: WorkflowStatus | string;
  uses_default_height: boolean;
  wall_height_mm: number | null;
  effective_wall_height_mm: number;
  is_custom_name: boolean;
  source_document_id: string | null;
  source_page_number: number | null;
  source_rotation: 0 | 90 | 180 | 270;
  crop_version: number;
  crop: FloorCrop | null;
  last_error: string | null;
  active_jobs: FloorPlanJob[];
  created_at: string;
  updated_at: string;
};

export type FloorPlansState = {
  project_id: string;
  project_name: string;
  default_wall_height_mm: number;
  measurement_unit: "mm" | "cm" | "m" | "in" | "ft" | string;
  floors: FloorPlanFloor[];
  documents: FloorPlanDocument[];
  can_continue: boolean;
  updated_at: string;
};

export type FloorCropSaveInput = {
  document_id: string;
  document_page_id: string;
  source_page_number: number;
  original_page_width: number;
  original_page_height: number;
  rotation: 0 | 90 | 180 | 270;
  render_dpi: number;
  original_rect: Rect;
  normalized_display_rect: Rect;
};

export type FloorSourceUploadResult = {
  document: FloorPlanDocument;
  reused: boolean;
  duplicate: boolean;
  jobs: Array<Record<string, unknown>>;
};

export type FloorCropSaveResult = {
  crop: FloorCrop;
  jobs: FloorPlanJob[];
  source_changed: boolean;
  unchanged?: boolean;
};
