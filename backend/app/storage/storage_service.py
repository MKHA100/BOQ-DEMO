from __future__ import annotations

from pathlib import Path
import mimetypes
from fastapi.responses import FileResponse, RedirectResponse

from app.core.config import settings
from app.storage.local_storage import LocalStorage
from app.storage.r2_storage import R2Storage


class StorageService:
    """Unified storage service.

    APP_MODE is the single switch:
    - local       => save/read files from storage_data only
    - production  => cache files locally while processing, then upload/read from R2

    Database records keep the same local file_path values so existing project code
    remains compatible in both modes.
    """

    def __init__(self) -> None:
        self.local = LocalStorage()
        self.r2 = R2Storage()

    @property
    def use_r2(self) -> bool:
        return settings.use_r2

    def create_project_directories(self, project_id: str) -> None:
        self.local.create_project_directories(project_id)

    def path_to_key(self, path: str | Path) -> str:
        p = Path(path)
        try:
            return p.resolve().relative_to(settings.storage_root).as_posix()
        except Exception:
            return p.as_posix().lstrip("/")

    def key_to_path(self, key: str) -> Path:
        return settings.storage_root / key

    def content_type_for(self, path: str | Path) -> str | None:
        content_type, _ = mimetypes.guess_type(str(path))
        return content_type

    def write_bytes(self, path: Path, content: bytes, upload: bool = True) -> Path:
        saved = self.local.write_bytes(path, content)
        if upload:
            self.upload_file(saved)
        return saved

    def copy_file(self, source: Path, destination: Path, upload: bool = True) -> Path:
        saved = self.local.copy_file(source, destination)
        if upload:
            self.upload_file(saved)
        return saved

    def upload_file(self, path: str | Path) -> str | None:
        p = Path(path)
        if not p.exists():
            return None
        if not self.use_r2:
            return None
        key = self.path_to_key(p)
        self.r2.upload_file(p, key, self.content_type_for(p))
        return key

    def ensure_local_file(self, path: str | Path) -> Path:
        p = Path(path)
        if p.exists():
            return p
        if not self.use_r2:
            return p
        key = self.path_to_key(p)
        return self.r2.download_file(key, p)

    def delete_file(self, path: str | Path) -> None:
        p = Path(path)
        if p.exists():
            p.unlink()
        if self.use_r2:
            self.r2.delete_file(self.path_to_key(p))

    def file_exists(self, path: str | Path) -> bool:
        p = Path(path)
        if p.exists():
            return True
        return self.use_r2 and self.r2.object_exists(self.path_to_key(p))

    def download_response(self, path: str | Path, media_type: str | None = None, filename: str | None = None):
        p = Path(path)
        if self.use_r2 and not p.exists():
            key = self.path_to_key(p)
            public_url = self.r2.public_url(key)
            if public_url:
                return RedirectResponse(public_url)
            return RedirectResponse(self.r2.presigned_get_url(key))
        local_path = self.ensure_local_file(p)
        return FileResponse(local_path, media_type=media_type, filename=filename or local_path.name)

    def remove_project(self, project_id: str) -> None:
        self.local.remove_project(project_id)
        if self.use_r2:
            self.r2.delete_prefix(f"projects/{project_id}/")


storage_service = StorageService()
