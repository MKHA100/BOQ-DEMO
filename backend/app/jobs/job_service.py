from __future__ import annotations

import hashlib
import json
from typing import Any

from app.jobs.job_models import get_task_spec
from app.jobs.job_repository import READ_MODEL_TASKS, job_repository

def build_job_key(*, project_id: str | None, floor_id: str | None, task_type: str,
    input_versions: dict | None, entity_id: str | None = None) -> str:
    payload=json.dumps(input_versions or {},sort_keys=True,separators=(",",":"),default=str)
    version_hash=hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20]
    scope=f"project:{project_id or 'global'}:floor:{floor_id or 'all'}"
    entity=f":entity:{entity_id}" if entity_id else ""
    return f"{scope}:task:{task_type}{entity}:input:{version_hash}"

class JobService:
    def enqueue(self, *, task_type: str, project_id: str | None, floor_id: str | None = None,
        payload: dict | None = None, input_versions: dict | None = None, entity_id: str | None = None,
        created_by: str | None = None, job_key: str | None = None) -> tuple[dict,bool]:
        spec=get_task_spec(task_type)
        if spec.floor_scoped and not floor_id:raise ValueError(f"{task_type} requires floor_id")
        # BOQ is project-wide even when a floor edit caused the refresh.
        resolved_floor_id=None if task_type in READ_MODEL_TASKS else floor_id
        if task_type in READ_MODEL_TASKS and project_id:
            pending=job_repository.latest_pending_job(project_id=project_id,task_type=task_type,floor_id=resolved_floor_id)
            if pending:
                refreshed=job_repository.refresh_pending_job(str(pending['id']),payload=payload or {},
                    input_versions=input_versions or {},created_by=created_by,max_attempts=spec.retry_limit)
                return self.serialize_job(refreshed or pending),False
            running=job_repository.latest_running_job(project_id=project_id,task_type=task_type,floor_id=resolved_floor_id)
            if running:
                resolved_key=job_key or f"project:{project_id}:floor:{resolved_floor_id or 'all'}:task:{task_type}:after:{running['id']}"
            else:
                resolved_key=job_key or build_job_key(project_id=project_id,floor_id=resolved_floor_id,
                    task_type=task_type,input_versions=input_versions,entity_id=None)
        else:
            resolved_key=job_key or build_job_key(project_id=project_id,floor_id=resolved_floor_id,
                task_type=task_type,input_versions=input_versions,entity_id=entity_id)
        job,created=job_repository.create_or_get_job(task_type=task_type,category=spec.category,
            job_key=resolved_key,project_id=project_id,floor_id=resolved_floor_id,payload=payload or {},
            input_versions=input_versions or {},created_by=created_by,max_attempts=spec.retry_limit)
        return self.serialize_job(job),created
    def requeue_job(self,job_id:str)->dict|None:
        job=job_repository.requeue_job(job_id,reset_attempts=True);return self.serialize_job(job) if job else None
    def get_job(self,job_id:str)->dict|None:
        job=job_repository.get_job(job_id);return self.serialize_job(job) if job else None
    def list_project_jobs(self,*,project_id:str,floor_id:str|None=None,active_only:bool=False,limit:int=50)->list[dict]:
        return [self.serialize_job(job) for job in job_repository.list_project_jobs(project_id=project_id,
            floor_id=floor_id,active_only=active_only,limit=limit)]
    def serialize_job(self,job:dict)->dict:
        return {'id':job.get('id'),'project_id':job.get('project_id'),'floor_id':job.get('floor_id'),
            'category':job.get('category'),'task_type':job.get('task_type'),'job_type':job.get('task_type'),
            'job_key':job.get('job_key'),'status':job.get('status'),'progress':int(job.get('progress') or 0),
            'message':job.get('message'),'error_message':job.get('error_message'),'payload':self._loads(job.get('payload_json')),
            'input_versions':self._loads(job.get('input_versions_json')),'result':self._loads(job.get('result_json')),
            'attempts':int(job.get('attempts') or 0),'max_attempts':int(job.get('max_attempts') or 1),
            'created_at':job.get('created_at'),'updated_at':job.get('updated_at'),'started_at':job.get('started_at'),
            'finished_at':job.get('finished_at')}
    @staticmethod
    def _loads(value:Any)->dict:
        if isinstance(value,dict):return value
        if not value:return {}
        try:parsed=json.loads(value)
        except (TypeError,ValueError,json.JSONDecodeError):return {}
        return parsed if isinstance(parsed,dict) else {}

job_service=JobService()
