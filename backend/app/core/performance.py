from __future__ import annotations

import time
from contextvars import ContextVar
from uuid import uuid4

from fastapi import Request, Response

_query_counter: ContextVar[dict[str, int] | None] = ContextVar("autoboq_query_counter", default=None)


def reset_query_count() -> None:
    _query_counter.set({"count": 0})


def increment_query_count() -> None:
    counter = _query_counter.get()
    if counter is not None:
        counter["count"] += 1


def current_query_count() -> int:
    counter = _query_counter.get()
    return int(counter["count"]) if counter is not None else 0


async def add_performance_headers(request: Request, call_next) -> Response:
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    reset_query_count()
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    query_count = current_query_count()
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    response.headers["X-DB-Query-Count"] = str(query_count)
    response.headers["Server-Timing"] = f'app;dur={elapsed_ms:.2f}, db;desc="{query_count} queries"'
    return response
