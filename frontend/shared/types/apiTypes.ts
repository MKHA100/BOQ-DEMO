export type ProjectStatus = "active" | "on_hold" | "completed" | "archived";

export type ProjectResponse = {
  id: string;
  name: string;
  status: ProjectStatus;
  project_number?: string | null;
  client_name?: string | null;
  location?: string | null;
  description?: string | null;
  organization_id?: string | null;
  organization_name?: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectListItem = ProjectResponse;

export type ProjectListResponse = {
  projects: ProjectListItem[];
  total: number;
  limit: number;
  offset: number;
};

export type ProjectCreateInput = {
  name: string;
  project_number?: string | null;
  client_name?: string | null;
  location?: string | null;
  description?: string | null;
};

export type ProjectUpdateInput = Partial<ProjectCreateInput> & {
  status?: ProjectStatus;
};

export type ProjectCreateResponse = ProjectResponse & {
  project_id: string;
};
