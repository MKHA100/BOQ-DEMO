"""Copy retained application tables from a clean local SQLite database to PostgreSQL."""
from __future__ import annotations
import os, sqlite3
from pathlib import Path
from app.core.config import settings
from app.database.session import PostgresConnectionAdapter

RETAINED_TABLES = (
    "subscription_plans", "organizations", "users", "auth_sessions",
    "organization_memberships", "subscriptions", "billing_history",
    "user_invitations", "user_profiles", "account_settings",
    "organization_settings", "usage_counters", "audit_logs", "notifications",
    "password_reset_tokens", "payment_webhook_events", "projects",
)

def migrate() -> None:
    sqlite_path = Path(os.getenv("DATABASE_PATH", str(settings.database_path)))
    postgres_url = os.getenv("DIRECT_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not sqlite_path.exists(): raise SystemExit(f"SQLite database not found: {sqlite_path}")
    if not postgres_url: raise SystemExit("Set DIRECT_DATABASE_URL or DATABASE_URL.")
    source = sqlite3.connect(sqlite_path); source.row_factory = sqlite3.Row
    target = PostgresConnectionAdapter(postgres_url)
    try:
        for table in RETAINED_TABLES:
            exists = source.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
            if not exists: continue
            columns = [row[1] for row in source.execute(f"PRAGMA table_info({table})").fetchall()]
            rows = source.execute(f"SELECT * FROM {table}").fetchall()
            placeholders = ", ".join("?" for _ in columns)
            target.executemany(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                [tuple(row[column] for column in columns) for row in rows],
            )
            print(f"{table}: copied {len(rows)} rows")
        target.commit()
    except Exception:
        target.rollback(); raise
    finally:
        source.close(); target.close()

if __name__ == "__main__": migrate()
