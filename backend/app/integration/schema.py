INTEGRATION_SCHEMA = r"""
CREATE INDEX IF NOT EXISTS idx_job_runs_claim
  ON job_runs(status, retry_at, created_at, task_type);
CREATE INDEX IF NOT EXISTS idx_job_runs_active_scope
  ON job_runs(project_id, floor_id, category, status, updated_at);
CREATE INDEX IF NOT EXISTS idx_job_runs_lease
  ON job_runs(status, lease_expires_at, attempts, max_attempts);
CREATE INDEX IF NOT EXISTS idx_wall_openings_element_scope
  ON wall_openings(project_id, floor_id, element_id, wall_id);
CREATE INDEX IF NOT EXISTS idx_room_wall_relations_wall_scope
  ON room_wall_relations(project_id, floor_id, wall_id, room_id);
CREATE INDEX IF NOT EXISTS idx_review_items_filter
  ON review_items(project_id, floor_id, entity_type, status, updated_at);
CREATE INDEX IF NOT EXISTS idx_boq_rows_refresh
  ON boq_rows(project_id, boq_id, entity_type, is_stale, updated_at);
CREATE INDEX IF NOT EXISTS idx_outbox_unpublished
  ON outbox_events(published_at, created_at, project_id);
"""
