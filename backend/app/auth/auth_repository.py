from app.database.session import get_connection, row_to_dict


class AuthRepository:
    def create_user(self, user: dict) -> dict:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO users (id, email, password_hash, full_name, role, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user["id"], user["email"], user["password_hash"], user.get("full_name"), user.get("role", "member"), user.get("status", "active"), user["created_at"], user["updated_at"]),
            )
        return user

    def get_user_by_email(self, email: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        return row_to_dict(row)

    def get_user_by_id(self, user_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return row_to_dict(row)

    def create_session(self, token_hash: str, user_id: str, created_at: str, expires_at: str) -> None:
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO auth_sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (token_hash, user_id, created_at, expires_at),
            )

    def get_session_user(self, token_hash: str, now: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT users.id, users.email, users.full_name, users.role, users.status, users.created_at,
                       organizations.id AS organization_id, organizations.name AS organization_name
                FROM auth_sessions
                JOIN users ON users.id = auth_sessions.user_id
                LEFT JOIN organization_memberships ON organization_memberships.user_id = users.id AND organization_memberships.status = 'active'
                LEFT JOIN organizations ON organizations.id = organization_memberships.organization_id
                WHERE auth_sessions.token_hash = ? AND auth_sessions.expires_at > ?
                ORDER BY organizations.created_at ASC
                LIMIT 1
                """,
                (token_hash, now),
            ).fetchone()
        return row_to_dict(row)

    def delete_session(self, token_hash: str) -> None:
        with get_connection() as connection:
            connection.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))
