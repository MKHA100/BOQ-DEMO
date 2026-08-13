from __future__ import annotations

from app.jobs.job_models import TASK_SPECS, register_job_type

FOUNDATION_JOB_SPECS: tuple[dict, ...] = (
    {"task_type": "ingest.page_metadata", "category": "ingest", "label": "Page information", "retry_limit": 3},
    {"task_type": "render.page_thumbnails", "category": "render", "label": "Page thumbnails", "retry_limit": 3},
    {"task_type": "render.page_previews", "category": "render", "label": "Page previews", "retry_limit": 3},
    {"task_type": "render.floor_crop", "category": "render", "label": "Floor crop preview", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "extract.floor_crop_text", "category": "extract", "label": "Floor drawing notes", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "extract.vector_text", "category": "extract", "label": "Drawing text", "retry_limit": 3},
    {"task_type": "ingest.page_classification", "category": "ingest", "label": "Page organization", "retry_limit": 3},
    {"task_type": "extract.doors", "category": "extract", "label": "Door information", "retry_limit": 3},
    {"task_type": "extract.windows", "category": "extract", "label": "Window information", "retry_limit": 3},
    {"task_type": "extract.walls", "category": "extract", "label": "Wall information", "retry_limit": 3},
    {"task_type": "extract.floors", "category": "extract", "label": "Floor information", "retry_limit": 3},
    {"task_type": "extract.schedule", "category": "extract", "label": "Schedule extraction", "retry_limit": 3},
    {"task_type": "extract.specification", "category": "extract", "label": "Specification extraction", "retry_limit": 3},
    {"task_type": "extract.schedule.doors", "category": "extract", "label": "Door schedule", "retry_limit": 3},
    {"task_type": "extract.schedule.windows", "category": "extract", "label": "Window schedule", "retry_limit": 3},
    {"task_type": "extract.schedule.walls", "category": "extract", "label": "Wall schedule", "retry_limit": 3},
    {"task_type": "extract.schedule.floors", "category": "extract", "label": "Floor schedule", "retry_limit": 3},
    {"task_type": "extract.schedule.specification", "category": "extract", "label": "Specification", "retry_limit": 3},
    {"task_type": "extract.schedule.other", "category": "extract", "label": "Supporting file", "retry_limit": 3},
    {"task_type": "vision.detect_doors", "category": "vision", "label": "Door detection", "retry_limit": 2, "floor_scoped": True},
    {"task_type": "vision.detect_windows", "category": "vision", "label": "Window detection", "retry_limit": 2, "floor_scoped": True},
    {"task_type": "vision.detect_walls", "category": "vision", "label": "Wall detection", "retry_limit": 2, "floor_scoped": True},
    {"task_type": "vision.detect_rooms", "category": "vision", "label": "Room suggestions", "retry_limit": 2, "floor_scoped": True},
    {"task_type": "vision.read_tags", "category": "vision", "label": "Tag reading", "retry_limit": 5, "floor_scoped": True},
    {"task_type": "vision.match_schedules", "category": "vision", "label": "Schedule matching", "retry_limit": 5, "floor_scoped": True},
    {"task_type": "vision.detect_elements", "category": "vision", "label": "Model analysis", "retry_limit": 2, "floor_scoped": True},
    {"task_type": "measure.elements", "category": "measure", "label": "Element measurements", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "walls.build_centerlines", "category": "walls", "label": "Wall centerlines", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "walls.prepare_quantities", "category": "walls", "label": "Wall quantities", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "rooms.prepare_geometry", "category": "rooms", "label": "Room geometry", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "measure.floor", "category": "measure", "label": "Floor measurements", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "measure.element", "category": "measure", "label": "Element measurement", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "walls.build", "category": "walls", "label": "Wall calculation", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "walls.recalculate_deduction", "category": "walls", "label": "Wall opening deduction", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "walls.build_lines", "category": "walls", "label": "Wall lines", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "walls.find_boundary", "category": "walls", "label": "Building boundary", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "walls.classify", "category": "walls", "label": "Wall classification", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "walls.assign_openings", "category": "walls", "label": "Opening assignment", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "walls.calculate_areas", "category": "walls", "label": "Wall quantities", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "rooms.rebuild_touching", "category": "rooms", "label": "Touching rooms", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "rooms.publish_model_results", "category": "rooms", "label": "Publish detected rooms", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "rooms.prepare_lines", "category": "rooms", "label": "Room boundaries", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "rooms.build_polygons", "category": "rooms", "label": "Room polygons", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "rooms.reconcile", "category": "rooms", "label": "Room comparison", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "rooms.identify_labels", "category": "rooms", "label": "Room labels", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "rooms.assign_finishes", "category": "rooms", "label": "Floor finishes", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "rooms.calculate_areas", "category": "rooms", "label": "Floor quantities", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "rooms.precision_refine", "category": "rooms", "label": "Precision room geometry", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "rooms.interpret_floor", "category": "rooms", "label": "Floor room interpretation", "retry_limit": 2, "floor_scoped": True},
    {"task_type": "rooms.interpret_ambiguous", "category": "rooms", "label": "Room label interpretation", "retry_limit": 2, "floor_scoped": True},
    {"task_type": "rooms.build", "category": "rooms", "label": "Room calculation", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "rooms.measure", "category": "rooms", "label": "Room measurement", "retry_limit": 3, "floor_scoped": True},
    {"task_type": "review.refresh", "category": "review", "label": "Review refresh", "retry_limit": 3},
    {"task_type": "boq.refresh", "category": "boq", "label": "BOQ refresh", "retry_limit": 3},
    {"task_type": "export.generate", "category": "export", "label": "Export generation", "retry_limit": 2},
)


def register_foundation_job_specs() -> None:
    for spec in FOUNDATION_JOB_SPECS:
        if spec["task_type"] in TASK_SPECS:
            continue
        register_job_type(
            spec["task_type"],
            spec.get("label"),
            category=spec.get("category"),
            retry_limit=spec.get("retry_limit", 3),
            floor_scoped=spec.get("floor_scoped", False),
        )
