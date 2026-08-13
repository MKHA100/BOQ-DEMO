from __future__ import annotations

from app.boq.setup_repo import boq_setup_repository
from app.projects.project_service import project_service


class BoqSetupService:
    def get(self, project: dict) -> dict:
        return boq_setup_repository.ensure(project)

    def update(self, project_id: str, payload: dict, user_id: str | None = None) -> dict:
        project = project_service.get_project(project_id, user_id)
        boq_setup_repository.ensure(project)
        return boq_setup_repository.update(project_id, payload)


boq_setup_service = BoqSetupService()
