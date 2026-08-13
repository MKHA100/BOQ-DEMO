from app.database.session import get_connection, row_to_dict


class PlatformRepository:
    def list_rows(self, table: str, order_by: str = "created_at DESC") -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()
        return [row_to_dict(row) for row in rows]

    def get_row(self, table: str, row_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
        return row_to_dict(row)

    def execute(self, query: str, params: tuple = ()) -> None:
        with get_connection() as connection:
            connection.execute(query, params)

    def fetch_one(self, query: str, params: tuple = ()) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(query, params).fetchone()
        return row_to_dict(row)

    def fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [row_to_dict(row) for row in rows]


platform_repository = PlatformRepository()
