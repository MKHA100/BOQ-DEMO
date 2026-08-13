from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database.session import init_db
from app.model_review.cleanup_service import detection_cleanup_service


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Supersede duplicate generated floor detections safely and rebuild affected derived data"
    )
    parser.add_argument("project_id")
    parser.add_argument("--floor-id", default=None)
    parser.add_argument("--no-rebuild", action="store_true", help="Only supersede duplicates; do not queue wall/room rebuilds")
    args = parser.parse_args()
    init_db()
    result = detection_cleanup_service.repair_project(
        args.project_id,
        args.floor_id,
        enqueue_rebuild=not args.no_rebuild,
    )
    print(
        "Detection cleanup complete: "
        f"kept={result['kept']} superseded={result['superseded']} "
        f"affected_floors={len(result['affected_floors'])} queued_jobs={len(result['jobs'])}"
    )


if __name__ == "__main__":
    main()
