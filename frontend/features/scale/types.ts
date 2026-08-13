import type { Point } from "@/features/drawing/types";

export type ScaleStatus = "not_calibrated" | "in_progress" | "calibrated" | "needs_review" | "failed";

export type Calibration = {
  id: string;
  point_a: Point;
  point_b: Point;
  pixel_distance: number;
  real_distance_mm: number;
  mm_per_pixel: number;
  verification_points: { point_a: Point; point_b: Point } | null;
  verification_expected_mm: number | null;
  verification_measured_mm: number | null;
  verification_difference_percent: number | null;
  input_unit: "mm" | "cm" | "m" | "ft_in";
  crop_version: number;
  scale_version: number;
  status: "calibrated" | "needs_review";
};

export type DimensionSuggestion = {
  id: string;
  label_text: string;
  display_scale?: string;
  value_mm: number;
  point_a: Point;
  point_b: Point;
  confidence: number;
  suggested_mm_per_pixel: number;
};

export type ScaleFloor = {
  id: string;
  project_id: string;
  name: string;
  level_index: number;
  crop_version: number;
  scale_version: number;
  source_document_id: string | null;
  source_page_number: number | null;
  original_page_width: number | null;
  original_page_height: number | null;
  rotation: number;
  drawing_url: string | null;
  status: ScaleStatus;
  calibration: Calibration | null;
  dimension_suggestions: DimensionSuggestion[];
};

export type ScaleState = {
  project_id: string;
  project_name: string;
  floors: ScaleFloor[];
  can_continue: boolean;
};

export type CalibrationInput = {
  point_a: Point;
  point_b: Point;
  real_distance?: number;
  unit: "mm" | "cm" | "m" | "ft_in";
  feet?: number;
  inches?: number;
  crop_version: number;
  verification?: {
    point_a: Point;
    point_b: Point;
    expected_distance?: number;
    unit: "mm" | "cm" | "m" | "ft_in";
    feet?: number;
    inches?: number;
  };
};
