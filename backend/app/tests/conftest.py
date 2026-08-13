from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def foundation_db(monkeypatch, tmp_path):
    database_path = tmp_path / "foundation.db"
    storage_path = tmp_path / "storage"
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOCAL_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(storage_path))
    monkeypatch.setenv("SYNC_SUPER_ADMIN_ON_STARTUP", "false")

    # backend/.env is intentionally authoritative for local application runs,
    # but it must not overwrite this fixture's temporary database/storage.
    import dotenv

    original_load_dotenv = dotenv.load_dotenv

    def load_test_dotenv(*args, **kwargs):
        kwargs["override"] = False
        return original_load_dotenv(*args, **kwargs)

    monkeypatch.setattr(dotenv, "load_dotenv", load_test_dotenv)

    import app.core.config as config
    import app.database.session as session
    import app.storage.storage_paths as storage_paths
    import app.storage.local_storage as local_storage
    import app.storage.r2_storage as r2_storage
    import app.storage.storage_service as storage_service

    importlib.reload(config)
    importlib.reload(session)
    importlib.reload(storage_paths)
    importlib.reload(local_storage)
    importlib.reload(r2_storage)
    importlib.reload(storage_service)
    session.init_db()

    for module_name in (
        "app.pdf_upload.repo",
        "app.pdf_upload.service",
        "app.pdf_upload.pdf",
        "app.pdf_upload.extract",
        "app.pdf_upload.jobs",
        "app.floor_plans.repo",
        "app.floor_plans.service",
        "app.floor_plans.jobs",
        "app.specifications.repo",
        "app.specifications.service",
        "app.specifications.extract",
        "app.specifications.jobs",
        "app.scale.repo",
        "app.scale.service",
        "app.scale.jobs",
        "app.model_review.repo",
        "app.model_review.prediction_processor",
        "app.model_review.reconciliation_service",
        "app.model_review.provider",
        "app.model_review.detection_service",
        "app.model_review.cleanup_service",
        "app.model_review.tag_service",
        "app.model_review.service",
        "app.model_review.jobs",
        "app.walls.repo",
        "app.walls.service",
        "app.walls.jobs",
        "app.floors.repo",
        "app.floors.room_segmentation_provider",
        "app.floors.line_builder",
        "app.floors.polygon_builder",
        "app.floors.hybrid_matcher",
        "app.floors.label_service",
        "app.floors.shape_recognizer",
        "app.floors.polygon_regularizer",
        "app.floors.building_envelope_service",
        "app.floors.wall_footprint_service",
        "app.floors.free_space_service",
        "app.floors.dimension_constraint_service",
        "app.floors.room_validation_service",
        "app.floors.room_edit_service",
        "app.floors.edit_history_service",
        "app.floors.finish_zone_service",
        "app.floors.llm_room_prompt",
        "app.floors.llm_room_schema",
        "app.floors.llm_room_context_service",
        "app.floors.llm_room_cache",
        "app.floors.room_area_resolver",
        "app.floors.room_result_validator",
        "app.floors.llm_room_interpreter",
        "app.floors.precision_pipeline",
        "app.floors.service",
        "app.floors.jobs",
        "app.review.repo",
        "app.review.service",
        "app.review.jobs",
        "app.boq.repo",
        "app.boq.service",
        "app.boq.jobs",
    ):
        try:
            import sys
            module = sys.modules.get(module_name)
            if module is not None:
                importlib.reload(module)
        except Exception:
            pass

    from app.jobs import job_models
    from app.workflow.jobs import register_foundation_job_specs

    job_models.TASK_SPECS.clear()
    job_models.SUPPORTED_JOB_TYPES.clear()
    job_models.JOB_TYPE_LABELS.clear()
    register_foundation_job_specs()
    import app.jobs.worker as worker
    worker.PROCESSORS.clear()
    worker._PROCESSORS_REGISTERED = False

    return {"database_path": database_path, "storage_path": storage_path, "session": session}
