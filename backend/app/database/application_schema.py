"""General application schema extensions.

These columns and indexes support the project library, dashboard summaries,
organization views, and account activity without depending on PDF processing.
"""

APPLICATION_FOUNDATION_SCHEMA = """
ALTER TABLE projects ADD COLUMN project_number TEXT;
ALTER TABLE projects ADD COLUMN client_name TEXT;
ALTER TABLE projects ADD COLUMN location TEXT;
ALTER TABLE projects ADD COLUMN description TEXT;
ALTER TABLE projects ADD COLUMN archived_at TEXT;

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_updated_at ON projects(updated_at);
CREATE INDEX IF NOT EXISTS idx_projects_org_status ON projects(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_memberships_user_status ON organization_memberships(user_id, status);
CREATE INDEX IF NOT EXISTS idx_memberships_org_status ON organization_memberships(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON notifications(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_org_created ON audit_logs(organization_id, created_at);
CREATE INDEX IF NOT EXISTS idx_billing_history_org_created ON billing_history(organization_id, created_at);
"""

__all__ = ["APPLICATION_FOUNDATION_SCHEMA"]
