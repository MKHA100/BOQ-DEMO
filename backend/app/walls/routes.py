from fastapi import APIRouter,Depends
from app.auth.dependencies import get_current_user
from app.projects.project_service import project_service
from app.walls.schemas import OpeningAssignRequest,WallCreateRequest,WallMergeRequest,WallSplitRequest,WallUpdateRequest
from app.walls.service import walls_service

router=APIRouter(prefix="/projects/{project_id}/walls",tags=["walls"])

@router.get("")
def state(project_id:str,floor_id:str|None=None,current_user:dict=Depends(get_current_user)):
    project=project_service.get_project(project_id,current_user.get("id")); return walls_service.get_state(project,floor_id)
@router.post("/floors/{floor_id}")
def create(project_id:str,floor_id:str,payload:WallCreateRequest,current_user:dict=Depends(get_current_user)):
    project_service.get_project(project_id,current_user.get("id")); return walls_service.create(project_id,floor_id,payload.model_dump(),current_user.get("id"))
@router.post("/floors/{floor_id}/regenerate")
def regenerate(project_id:str,floor_id:str,current_user:dict=Depends(get_current_user)):
    project_service.get_project(project_id,current_user.get("id")); return walls_service.process_floor(project_id,floor_id,current_user.get("id"))
@router.post("/floors/{floor_id}/auto-fix")
def auto_fix(project_id:str,floor_id:str,current_user:dict=Depends(get_current_user)):
    project_service.get_project(project_id,current_user.get("id")); return walls_service.auto_fix(project_id,floor_id,current_user.get("id"))
@router.post("/floors/{floor_id}/confirm-all")
def confirm_all(project_id:str,floor_id:str,current_user:dict=Depends(get_current_user)):
    project_service.get_project(project_id,current_user.get("id")); return walls_service.confirm_all(project_id,floor_id,current_user.get("id"))
@router.patch("/floors/{floor_id}/{wall_id}")
def update(project_id:str,floor_id:str,wall_id:str,payload:WallUpdateRequest,current_user:dict=Depends(get_current_user)):
    project_service.get_project(project_id,current_user.get("id")); return walls_service.update(project_id=project_id,floor_id=floor_id,wall_id=wall_id,payload=payload.model_dump(exclude_unset=True),created_by=current_user.get("id"))
@router.post("/floors/{floor_id}/{wall_id}/openings")
def assign(project_id:str,floor_id:str,wall_id:str,payload:OpeningAssignRequest,current_user:dict=Depends(get_current_user)):
    project_service.get_project(project_id,current_user.get("id")); return walls_service.assign_opening(project_id,floor_id,wall_id,payload.element_id,current_user.get("id"))
@router.post("/floors/{floor_id}/{wall_id}/split")
def split(project_id:str,floor_id:str,wall_id:str,payload:WallSplitRequest,current_user:dict=Depends(get_current_user)):
    project_service.get_project(project_id,current_user.get("id")); return walls_service.split(project_id,floor_id,wall_id,payload.model_dump(),current_user.get("id"))
@router.post("/floors/{floor_id}/{wall_id}/merge")
def merge(project_id:str,floor_id:str,wall_id:str,payload:WallMergeRequest,current_user:dict=Depends(get_current_user)):
    project_service.get_project(project_id,current_user.get("id")); return walls_service.merge(project_id,floor_id,wall_id,payload.other_wall_id,current_user.get("id"))
@router.post("/floors/{floor_id}/{wall_id}/restore")
def restore(project_id:str,floor_id:str,wall_id:str,current_user:dict=Depends(get_current_user)):
    project_service.get_project(project_id,current_user.get("id")); return walls_service.restore(project_id,floor_id,wall_id,current_user.get("id"))
@router.delete("/floors/{floor_id}/{wall_id}")
def remove(project_id:str,floor_id:str,wall_id:str,current_user:dict=Depends(get_current_user)):
    project_service.get_project(project_id,current_user.get("id")); return walls_service.delete(project_id,floor_id,wall_id,current_user.get("id"))
