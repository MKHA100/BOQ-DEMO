from app.workflow.element_repo import ElementRepositoryMixin
from app.workflow.event_repo import EventRepositoryMixin
from app.workflow.file_repo import FileRepositoryMixin
from app.workflow.floor_repo import FloorRepositoryMixin
from app.workflow.repo_base import dumps, loads, now_iso
from app.workflow.room_repo import RoomRepositoryMixin


class WorkflowRepository(
    FloorRepositoryMixin,
    ElementRepositoryMixin,
    RoomRepositoryMixin,
    EventRepositoryMixin,
    FileRepositoryMixin,
):
    pass


workflow_repository = WorkflowRepository()

__all__ = ["dumps", "loads", "now_iso", "workflow_repository"]
