from contextlib import contextmanager
import re
import sqlite3
from typing import Any, Iterable
from app.core.config import settings
from app.database.migrations import run_migrations
from app.core.performance import increment_query_count

try:
    import psycopg
except Exception:
    psycopg = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
  full_name TEXT, role TEXT NOT NULL DEFAULT 'member', status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_sessions (
  token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS subscription_plans (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE, price_monthly REAL NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'USD', user_limit INTEGER NOT NULL DEFAULT 5, project_limit INTEGER NOT NULL DEFAULT 10,
  storage_limit_mb INTEGER NOT NULL DEFAULT 1024, export_limit_monthly INTEGER NOT NULL DEFAULT 100,
  ai_credit_limit_monthly INTEGER NOT NULL DEFAULT 1000, features_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS organizations (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'active', plan_id TEXT,
  storage_limit_mb INTEGER NOT NULL DEFAULT 1024, project_limit INTEGER NOT NULL DEFAULT 10, user_limit INTEGER NOT NULL DEFAULT 5,
  export_limit_monthly INTEGER NOT NULL DEFAULT 100, ai_credit_limit_monthly INTEGER NOT NULL DEFAULT 1000,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(plan_id) REFERENCES subscription_plans(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS organization_memberships (
  id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, user_id TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'member',
  status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(organization_id, user_id), FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS subscriptions (
  id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, plan_id TEXT, status TEXT NOT NULL DEFAULT 'active', provider TEXT NOT NULL DEFAULT 'manual',
  current_period_start TEXT, current_period_end TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE, FOREIGN KEY(plan_id) REFERENCES subscription_plans(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS billing_history (
  id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, subscription_id TEXT, provider TEXT NOT NULL DEFAULT 'manual',
  invoice_number TEXT, amount REAL NOT NULL DEFAULT 0, currency TEXT NOT NULL DEFAULT 'USD', status TEXT NOT NULL DEFAULT 'recorded',
  period_start TEXT, period_end TEXT, file_path TEXT, created_at TEXT NOT NULL,
  FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE, FOREIGN KEY(subscription_id) REFERENCES subscriptions(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS user_invitations (
  id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, email TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'member', token_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending', invited_by TEXT, expires_at TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE, FOREIGN KEY(invited_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS user_profiles (
  user_id TEXT PRIMARY KEY, full_name TEXT, phone TEXT, job_title TEXT, timezone TEXT, updated_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS account_settings (
  user_id TEXT PRIMARY KEY, settings_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS organization_settings (
  organization_id TEXT PRIMARY KEY, settings_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL,
  FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS usage_counters (
  id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, period_key TEXT NOT NULL, projects_created INTEGER NOT NULL DEFAULT 0,
  storage_used_mb REAL NOT NULL DEFAULT 0, exports_generated INTEGER NOT NULL DEFAULT 0, ai_credits_used INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL, UNIQUE(organization_id, period_key), FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS audit_logs (
  id TEXT PRIMARY KEY, organization_id TEXT, user_id TEXT, action TEXT NOT NULL, entity_type TEXT, entity_id TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
  FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE SET NULL, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS notifications (
  id TEXT PRIMARY KEY, organization_id TEXT, user_id TEXT, channel TEXT NOT NULL DEFAULT 'email', recipient TEXT, subject TEXT, body TEXT,
  status TEXT NOT NULL DEFAULT 'queued', created_at TEXT NOT NULL,
  FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE SET NULL, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, token_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS payment_webhook_events (
  id TEXT PRIMARY KEY, provider TEXT NOT NULL, event_type TEXT NOT NULL, event_id TEXT, payload_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, user_id TEXT, organization_id TEXT, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL, FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_organization ON projects(organization_id);
"""

class HybridRow:
    def __init__(self, columns: list[str], values: tuple[Any, ...]):
        self._data = dict(zip(columns, values))
        self._values = values
    def __getitem__(self, key: str | int) -> Any:
        return self._data[key] if isinstance(key, str) else self._values[key]
    def __iter__(self):
        return iter(self._data)
    def keys(self):
        return self._data.keys()

class CursorResult:
    def __init__(self, columns: list[str], rows: list[tuple[Any, ...]], rowcount: int = 0):
        self._columns, self._rows, self.rowcount = columns, rows, rowcount
    def fetchone(self):
        return HybridRow(self._columns, self._rows[0]) if self._rows else None
    def fetchall(self):
        return [HybridRow(self._columns, row) for row in self._rows]

class PostgresConnectionAdapter:
    dialect = "postgres"
    def __init__(self, database_url: str):
        if psycopg is None: raise RuntimeError("psycopg is required for PostgreSQL")
        self._connection = psycopg.connect(database_url)
    def _convert(self, query: str) -> str:
        return re.sub(r"%(?![%sbt])", "%%", query.replace("?", "%s"))
    def execute(self, query: str, params: Iterable[Any] | None = None):
        increment_query_count()
        with self._connection.cursor() as cursor:
            cursor.execute(self._convert(query), tuple(params or ()))
            columns = [column.name for column in cursor.description] if cursor.description else []
            rows = cursor.fetchall() if cursor.description else []
            return CursorResult(columns, rows, cursor.rowcount)
    def executemany(self, query: str, params_seq: Iterable[Iterable[Any]]):
        increment_query_count()
        with self._connection.cursor() as cursor:
            cursor.executemany(self._convert(query), [tuple(params) for params in params_seq])
            return CursorResult([], [], cursor.rowcount)
    def executescript(self, script: str):
        cleaned = re.sub(r"PRAGMA[^;]+;", "", script, flags=re.I)
        with self._connection.cursor() as cursor:
            for statement in [part.strip() for part in cleaned.split(";") if part.strip()]:
                increment_query_count()
                cursor.execute(statement)
    def commit(self): self._connection.commit()
    def rollback(self): self._connection.rollback()
    def close(self): self._connection.close()


def _seed_platform_defaults(connection: Any) -> None:
    from datetime import datetime, timezone
    from uuid import uuid4
    import json
    now = datetime.now(timezone.utc).isoformat()
    defaults = [
      ("starter", "Starter", 0, 5, 10, 1024, 100, 1000, ["Project management", "Team access", "Local development"]),
      ("professional", "Professional", 49, 25, 100, 10240, 1000, 10000, ["Project management", "Organization controls", "Production storage"]),
    ]
    for slug, name, price, users, projects, storage, exports, credits, features in defaults:
        if connection.execute("SELECT id FROM subscription_plans WHERE slug = ?", (slug,)).fetchone(): continue
        connection.execute("""INSERT INTO subscription_plans
          (id,name,slug,price_monthly,currency,user_limit,project_limit,storage_limit_mb,export_limit_monthly,ai_credit_limit_monthly,features_json,status,created_at,updated_at)
          VALUES (?,?,?,?, 'USD',?,?,?,?,?,?, 'active',?,?)""",
          (str(uuid4()),name,slug,price,users,projects,storage,exports,credits,json.dumps(features),now,now))


def _sync_super_admin(connection: Any) -> None:
    if not settings.sync_super_admin_on_startup or not settings.super_admin_email or not settings.super_admin_password: return
    from datetime import datetime, timezone
    from uuid import uuid4
    from app.auth.passwords import hash_password
    now = datetime.now(timezone.utc).isoformat(); email = settings.super_admin_email.strip().lower()
    org = connection.execute("SELECT id FROM organizations WHERE slug = 'platform'").fetchone()
    organization_id = org[0] if org else str(uuid4())
    if not org:
        connection.execute("""INSERT INTO organizations
          (id,name,slug,status,storage_limit_mb,project_limit,user_limit,export_limit_monthly,ai_credit_limit_monthly,created_at,updated_at)
          VALUES (?, 'Platform', 'platform', 'active', 10240,1000,100,10000,100000,?,?)""", (organization_id,now,now))
    user = connection.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone(); user_id = user[0] if user else str(uuid4())
    if user:
        connection.execute("UPDATE users SET password_hash=?, full_name=?, role='super_admin', status='active', updated_at=? WHERE id=?",
          (hash_password(settings.super_admin_password), settings.super_admin_name, now, user_id))
    else:
        connection.execute("INSERT INTO users (id,email,password_hash,full_name,role,status,created_at,updated_at) VALUES (?,?,?,?, 'super_admin','active',?,?)",
          (user_id,email,hash_password(settings.super_admin_password),settings.super_admin_name,now,now))
    membership = connection.execute("SELECT id FROM organization_memberships WHERE organization_id=? AND user_id=?", (organization_id,user_id)).fetchone()
    if not membership:
        connection.execute("INSERT INTO organization_memberships (id,organization_id,user_id,role,status,created_at,updated_at) VALUES (?,?,?,'super_admin','active',?,?)",
          (str(uuid4()),organization_id,user_id,now,now))


def _configure_sqlite(connection: sqlite3.Connection, *, initialize: bool = False) -> sqlite3.Connection:
    timeout_ms = max(5, int(settings.sqlite_busy_timeout_seconds)) * 1000
    connection.execute(f"PRAGMA busy_timeout = {timeout_ms}")
    connection.execute("PRAGMA foreign_keys = ON")
    if initialize:
        # WAL permits API readers while the background worker commits results.
        # journal_mode is persistent for the SQLite database file.
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    if settings.use_postgres:
        connection = PostgresConnectionAdapter(settings.database_url or "")
        try:
            connection.executescript(SCHEMA); run_migrations(connection); _seed_platform_defaults(connection); _sync_super_admin(connection); connection.commit()
        finally: connection.close()
    else:
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(
            settings.database_path, timeout=float(settings.sqlite_busy_timeout_seconds)
        ) as connection:
            _configure_sqlite(connection, initialize=True)
            connection.executescript(SCHEMA)
            run_migrations(connection); _seed_platform_defaults(connection); _sync_super_admin(connection); connection.commit()

@contextmanager
def get_connection():
    if settings.use_postgres:
        connection = PostgresConnectionAdapter(settings.database_url or "")
        try:
            yield connection; connection.commit()
        except Exception:
            connection.rollback(); raise
        finally: connection.close()
    else:
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            settings.database_path, timeout=float(settings.sqlite_busy_timeout_seconds)
        )
        _configure_sqlite(connection)
        connection.set_trace_callback(lambda _statement: increment_query_count())
        try:
            yield connection; connection.commit()
        except Exception:
            connection.rollback(); raise
        finally: connection.close()

def row_to_dict(row: Any | None) -> dict | None:
    return dict(row) if row is not None else None
