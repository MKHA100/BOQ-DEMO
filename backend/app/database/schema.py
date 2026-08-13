"""Schema compatibility helpers.

The active schema is still centralized in app.database.session.SCHEMA so SQLite
and Neon/PostgreSQL initialization stay in one place. This module exists for
feature code/tests that need to import a stable schema object.
"""

from app.database.session import SCHEMA

__all__ = ["SCHEMA"]
