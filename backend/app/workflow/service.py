from app.workflow.element_service import ElementServiceMixin
from app.workflow.floor_service import FloorServiceMixin
from app.workflow.geometry_service import GeometryServiceMixin
from app.workflow.service_base import ServiceBaseMixin
from app.workflow.summary_service import SummaryServiceMixin


class WorkflowService(
    FloorServiceMixin,
    ElementServiceMixin,
    GeometryServiceMixin,
    SummaryServiceMixin,
    ServiceBaseMixin,
):
    pass


workflow_service = WorkflowService()
