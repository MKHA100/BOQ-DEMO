from pathlib import Path
from app.core.config import settings


def project_root(project_id: str) -> Path:
    return settings.storage_root / "projects" / project_id


def files_dir(project_id: str) -> Path:
    return project_root(project_id) / "files"


def metadata_dir(project_id: str) -> Path:
    return project_root(project_id) / "metadata"


def temporary_dir(project_id: str) -> Path:
    return project_root(project_id) / "temporary"


def document_root(project_id: str, document_id: str) -> Path:
    return files_dir(project_id) / "documents" / document_id


def document_original_path(project_id: str, document_id: str, content_hash: str) -> Path:
    return document_root(project_id, document_id) / "original" / f"{content_hash}.pdf"


def document_assets_dir(project_id: str, document_id: str) -> Path:
    return document_root(project_id, document_id) / "pages"


def page_thumbnail_path(project_id: str, document_id: str, page_number: int) -> Path:
    return document_assets_dir(project_id, document_id) / f"page-{page_number:04d}" / "thumbnail.png"


def page_preview_path(project_id: str, document_id: str, page_number: int) -> Path:
    return document_assets_dir(project_id, document_id) / f"page-{page_number:04d}" / "preview.png"


def page_text_path(project_id: str, document_id: str, page_number: int) -> Path:
    return metadata_dir(project_id) / "documents" / document_id / f"page-{page_number:04d}.json"


def temporary_upload_path(project_id: str, upload_id: str) -> Path:
    return temporary_dir(project_id) / f"{upload_id}.part"


def relative_storage_key(path: Path) -> str:
    try:
        return path.resolve().relative_to(settings.storage_root).as_posix()
    except Exception:
        return path.as_posix().lstrip("/")


def document_source_path(project_id: str, document_id: str, content_hash: str, extension: str) -> Path:
    clean_extension = extension.lower().lstrip('.') or 'bin'
    return document_root(project_id, document_id) / 'original' / f'{content_hash}.{clean_extension}'


def floor_crop_dir(project_id: str, floor_id: str, crop_version: int) -> Path:
    return files_dir(project_id) / 'floors' / floor_id / 'crops' / f'v{crop_version:04d}'


def floor_crop_asset_path(project_id: str, floor_id: str, crop_version: int) -> Path:
    return floor_crop_dir(project_id, floor_id, crop_version) / 'crop.png'


def floor_crop_preview_path(project_id: str, floor_id: str, crop_version: int) -> Path:
    return floor_crop_dir(project_id, floor_id, crop_version) / 'preview.png'


def supporting_source_dir(project_id: str, source_id: str) -> Path:
    return files_dir(project_id) / 'supporting' / source_id


def supporting_source_original_path(project_id: str, source_id: str, content_hash: str, extension: str) -> Path:
    clean_extension = extension.lower().lstrip('.') or 'bin'
    return supporting_source_dir(project_id, source_id) / 'original' / f'{content_hash}.{clean_extension}'


def supporting_source_preview_path(project_id: str, source_id: str) -> Path:
    return supporting_source_dir(project_id, source_id) / 'preview.png'


def boq_export_path(project_id: str, boq_id: str, filename: str) -> Path:
    return files_dir(project_id) / "boq" / boq_id / "exports" / filename
