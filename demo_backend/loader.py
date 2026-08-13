from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from threading import Lock


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "mattegoda"
FIXTURE_PATH = FIXTURE_ROOT / "fixture.json"
ASSET_ROOT = FIXTURE_ROOT

_lock = Lock()
_mtime_ns = -1
_fixture: dict = {}


def load_fixture() -> dict:
    """Load a fresh copy and hot-reload fixture edits without restarting FastAPI."""
    global _fixture, _mtime_ns
    if not FIXTURE_PATH.exists():
        return {}
    modified = FIXTURE_PATH.stat().st_mtime_ns
    with _lock:
        if modified != _mtime_ns:
            parsed = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("Demo fixture root must be an object.")
            _fixture = parsed
            _mtime_ns = modified
        return deepcopy(_fixture)


def asset_path(name: str) -> Path | None:
    candidate = (ASSET_ROOT / name).resolve()
    root = ASSET_ROOT.resolve()
    if candidate != root and root in candidate.parents and candidate.is_file():
        return candidate
    return None
