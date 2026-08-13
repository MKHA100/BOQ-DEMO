export type ReviewItem = {
  id: string;
  project_id: string;
  floor_id: string;
  entity_type: "door" | "window" | "wall" | "floor";
  entity_id: string;
  display_number: string | null;
  title: string;
  data: Record<string, unknown>;
  status: "ready" | "needs_review" | "confirmed";
  critical: boolean;
  is_stale: boolean;
  source_version: number;
  review_version: number;
};
export type ReviewFloorSummary = { id: string; name: string; level_index: number; total: number; confirmed: number; ready: number; needs_review: number };
export type ReviewState = {
  project_id: string;
  floors: ReviewFloorSummary[];
  counts: Record<string, number>;
  items: ReviewItem[];
  stale?: boolean;
  active_jobs?: Array<{ id: string; task_type: string; status: string }>;
};
