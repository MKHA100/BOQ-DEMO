from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    project_number: str | None = Field(default=None, max_length=80)
    client_name: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=1000)


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    project_number: str | None = Field(default=None, max_length=80)
    client_name: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None, pattern="^(active|on_hold|completed|archived)$")


class ProjectResponse(BaseModel):
    id: str
    name: str
    status: str
    project_number: str | None = None
    client_name: str | None = None
    location: str | None = None
    description: str | None = None
    organization_id: str | None = None
    organization_name: str | None = None
    created_at: str
    updated_at: str


class ProjectCreateResponse(ProjectResponse):
    project_id: str


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int
    limit: int
    offset: int
