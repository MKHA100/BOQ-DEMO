export type UploadDocument = {
  id: string;
  project_id: string;
  document_type: string;
  file_name: string;
  original_file_name: string | null;
  mime_type: string;
  content_hash: string | null;
  size_bytes: number;
  page_count: number | null;
  status: string;
  validation_status: string;
  manifest_status: string;
  ingestion_status: string;
  manifest_version: number;
  is_primary: boolean;
  version: number;
  created_at: string;
  updated_at: string;
};

export type UploadResult = {
  document: UploadDocument;
  reused: boolean;
  duplicate: boolean;
  jobs: Array<Record<string, unknown>>;
  next_step: "floor-plans";
};

export type UploadProgress = {
  loaded: number;
  total: number;
  percent: number;
};
