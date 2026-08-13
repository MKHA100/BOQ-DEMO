from pathlib import Path
import shutil

from app.core.config import settings
from app.storage import storage_paths


class LocalStorage:
    """Local filesystem storage adapter.

    Used directly in APP_MODE=local and also as the local processing/cache folder
    before files are uploaded to R2 in APP_MODE=production.
    """

    def __init__(self) -> None:
        self.ensure_root()

    def ensure_root(self) -> Path:
        settings.storage_root.mkdir(parents=True, exist_ok=True)
        return settings.storage_root

    def create_project_directories(self, project_id: str) -> None:
        self.ensure_root()
        for directory in [
            storage_paths.files_dir(project_id),
            storage_paths.metadata_dir(project_id),
            storage_paths.temporary_dir(project_id),
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def write_bytes(self, path: Path, content: bytes) -> Path:
        self.ensure_root()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def copy_file(self, source: Path, destination: Path) -> Path:
        self.ensure_root()
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination

    def remove_project(self, project_id: str) -> None:
        root = storage_paths.project_root(project_id)
        if root.exists():
            shutil.rmtree(root)
