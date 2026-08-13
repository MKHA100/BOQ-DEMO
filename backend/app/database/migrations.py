from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.database.application_schema import APPLICATION_FOUNDATION_SCHEMA
from app.workflow.schema import WORKFLOW_SCHEMA
from app.pdf_upload.schema import PDF_UPLOAD_SCHEMA
from app.floor_plans.schema import FLOOR_PLANS_SCHEMA
from app.specifications.schema import SPECIFICATIONS_SCHEMA
from app.scale.schema import SCALE_SCHEMA
from app.model_review.schema import MODEL_REVIEW_SCHEMA
from app.model_review.versioned_detection_schema import (
    VERSIONED_DETECTION_MIGRATION_VERSION,
    VERSIONED_DETECTION_TABLES_SQL,
    ELEMENT_DETECTION_COLUMNS,
    WALL_DETECTION_COLUMNS,
    ROOM_DETECTION_COLUMNS,
)
from app.walls.schema import WALLS_SCHEMA
from app.floors.schema import FLOORS_SCHEMA
from app.floors.hybrid_schema import (
    HYBRID_FLOOR_MIGRATION_VERSION,
    HYBRID_FLOOR_TABLES_SQL,
    ROOM_COLUMNS,
    ROOM_SUGGESTION_COLUMNS,
)
from app.floors.accuracy_schema import (
    FLOOR_ACCURACY_MIGRATION_VERSION,
    FLOOR_ACCURACY_TABLES_SQL,
    ROOM_ACCURACY_COLUMNS,
)
from app.floors.precision_schema import (
    FLOOR_INTERPRETATION_MIGRATION_VERSION,
    FLOOR_INTERPRETATION_TABLES_SQL,
    FLOOR_PRECISION_MIGRATION_VERSION,
    FLOOR_PRECISION_TABLES_SQL,
    ROOM_INTERPRETATION_COLUMNS,
    ROOM_PRECISION_COLUMNS,
)
from app.review.schema import REVIEW_SCHEMA
from app.boq.schema import BOQ_SCHEMA
from app.boq.formal_schema import FORMAL_BOQ_TABLES_SQL
from app.integration.schema import INTEGRATION_SCHEMA

ITEM_NUMBER_MIGRATION_VERSION = "20260715_013_model_review_item_numbers"
FORMAL_BOQ_MIGRATION_VERSION = "20260715_014_formal_boq_templates_exports"

MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("20260713_001_workflow_foundation", WORKFLOW_SCHEMA),
    ("20260713_002_application_foundation", APPLICATION_FOUNDATION_SCHEMA),
    ("20260713_003_pdf_upload_ingestion", PDF_UPLOAD_SCHEMA),
    ("20260713_004_floor_plans", FLOOR_PLANS_SCHEMA),
    ("20260713_005_schedules_specifications", SPECIFICATIONS_SCHEMA),
    ("20260713_006_scale", SCALE_SCHEMA),
    ("20260713_007_model_review", MODEL_REVIEW_SCHEMA),
    ("20260713_008_walls", WALLS_SCHEMA),
    ("20260713_009_floors", FLOORS_SCHEMA),
    ("20260713_010_review", REVIEW_SCHEMA),
    ("20260713_011_boq", BOQ_SCHEMA),
    ("20260713_012_integration_qa", INTEGRATION_SCHEMA),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()




def _row_value(row: Any, key: str, index: int) -> Any:
    """Read a query result from sqlite tuples, sqlite.Row, or Postgres HybridRow."""
    if hasattr(row, "keys"):
        return row[key]
    return row[index]


def _column_exists(connection: Any, table_name: str, column_name: str) -> bool:
    if getattr(connection, "dialect", None) == "postgres":
        return (
            connection.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = ?
                  AND column_name = ?
                """,
                (table_name, column_name),
            ).fetchone()
            is not None
        )

    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    for row in rows:
        name = _row_value(row, "name", 1)
        if name == column_name:
            return True
    return False


def _add_column_if_missing(
    connection: Any,
    table_name: str,
    column_name: str,
    sql_type: str,
) -> None:
    if _column_exists(connection, table_name, column_name):
        return
    connection.execute(
        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sql_type}"
    )


def _ensure_item_number_columns(connection: Any) -> None:
    _add_column_if_missing(connection, "elements", "item_number", "INTEGER")
    _add_column_if_missing(connection, "walls", "source_element_id", "TEXT")
    _add_column_if_missing(connection, "walls", "item_number", "INTEGER")


def _ensure_item_number_indexes(connection: Any) -> None:
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_elements_project_item_number
        ON elements(project_id, item_number)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_elements_project_type_item
        ON elements(project_id, element_type, item_number)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_walls_project_item_number
        ON walls(project_id, item_number)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_walls_source_element
        ON walls(project_id, floor_id, source_element_id)
        """
    )


def _backfill_element_item_numbers(connection: Any) -> None:
    projects = connection.execute(
        "SELECT DISTINCT project_id FROM elements ORDER BY project_id"
    ).fetchall()
    for project in projects:
        project_id = _row_value(project, "project_id", 0)
        rows = connection.execute(
            "SELECT id, item_number FROM elements WHERE project_id=? ORDER BY created_at, id",
            (project_id,),
        ).fetchall()
        used: set[int] = set()
        next_number = 1
        for row in rows:
            raw = _row_value(row, "item_number", 1)
            number = int(raw) if raw is not None else None
            if number is not None and number > 0 and number not in used:
                used.add(number)
                next_number = max(next_number, number + 1)
                continue
            while next_number in used:
                next_number += 1
            connection.execute(
                "UPDATE elements SET item_number=? WHERE id=?",
                (next_number, _row_value(row, "id", 0)),
            )
            used.add(next_number)
            next_number += 1


def _backfill_wall_item_numbers(connection: Any) -> None:
    projects = connection.execute(
        "SELECT DISTINCT project_id FROM walls ORDER BY project_id"
    ).fetchall()
    for project in projects:
        project_id = _row_value(project, "project_id", 0)
        element_rows = connection.execute(
            """
            SELECT id, floor_id, item_number
            FROM elements
            WHERE project_id=? AND element_type='wall'
            ORDER BY floor_id, item_number, created_at, id
            """,
            (project_id,),
        ).fetchall()
        elements_by_floor: dict[str, list[Any]] = {}
        for row in element_rows:
            elements_by_floor.setdefault(_row_value(row, "floor_id", 1), []).append(row)

        wall_rows = connection.execute(
            """
            SELECT id, floor_id, source_element_id, item_number
            FROM walls
            WHERE project_id=?
            ORDER BY floor_id, created_at, id
            """,
            (project_id,),
        ).fetchall()
        walls_by_floor: dict[str, list[Any]] = {}
        for row in wall_rows:
            walls_by_floor.setdefault(_row_value(row, "floor_id", 1), []).append(row)

        max_element = connection.execute(
            "SELECT COALESCE(MAX(item_number), 0) AS maximum FROM elements WHERE project_id=?",
            (project_id,),
        ).fetchone()
        max_element = _row_value(max_element, "maximum", 0)
        next_number = int(max_element or 0) + 1
        used_wall_numbers: set[int] = set()

        for floor_id, walls in walls_by_floor.items():
            candidates = elements_by_floor.get(floor_id, [])
            for index, wall in enumerate(walls):
                wall_item_number = _row_value(wall, "item_number", 3)
                current = int(wall_item_number) if wall_item_number is not None else None
                if current is not None and current > 0 and current not in used_wall_numbers:
                    used_wall_numbers.add(current)
                    continue

                source = None
                wall_source_element_id = _row_value(wall, "source_element_id", 2)
                if wall_source_element_id:
                    source = next(
                        (item for item in candidates if _row_value(item, "id", 0) == wall_source_element_id),
                        None,
                    )
                if source is None and index < len(candidates):
                    source = candidates[index]

                if source is not None and _row_value(source, "item_number", 2) is not None:
                    number = int(_row_value(source, "item_number", 2))
                    source_id = _row_value(source, "id", 0)
                else:
                    while next_number in used_wall_numbers:
                        next_number += 1
                    number = next_number
                    source_id = wall_source_element_id
                    next_number += 1

                if number in used_wall_numbers:
                    while next_number in used_wall_numbers:
                        next_number += 1
                    number = next_number
                    next_number += 1

                connection.execute(
                    "UPDATE walls SET item_number=?, source_element_id=COALESCE(source_element_id, ?) WHERE id=?",
                    (number, source_id, _row_value(wall, "id", 0)),
                )
                used_wall_numbers.add(number)


def _apply_item_number_migration(connection: Any) -> None:
    # This migration is intentionally idempotent because SQLite can persist the
    # first ALTER TABLE from a failed executescript without recording the
    # migration version.
    _ensure_item_number_columns(connection)
    _backfill_element_item_numbers(connection)
    _backfill_wall_item_numbers(connection)
    _ensure_item_number_indexes(connection)

    if not connection.execute(
        "SELECT version FROM schema_migrations WHERE version = ?",
        (ITEM_NUMBER_MIGRATION_VERSION,),
    ).fetchone():
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (ITEM_NUMBER_MIGRATION_VERSION, _now()),
        )



def _apply_formal_boq_migration(connection: Any) -> None:
    """Install the formal BOQ/template/export schema safely on fresh or existing DBs."""
    connection.executescript(FORMAL_BOQ_TABLES_SQL)

    for table_name, columns in {
        "boq_templates": (
            ("description", "TEXT"),
            ("category", "TEXT NOT NULL DEFAULT 'custom'"),
            ("is_builtin", "INTEGER NOT NULL DEFAULT 0"),
            ("is_active", "INTEGER NOT NULL DEFAULT 1"),
        ),
        "boqs": (
            ("setup_version", "INTEGER NOT NULL DEFAULT 1"),
            ("report_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("report_hash", "TEXT"),
            ("currency", "TEXT NOT NULL DEFAULT 'Rs'"),
            ("vat_percentage", "REAL NOT NULL DEFAULT 0"),
        ),
        "boq_rows": (
            ("bill_no", "TEXT"),
            ("bill_name", "TEXT"),
            ("subcategory_code", "TEXT"),
            ("subcategory_name", "TEXT"),
            ("boq_item_number", "TEXT"),
            ("protected_rate", "INTEGER NOT NULL DEFAULT 0"),
        ),
        "export_files": (
            ("setup_version", "INTEGER NOT NULL DEFAULT 1"),
            ("report_hash", "TEXT"),
        ),
    }.items():
        for column_name, sql_type in columns:
            _add_column_if_missing(connection, table_name, column_name, sql_type)

    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_boq_rows_bill ON boq_rows(boq_id, bill_no, subcategory_code, sort_order)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_exports_report ON export_files(project_id, report_hash, setup_version, status)"
    )

    if not connection.execute(
        "SELECT version FROM schema_migrations WHERE version = ?",
        (FORMAL_BOQ_MIGRATION_VERSION,),
    ).fetchone():
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (FORMAL_BOQ_MIGRATION_VERSION, _now()),
        )



def _apply_hybrid_floor_migration(connection: Any) -> None:
    """Install hybrid room analysis storage safely on every supported database."""
    for column_name, sql_type in ROOM_COLUMNS:
        _add_column_if_missing(connection, "rooms", column_name, sql_type)

    connection.executescript(HYBRID_FLOOR_TABLES_SQL)
    for column_name, sql_type in ROOM_SUGGESTION_COLUMNS:
        _add_column_if_missing(connection, "room_suggestions", column_name, sql_type)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_rooms_geometry_hash ON rooms(project_id, floor_id, geometry_hash)"
    )

    if not connection.execute(
        "SELECT version FROM schema_migrations WHERE version = ?",
        (HYBRID_FLOOR_MIGRATION_VERSION,),
    ).fetchone():
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (HYBRID_FLOOR_MIGRATION_VERSION, _now()),
        )

def _apply_floor_accuracy_migration(connection: Any) -> None:
    """Install dimension evidence, semantic room types and finish zones safely."""
    for column_name, sql_type in ROOM_ACCURACY_COLUMNS:
        _add_column_if_missing(connection, "rooms", column_name, sql_type)
    connection.executescript(FLOOR_ACCURACY_TABLES_SQL)
    if not connection.execute(
        "SELECT version FROM schema_migrations WHERE version = ?",
        (FLOOR_ACCURACY_MIGRATION_VERSION,),
    ).fetchone():
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (FLOOR_ACCURACY_MIGRATION_VERSION, _now()),
        )



def _apply_floor_precision_migration(connection: Any) -> None:
    """Install precision room geometry and editor history safely."""
    for column_name, sql_type in ROOM_PRECISION_COLUMNS:
        _add_column_if_missing(connection, "rooms", column_name, sql_type)
    connection.executescript(FLOOR_PRECISION_TABLES_SQL)
    # Backfill the three geometry stages from the current canonical geometry.
    connection.execute(
        """
        UPDATE rooms
        SET raw_geometry_json=CASE WHEN COALESCE(raw_geometry_json,'{}')='{}' THEN geometry_json ELSE raw_geometry_json END,
            regularized_geometry_json=CASE WHEN COALESCE(regularized_geometry_json,'{}')='{}' THEN geometry_json ELSE regularized_geometry_json END,
            confirmed_geometry_json=CASE WHEN COALESCE(confirmed_geometry_json,'{}')='{}' THEN geometry_json ELSE confirmed_geometry_json END,
            precision_status=CASE WHEN COALESCE(precision_status,'pending')='pending' THEN 'needs_review' ELSE precision_status END,
            boundary_source=CASE WHEN COALESCE(boundary_source,'unknown')='unknown' THEN COALESCE(detection_source,'unknown') ELSE boundary_source END
        """
    )
    if not connection.execute(
        "SELECT version FROM schema_migrations WHERE version = ?",
        (FLOOR_PRECISION_MIGRATION_VERSION,),
    ).fetchone():
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (FLOOR_PRECISION_MIGRATION_VERSION, _now()),
        )


def _apply_floor_interpretation_migration(connection: Any) -> None:
    """Install reusable floor-level room interpretation storage idempotently."""
    for column_name, sql_type in ROOM_INTERPRETATION_COLUMNS:
        _add_column_if_missing(connection, "rooms", column_name, sql_type)
    connection.executescript(FLOOR_INTERPRETATION_TABLES_SQL)
    connection.execute(
        """
        UPDATE rooms
        SET wall_corrected_geometry_json=CASE
              WHEN COALESCE(wall_corrected_geometry_json,'{}')='{}'
               AND COALESCE(boundary_source,'unknown') IN
                   ('wall_corrected','model_seed_wall_region','model_seed_wall_faces','hybrid','wall_geometry')
              THEN geometry_json ELSE wall_corrected_geometry_json END,
            dimension_status=CASE
              WHEN COALESCE(printed_width_mm,0)>0 AND COALESCE(printed_length_mm,0)>0 THEN 'exact'
              WHEN COALESCE(printed_width_mm,0)>0 OR COALESCE(printed_length_mm,0)>0 THEN 'partial'
              ELSE COALESCE(dimension_status,'unknown') END,
            dimension_source=CASE
              WHEN COALESCE(printed_width_mm,0)>0 OR COALESCE(printed_length_mm,0)>0
              THEN 'drawing' ELSE COALESCE(dimension_source,'unknown') END
        """
    )
    if not connection.execute(
        "SELECT version FROM schema_migrations WHERE version = ?",
        (FLOOR_INTERPRETATION_MIGRATION_VERSION,),
    ).fetchone():
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (FLOOR_INTERPRETATION_MIGRATION_VERSION, _now()),
        )


def _apply_versioned_detection_migration(connection: Any) -> None:
    """Add current-crop provenance without deleting historical generated data."""
    for column_name, sql_type in ELEMENT_DETECTION_COLUMNS:
        _add_column_if_missing(connection, "elements", column_name, sql_type)
    for column_name, sql_type in WALL_DETECTION_COLUMNS:
        _add_column_if_missing(connection, "walls", column_name, sql_type)
    for column_name, sql_type in ROOM_DETECTION_COLUMNS:
        _add_column_if_missing(connection, "rooms", column_name, sql_type)
    connection.executescript(VERSIONED_DETECTION_TABLES_SQL)

    # Existing records predate crop provenance. Associate generated records with
    # the current floor crop so they remain visible until a replacement analysis
    # reconciles or supersedes them. Manual records deliberately keep NULL crop scope.
    connection.execute(
        """
        UPDATE elements
        SET crop_id = COALESCE(crop_id, (
              SELECT fc.id FROM floor_crops fc
              WHERE fc.project_id=elements.project_id AND fc.floor_id=elements.floor_id AND fc.is_current=1
              ORDER BY fc.crop_version DESC LIMIT 1
            )),
            crop_version = COALESCE(crop_version, (
              SELECT fc.crop_version FROM floor_crops fc
              WHERE fc.project_id=elements.project_id AND fc.floor_id=elements.floor_id AND fc.is_current=1
              ORDER BY fc.crop_version DESC LIMIT 1
            )),
            generated_status = COALESCE(generated_status, 'current'),
            analysis_mode = COALESCE(analysis_mode, 'standard')
        WHERE COALESCE(is_manual,0)=0
        """
    )
    connection.execute(
        """
        UPDATE walls SET source_crop_version=COALESCE(source_crop_version,(
          SELECT crop_version FROM floor_versions fv WHERE fv.project_id=walls.project_id AND fv.floor_id=walls.floor_id
        )), generated_status=COALESCE(generated_status,'current')
        """
    )
    connection.execute(
        """
        UPDATE rooms SET source_crop_version=COALESCE(source_crop_version,(
          SELECT crop_version FROM floor_versions fv WHERE fv.project_id=rooms.project_id AND fv.floor_id=rooms.floor_id
        )), generated_status=COALESCE(generated_status,'current')
        """
    )
    if not connection.execute(
        "SELECT version FROM schema_migrations WHERE version = ?",
        (VERSIONED_DETECTION_MIGRATION_VERSION,),
    ).fetchone():
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (VERSIONED_DETECTION_MIGRATION_VERSION, _now()),
        )


def run_migrations(connection: Any) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version TEXT PRIMARY KEY,
          applied_at TEXT NOT NULL
        )
        """
    )
    for version, script in MIGRATIONS:
        if connection.execute(
            "SELECT version FROM schema_migrations WHERE version = ?", (version,)
        ).fetchone():
            continue
        connection.executescript(script)
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (version, _now()),
        )

    _apply_item_number_migration(connection)
    _apply_formal_boq_migration(connection)
    _apply_hybrid_floor_migration(connection)
    _apply_floor_accuracy_migration(connection)
    _apply_versioned_detection_migration(connection)
    _apply_floor_precision_migration(connection)
    _apply_floor_interpretation_migration(connection)
