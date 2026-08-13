from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_ROOT / ".env", override=True)

def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default

def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default

def _env_tuple(name: str, default: str) -> tuple[str, ...]:
    return tuple(value.strip() for value in os.getenv(name, default).split(",") if value.strip())

def _app_mode() -> str:
    value = os.getenv("APP_MODE", os.getenv("RUNTIME_MODE", "local")).strip().lower()
    return "production" if value in {"production", "prod", "cloud", "neon"} else "local"

APP_MODE = _app_mode()
ENVIRONMENT = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development")).strip().lower()

@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "AutoBOQ")
    app_version: str = os.getenv("APP_VERSION", "2.1.0-foundation")
    api_prefix: str = os.getenv("API_PREFIX", "/api/v1")
    app_mode: str = APP_MODE
    environment: str = ENVIRONMENT
    debug: bool = _env_bool("DEBUG", ENVIRONMENT != "production")
    cors_origins: tuple[str, ...] = _env_tuple("CORS_ORIGINS", "http://localhost:3000")
    storage_root: Path = Path(os.getenv("LOCAL_STORAGE_ROOT", os.getenv("STORAGE_ROOT", "storage_data"))).resolve()
    database_path: Path = Path(os.getenv("LOCAL_DATABASE_PATH", os.getenv("DATABASE_PATH", "storage_data/app.db"))).resolve()
    database_url: str | None = (os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL") or None) if APP_MODE == "production" else None
    direct_database_url: str | None = (os.getenv("DIRECT_DATABASE_URL") or os.getenv("NEON_DIRECT_DATABASE_URL") or os.getenv("DATABASE_URL") or None) if APP_MODE == "production" else None
    storage_backend: str = os.getenv("STORAGE_BACKEND", "r2" if APP_MODE == "production" else "local").strip().lower()
    r2_endpoint_url: str | None = os.getenv("R2_ENDPOINT_URL") or None
    r2_bucket_name: str | None = os.getenv("R2_BUCKET_NAME") or None
    r2_access_key_id: str | None = os.getenv("R2_ACCESS_KEY_ID") or None
    r2_secret_access_key: str | None = os.getenv("R2_SECRET_ACCESS_KEY") or None
    r2_public_base_url: str | None = os.getenv("R2_PUBLIC_BASE_URL") or None
    r2_presigned_url_ttl_seconds: int = _env_int("R2_PRESIGNED_URL_TTL_SECONDS", 3600)
    auth_token_ttl_hours: int = _env_int("AUTH_TOKEN_TTL_HOURS", 24)
    auth_required: bool = _env_bool("AUTH_REQUIRED", ENVIRONMENT == "production")
    allow_local_auth_bypass: bool = _env_bool("ALLOW_LOCAL_AUTH_BYPASS", ENVIRONMENT != "production")
    super_admin_email: str | None = os.getenv("SUPER_ADMIN_EMAIL", "admin@construction.local") or None
    super_admin_password: str | None = os.getenv("SUPER_ADMIN_PASSWORD", "ChangeMe12345") or None
    super_admin_name: str = os.getenv("SUPER_ADMIN_NAME", "Platform Admin")
    sync_super_admin_on_startup: bool = _env_bool("SYNC_SUPER_ADMIN_ON_STARTUP", True)
    worker_max_attempts: int = max(_env_int("WORKER_MAX_ATTEMPTS", 3), 1)
    sqlite_busy_timeout_seconds: int = max(_env_int("SQLITE_BUSY_TIMEOUT_SECONDS", 30), 5)
    worker_poll_interval_seconds: int = max(_env_int("WORKER_POLL_INTERVAL_SECONDS", 3), 1)
    worker_lease_seconds: int = max(_env_int("WORKER_LEASE_SECONDS", 90), 15)
    max_upload_mb: int = max(_env_int("MAX_UPLOAD_MB", 200), 1)
    pdf_thumbnail_width: int = max(_env_int("PDF_THUMBNAIL_WIDTH", 360), 120)
    pdf_preview_width: int = max(_env_int("PDF_PREVIEW_WIDTH", 1600), 640)
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    openai_extraction_model: str = os.getenv("OPENAI_EXTRACTION_MODEL", "gpt-4.1-mini").strip()
    openai_extraction_timeout_seconds: int = max(_env_int("OPENAI_EXTRACTION_TIMEOUT_SECONDS", 90), 15)
    openai_extraction_max_pages: int = max(min(_env_int("OPENAI_EXTRACTION_MAX_PAGES", 12), 30), 1)
    roboflow_api_key: str | None = os.getenv("ROBOFLOW_API_KEY") or None
    roboflow_model_id: str = os.getenv("ROBOFLOW_MODEL_ID", "cubicasa5k-2-qpmsa/6").strip()
    roboflow_api_base_url: str = os.getenv("ROBOFLOW_API_BASE_URL", "https://serverless.roboflow.com").strip()
    roboflow_timeout_seconds: int = max(_env_int("ROBOFLOW_TIMEOUT_SECONDS", 90), 15)
    roboflow_floor_enabled: bool = _env_bool("ROBOFLOW_FLOOR_ENABLED", True)
    roboflow_floor_model_id: str = os.getenv("ROBOFLOW_FLOOR_MODEL_ID", "room-segmentation-o7iga/4").strip()
    roboflow_floor_confidence: float = max(0.01, min(float(os.getenv("ROBOFLOW_FLOOR_CONFIDENCE", "0.45")), 0.99))
    roboflow_floor_timeout_seconds: int = max(_env_int("ROBOFLOW_FLOOR_TIMEOUT_SECONDS", 90), 15)
    room_tiled_detection_enabled: bool = _env_bool("ROOM_TILED_DETECTION_ENABLED", True)
    room_tile_target_pixels: int = max(640, min(_env_int("ROOM_TILE_TARGET_PIXELS", 1280), 2048))
    room_tile_overlap: float = max(0.10, min(_env_float("ROOM_TILE_OVERLAP", 0.20), 0.35))
    room_tile_maximum: int = max(1, min(_env_int("ROOM_TILE_MAXIMUM", 12), 20))
    room_tile_concurrency: int = max(1, min(_env_int("ROOM_TILE_CONCURRENCY", 4), 6))
    model_detection_max_concurrency: int = max(1, min(_env_int("MODEL_DETECTION_MAX_CONCURRENCY", 2), 4))
    roboflow_door_confidence: float = max(0.01, min(_env_float("ROBOFLOW_DOOR_CONFIDENCE", 0.35), 0.99))
    roboflow_window_confidence: float = max(0.01, min(_env_float("ROBOFLOW_WINDOW_CONFIDENCE", 0.35), 0.99))
    roboflow_wall_confidence: float = max(0.01, min(_env_float("ROBOFLOW_WALL_CONFIDENCE", 0.30), 0.99))
    roboflow_deep_analysis_enabled: bool = _env_bool("ROBOFLOW_DEEP_ANALYSIS_ENABLED", True)
    roboflow_deep_analysis_tile_overlap: float = max(0.0, min(_env_float("ROBOFLOW_DEEP_ANALYSIS_TILE_OVERLAP", 0.15), 0.45))
    wall_auto_recovery_enabled: bool = _env_bool("WALL_AUTO_RECOVERY_ENABLED", True)
    wall_recovery_tile_pixels: int = max(640, min(_env_int("WALL_RECOVERY_TILE_PIXELS", 1024), 1600))
    wall_recovery_tile_overlap: float = max(0.15, min(_env_float("WALL_RECOVERY_TILE_OVERLAP", 0.25), 0.40))
    wall_recovery_max_tiles: int = max(1, min(_env_int("WALL_RECOVERY_MAX_TILES", 9), 16))
    wall_recovery_concurrency: int = max(1, min(_env_int("WALL_RECOVERY_CONCURRENCY", 4), 6))
    wall_recovery_min_confidence: float = max(0.05, min(_env_float("WALL_RECOVERY_MIN_CONFIDENCE", 0.50), 0.90))
    # PDF vector pairs are useful evidence but are unsafe as independent wall
    # detections because stairs, grids and furniture also contain parallel lines.
    wall_vector_recovery_enabled: bool = _env_bool("WALL_VECTOR_RECOVERY_ENABLED", False)
    wall_recovery_min_length: float = max(4.0, _env_float("WALL_RECOVERY_MIN_LENGTH", 10.0))
    wall_recovery_min_aspect_ratio: float = max(1.8, _env_float("WALL_RECOVERY_MIN_ASPECT_RATIO", 2.8))
    wall_recovery_min_thickness_ratio: float = max(0.1, _env_float("WALL_RECOVERY_MIN_THICKNESS_RATIO", 0.45))
    wall_recovery_max_thickness_ratio: float = max(1.0, _env_float("WALL_RECOVERY_MAX_THICKNESS_RATIO", 2.2))
    wall_recovery_max_gap: float = max(1.0, _env_float("WALL_RECOVERY_MAX_GAP", 14.0))
    wall_recovery_gap_thickness_factor: float = max(0.5, _env_float("WALL_RECOVERY_GAP_THICKNESS_FACTOR", 1.8))
    wall_recovery_repeated_line_limit: int = max(3, _env_int("WALL_RECOVERY_REPEATED_LINE_LIMIT", 4))
    wall_recovery_border_tolerance: float = max(0.0, _env_float("WALL_RECOVERY_BORDER_TOLERANCE", 1.5))
    door_recovery_min_confidence: float = max(0.1, min(_env_float("DOOR_RECOVERY_MIN_CONFIDENCE", 0.45), 0.95))
    window_recovery_min_confidence: float = max(0.1, min(_env_float("WINDOW_RECOVERY_MIN_CONFIDENCE", 0.45), 0.95))
    opening_recovery_min_size: float = max(1.0, _env_float("OPENING_RECOVERY_MIN_SIZE", 4.0))
    opening_recovery_max_aspect_ratio: float = max(2.0, _env_float("OPENING_RECOVERY_MAX_ASPECT_RATIO", 10.0))
    opening_recovery_wall_distance: float = max(1.0, _env_float("OPENING_RECOVERY_WALL_DISTANCE", 12.0))
    opening_recovery_wall_distance_factor: float = max(0.1, _env_float("OPENING_RECOVERY_WALL_DISTANCE_FACTOR", 0.65))
    opening_recovery_independent_confidence: float = max(0.5, min(_env_float("OPENING_RECOVERY_INDEPENDENT_CONFIDENCE", 0.72), 0.99))
    opening_recovery_border_confidence: float = max(0.5, min(_env_float("OPENING_RECOVERY_BORDER_CONFIDENCE", 0.82), 0.99))
    room_fast_pass_enabled: bool = _env_bool("ROOM_FAST_PASS_ENABLED", True)
    room_precision_pass_enabled: bool = _env_bool("ROOM_PRECISION_PASS_ENABLED", True)
    room_precision_max_concurrency: int = max(1, min(_env_int("ROOM_PRECISION_MAX_CONCURRENCY", 1), 2))
    room_min_edge_pixels: float = max(1.0, _env_float("ROOM_MIN_EDGE_PIXELS", 4.0))
    room_collinear_tolerance_degrees: float = max(0.5, min(_env_float("ROOM_COLLINEAR_TOLERANCE_DEGREES", 3.0), 15.0))
    room_orthogonal_tolerance_degrees: float = max(1.0, min(_env_float("ROOM_ORTHOGONAL_TOLERANCE_DEGREES", 5.0), 20.0))
    room_rectangle_confidence: float = max(0.70, min(_env_float("ROOM_RECTANGLE_CONFIDENCE", 0.90), 0.99))
    room_dimension_warning_percent: float = max(0.5, _env_float("ROOM_DIMENSION_WARNING_PERCENT", 2.0))
    room_dimension_error_percent: float = max(1.0, _env_float("ROOM_DIMENSION_ERROR_PERCENT", 5.0))
    room_llm_enabled: bool = _env_bool("ROOM_LLM_ENABLED", True)
    room_llm_only_when_ambiguous: bool = _env_bool("ROOM_LLM_ONLY_WHEN_AMBIGUOUS", True)
    room_llm_background_enabled: bool = _env_bool("ROOM_LLM_BACKGROUND_ENABLED", True)
    room_llm_model: str = os.getenv("ROOM_LLM_MODEL", "gpt-5.5").strip()
    room_llm_timeout_seconds: int = max(_env_int("ROOM_LLM_TIMEOUT_SECONDS", 60), 15)
    room_llm_max_floor_calls: int = max(1, min(_env_int("ROOM_LLM_MAX_FLOOR_CALLS", 2), 2))
    room_llm_max_room_crops: int = max(0, min(_env_int("ROOM_LLM_MAX_ROOM_CROPS", 20), 40))
    # Keep the older name as an alias so existing deployments remain valid.
    room_llm_max_crops_per_floor: int = max(
        0,
        min(
            _env_int(
                "ROOM_LLM_MAX_CROPS_PER_FLOOR",
                _env_int("ROOM_LLM_MAX_ROOM_CROPS", 20),
            ),
            40,
        ),
    )
    room_llm_confidence_threshold: float = max(
        0.0, min(_env_float("ROOM_LLM_CONFIDENCE_THRESHOLD", 0.65), 1.0)
    )
    room_results_publish_early: bool = _env_bool("ROOM_RESULTS_PUBLISH_EARLY", True)
    room_exception_correction_enabled: bool = _env_bool(
        "ROOM_EXCEPTION_CORRECTION_ENABLED", True
    )
    room_exception_min_label_confidence: float = max(
        0.0, min(_env_float("ROOM_EXCEPTION_MIN_LABEL_CONFIDENCE", 0.72), 1.0)
    )
    # Full-floor OCR is a fallback for raster/outlined labels. Vector PDF text
    # remains the fast default and per-room OCR remains available later.
    room_exception_full_floor_ocr_enabled: bool = _env_bool(
        "ROOM_EXCEPTION_FULL_FLOOR_OCR_ENABLED", False
    )
    room_exception_ocr_max_dimension: int = max(
        1200, min(_env_int("ROOM_EXCEPTION_OCR_MAX_DIMENSION", 3000), 5000)
    )

    @property
    def use_postgres(self) -> bool:
        return self.app_mode == "production" and bool(self.database_url and self.database_url.startswith(("postgres://", "postgresql://")))

    @property
    def use_r2(self) -> bool:
        return self.app_mode == "production" and self.storage_backend == "r2"

    @property
    def is_production(self) -> bool:
        return self.environment == "production" and not self.debug

settings = Settings()
if settings.app_mode == "production" and not settings.use_postgres:
    raise RuntimeError("APP_MODE=production requires a PostgreSQL/Neon DATABASE_URL.")
