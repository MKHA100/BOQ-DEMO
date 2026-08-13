from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from uuid import uuid4

from app.database.session import get_connection, row_to_dict
from app.jobs.job_models import (
    JOB_STATUS_CANCELLED, JOB_STATUS_COMPLETED, JOB_STATUS_FAILED,
    JOB_STATUS_PENDING, JOB_STATUS_RUNNING,
)

READ_MODEL_TASKS = {"review.refresh", "boq.refresh"}

_TASK_PRIORITY_SQL = """
CASE
  WHEN task_type = 'render.floor_crop' THEN 0
  WHEN task_type IN ('render.page_thumbnails', 'render.page_previews') THEN 10
  WHEN task_type IN ('ingest.page_metadata', 'ingest.page_classification') THEN 20
  WHEN task_type = 'extract.floor_crop_text' THEN 25
  WHEN task_type = 'vision.detect_rooms' THEN 28
  WHEN task_type = 'vision.detect_floor_elements' THEN 30
  WHEN task_type = 'rooms.publish_model_results' THEN 34
  WHEN task_type = 'vision.recover_floor_walls' THEN 65
  WHEN task_type LIKE 'vision.%' THEN 40
  WHEN task_type LIKE 'measure.%' THEN 45
  WHEN task_type LIKE 'walls.%' THEN 50
  WHEN task_type IN ('rooms.interpret_floor', 'rooms.interpret_ambiguous') THEN 75
  WHEN task_type = 'rooms.precision_refine' THEN 80
  WHEN task_type = 'rooms.calculate_areas' THEN 82
  WHEN task_type LIKE 'rooms.%' THEN 55
  WHEN task_type LIKE 'extract.%' THEN 60
  WHEN task_type = 'review.refresh' THEN 90
  WHEN task_type = 'boq.refresh' THEN 100
  WHEN task_type = 'export.generate' THEN 110
  ELSE 70
END
"""

_FLOOR_PIPELINE_TASKS = {
    "render.floor_crop", "extract.floor_crop_text", "vision.detect_floor_elements",
    "vision.detect_doors", "vision.detect_windows", "vision.detect_walls",
    "vision.recover_floor_walls", "vision.read_tags",
    "vision.match_schedules", "vision.detect_rooms", "measure.elements",
    "walls.build_centerlines", "walls.prepare_quantities", "walls.build_lines",
    "walls.find_boundary", "walls.classify", "walls.assign_openings",
    "walls.calculate_areas", "walls.recalculate_deduction", "rooms.prepare_geometry",
    "rooms.publish_model_results", "rooms.prepare_lines", "rooms.build_polygons", "rooms.reconcile",
    "rooms.identify_labels", "rooms.assign_finishes", "rooms.calculate_areas",
    "rooms.precision_refine", "rooms.interpret_floor", "rooms.interpret_ambiguous",
    "rooms.build", "rooms.measure", "rooms.rebuild_touching", "review.refresh",
    "boq.refresh",
}

def _now_dt() -> datetime: return datetime.now(timezone.utc)
def _now() -> str: return _now_dt().isoformat()
def _json_dumps(value: Any) -> str:
    return json.dumps(value or {}, default=str, sort_keys=True, separators=(",", ":"))
def _json_loads(value: Any) -> dict:
    if isinstance(value, dict): return value
    if not value: return {}
    try: parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError): return {}
    return parsed if isinstance(parsed, dict) else {}
def _floor_clause(floor_id: str | None) -> tuple[str, tuple[Any, ...]]:
    return ("floor_id IS NULL", ()) if floor_id is None else ("floor_id = ?", (floor_id,))

class JobRepository:
    def create_or_get_job(self, *, task_type: str, category: str, job_key: str,
        project_id: str | None, floor_id: str | None, payload: dict | None,
        input_versions: dict | None, created_by: str | None, max_attempts: int) -> tuple[dict, bool]:
        existing = self.get_by_key(job_key)
        if existing: return existing, False
        now = _now(); job_id = str(uuid4())
        try:
            with get_connection() as connection:
                connection.execute("""
                    INSERT INTO job_runs (
                      id, project_id, floor_id, category, task_type, job_key, status, progress,
                      message, payload_json, input_versions_json, result_json, error_message,
                      attempts, max_attempts, retry_at, locked_by, lease_expires_at, heartbeat_at,
                      created_by, started_at, finished_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, '{}', NULL, 0, ?, NULL, NULL, NULL, NULL, ?, NULL, NULL, ?, ?)
                    """, (job_id, project_id, floor_id, category, task_type, job_key,
                    JOB_STATUS_PENDING, "Waiting", _json_dumps(payload), _json_dumps(input_versions),
                    max(1, int(max_attempts)), created_by, now, now))
        except Exception:
            existing = self.get_by_key(job_key)
            if existing: return existing, False
            raise
        return self.get_job(job_id) or {}, True

    def get_by_key(self, job_key: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute("SELECT * FROM job_runs WHERE job_key = ?", (job_key,)).fetchone()
        return row_to_dict(row)
    def get_job(self, job_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute("SELECT * FROM job_runs WHERE id = ?", (job_id,)).fetchone()
        return row_to_dict(row)

    def latest_active_job(self, *, project_id: str, task_type: str, floor_id: str | None = None) -> dict | None:
        floor_sql, floor_params = _floor_clause(floor_id)
        with get_connection() as connection:
            row = connection.execute(f"""
                SELECT * FROM job_runs WHERE project_id = ? AND task_type = ?
                AND status IN (?, ?) AND {floor_sql}
                ORDER BY CASE WHEN status = ? THEN 0 ELSE 1 END, created_at DESC LIMIT 1
                """, (project_id, task_type, JOB_STATUS_RUNNING, JOB_STATUS_PENDING,
                *floor_params, JOB_STATUS_RUNNING)).fetchone()
        return row_to_dict(row)
    def latest_pending_job(self, *, project_id: str, task_type: str, floor_id: str | None) -> dict | None:
        floor_sql, floor_params = _floor_clause(floor_id)
        with get_connection() as connection:
            row = connection.execute(f"""SELECT * FROM job_runs WHERE project_id=? AND task_type=?
                AND status=? AND {floor_sql} ORDER BY created_at DESC LIMIT 1""",
                (project_id, task_type, JOB_STATUS_PENDING, *floor_params)).fetchone()
        return row_to_dict(row)
    def latest_running_job(self, *, project_id: str, task_type: str, floor_id: str | None) -> dict | None:
        floor_sql, floor_params = _floor_clause(floor_id)
        with get_connection() as connection:
            row = connection.execute(f"""SELECT * FROM job_runs WHERE project_id=? AND task_type=?
                AND status=? AND {floor_sql} ORDER BY created_at DESC LIMIT 1""",
                (project_id, task_type, JOB_STATUS_RUNNING, *floor_params)).fetchone()
        return row_to_dict(row)
    def refresh_pending_job(self, job_id: str, *, payload: dict | None,
        input_versions: dict | None, created_by: str | None, max_attempts: int) -> dict | None:
        now = _now()
        with get_connection() as connection:
            connection.execute("""UPDATE job_runs SET payload_json=?, input_versions_json=?,
                created_by=COALESCE(?,created_by), max_attempts=?, retry_at=NULL,
                error_message=NULL, message='Waiting', updated_at=? WHERE id=? AND status=?""",
                (_json_dumps(payload), _json_dumps(input_versions), created_by,
                max(1,int(max_attempts)), now, job_id, JOB_STATUS_PENDING))
            row=connection.execute("SELECT * FROM job_runs WHERE id=?",(job_id,)).fetchone()
        return row_to_dict(row)

    def list_project_jobs(self, *, project_id: str, floor_id: str | None = None,
        active_only: bool = False, limit: int = 50) -> list[dict]:
        where=["project_id = ?"]; params:list[Any]=[project_id]
        if floor_id is not None: where.append("floor_id = ?"); params.append(floor_id)
        if active_only: where.append("status IN (?, ?)"); params.extend([JOB_STATUS_PENDING,JOB_STATUS_RUNNING])
        params.append(max(1,min(int(limit),1000)))
        with get_connection() as connection:
            rows=connection.execute(f"SELECT * FROM job_runs WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ?",tuple(params)).fetchall()
        return [row_to_dict(row) or {} for row in rows]

    def cancel_pending_floor_pipeline(self, project_id: str, floor_id: str) -> int:
        now=_now(); task_types=sorted(_FLOOR_PIPELINE_TASKS); placeholders=','.join('?' for _ in task_types)
        with get_connection() as connection:
            result=connection.execute(f"""UPDATE job_runs SET status=?, message='Superseded',
                finished_at=?,updated_at=?,locked_by=NULL,lease_expires_at=NULL,heartbeat_at=NULL
                WHERE project_id=? AND floor_id=? AND status=? AND task_type IN ({placeholders})""",
                (JOB_STATUS_CANCELLED,now,now,project_id,floor_id,JOB_STATUS_PENDING,*task_types))
        return int(result.rowcount or 0)

    def cleanup_pending_queue(self) -> dict[str,int]:
        cancelled_duplicates=0; cancelled_stale=0; now=_now()
        with get_connection() as connection:
            rows=connection.execute("""SELECT * FROM job_runs WHERE status=?
                AND task_type IN ('review.refresh','boq.refresh') ORDER BY created_at DESC""",
                (JOB_STATUS_PENDING,)).fetchall()
            seen:set[tuple[Any,Any,Any]]=set(); duplicate_ids:list[str]=[]
            for row in rows:
                scope_floor=None if row['task_type'] in READ_MODEL_TASKS else row['floor_id']
                key=(row['project_id'],scope_floor,row['task_type'])
                if key in seen: duplicate_ids.append(str(row['id']))
                else: seen.add(key)
            if duplicate_ids:
                placeholders=','.join('?' for _ in duplicate_ids)
                result=connection.execute(f"""UPDATE job_runs SET status=?,message='Coalesced',
                    finished_at=?,updated_at=? WHERE id IN ({placeholders}) AND status=?""",
                    (JOB_STATUS_CANCELLED,now,now,*duplicate_ids,JOB_STATUS_PENDING))
                cancelled_duplicates=int(result.rowcount or 0)
            floor_versions={(row['project_id'],row['floor_id']):int(row['crop_version'] or 0)
                for row in connection.execute('SELECT project_id,floor_id,crop_version FROM floor_versions').fetchall()}
            pending=connection.execute("""SELECT id,project_id,floor_id,task_type,input_versions_json
                FROM job_runs WHERE status=? AND floor_id IS NOT NULL""",(JOB_STATUS_PENDING,)).fetchall()
            stale_ids:list[str]=[]
            for row in pending:
                if str(row['task_type']) in READ_MODEL_TASKS: continue
                expected=_json_loads(row['input_versions_json']).get('crop_version')
                if expected is None: continue
                if floor_versions.get((row['project_id'],row['floor_id']),0)>int(expected or 0):
                    stale_ids.append(str(row['id']))
            if stale_ids:
                placeholders=','.join('?' for _ in stale_ids)
                result=connection.execute(f"""UPDATE job_runs SET status=?,message='Superseded',
                    finished_at=?,updated_at=? WHERE id IN ({placeholders}) AND status=?""",
                    (JOB_STATUS_CANCELLED,now,now,*stale_ids,JOB_STATUS_PENDING))
                cancelled_stale=int(result.rowcount or 0)
        return {'coalesced':cancelled_duplicates,'superseded':cancelled_stale}

    def requeue_job(self, job_id: str, *, reset_attempts: bool = True) -> dict | None:
        job=self.get_job(job_id)
        if not job:return None
        if job.get('status') in {JOB_STATUS_PENDING,JOB_STATUS_RUNNING}:return job
        now=_now(); attempts=0 if reset_attempts else int(job.get('attempts') or 0)
        with get_connection() as connection:
            connection.execute("""UPDATE job_runs SET status=?,progress=0,message=?,error_message=NULL,
                result_json='{}',attempts=?,retry_at=NULL,locked_by=NULL,lease_expires_at=NULL,
                heartbeat_at=NULL,started_at=NULL,finished_at=NULL,updated_at=? WHERE id=?""",
                (JOB_STATUS_PENDING,'Waiting',attempts,now,job_id))
            row=connection.execute('SELECT * FROM job_runs WHERE id=?',(job_id,)).fetchone()
        return row_to_dict(row)
    def release_expired_leases(self) -> int:
        now=_now()
        with get_connection() as connection:
            result=connection.execute("""UPDATE job_runs SET status=?,locked_by=NULL,lease_expires_at=NULL,
                heartbeat_at=NULL,retry_at=?,message=?,updated_at=? WHERE status=?
                AND lease_expires_at IS NOT NULL AND lease_expires_at<? AND attempts<max_attempts""",
                (JOB_STATUS_PENDING,now,'Waiting',now,JOB_STATUS_RUNNING,now))
        return int(result.rowcount or 0)
    def claim_next_job(self, *, worker_id: str, task_types: Iterable[str] | None = None, lease_seconds: int = 90) -> dict | None:
        allowed=[item for item in (task_types or []) if item]; self.release_expired_leases()
        now_dt=_now_dt(); now=now_dt.isoformat(); lease=(now_dt+timedelta(seconds=max(15,int(lease_seconds)))).isoformat()
        with get_connection() as connection:
            where=['status = ?','attempts < max_attempts','(retry_at IS NULL OR retry_at <= ?)']; params:list[Any]=[JOB_STATUS_PENDING,now]
            if allowed:
                placeholders=', '.join('?' for _ in allowed); where.append(f'task_type IN ({placeholders})'); params.extend(allowed)
            row=connection.execute(f"""SELECT * FROM job_runs WHERE {' AND '.join(where)}
                ORDER BY {_TASK_PRIORITY_SQL} ASC, created_at ASC LIMIT 1""",tuple(params)).fetchone()
            job=row_to_dict(row)
            if not job:return None
            result=connection.execute("""UPDATE job_runs SET status=?,attempts=attempts+1,locked_by=?,
                lease_expires_at=?,heartbeat_at=?,started_at=COALESCE(started_at,?),message=?,updated_at=?
                WHERE id=? AND status=?""",(JOB_STATUS_RUNNING,worker_id,lease,now,now,'Processing',now,job['id'],JOB_STATUS_PENDING))
            if result.rowcount==0:return None
            claimed=connection.execute('SELECT * FROM job_runs WHERE id=?',(job['id'],)).fetchone()
        return row_to_dict(claimed)
    def heartbeat(self, job_id: str, *, worker_id: str, lease_seconds: int = 90) -> dict | None:
        now_dt=_now_dt();now=now_dt.isoformat();lease=(now_dt+timedelta(seconds=max(15,int(lease_seconds)))).isoformat()
        with get_connection() as connection:
            connection.execute("""UPDATE job_runs SET heartbeat_at=?,lease_expires_at=?,updated_at=?
                WHERE id=? AND status=? AND locked_by=?""",(now,lease,now,job_id,JOB_STATUS_RUNNING,worker_id))
            row=connection.execute('SELECT * FROM job_runs WHERE id=?',(job_id,)).fetchone()
        return row_to_dict(row)
    def update_progress(self, job_id: str, *, progress: int, message: str | None = None, partial_result: dict | None = None) -> dict | None:
        job=self.get_job(job_id)
        if not job:return None
        result=_json_loads(job.get('result_json'))
        if partial_result:result.update(partial_result)
        now=_now()
        with get_connection() as connection:
            connection.execute("""UPDATE job_runs SET progress=?,message=COALESCE(?,message),result_json=?,updated_at=? WHERE id=?""",
                (max(0,min(int(progress),100)),message,_json_dumps(result),now,job_id))
            row=connection.execute('SELECT * FROM job_runs WHERE id=?',(job_id,)).fetchone()
        return row_to_dict(row)
    def complete_job(self, job_id: str, *, result: dict | None = None, message: str = 'Ready') -> dict | None:
        now=_now()
        with get_connection() as connection:
            connection.execute("""UPDATE job_runs SET status=?,progress=100,message=?,result_json=?,error_message=NULL,
                locked_by=NULL,lease_expires_at=NULL,heartbeat_at=NULL,finished_at=?,updated_at=? WHERE id=?""",
                (JOB_STATUS_COMPLETED,message,_json_dumps(result),now,now,job_id))
            row=connection.execute('SELECT * FROM job_runs WHERE id=?',(job_id,)).fetchone()
        return row_to_dict(row)
    def fail_job(self, job_id: str, *, error_message: str, retry: bool = True) -> dict | None:
        job=self.get_job(job_id)
        if not job:return None
        attempts=int(job.get('attempts') or 0);max_attempts=int(job.get('max_attempts') or 1);should_retry=retry and attempts<max_attempts
        now_dt=_now_dt();now=now_dt.isoformat();retry_at=(now_dt+timedelta(seconds=min(60,max(2,attempts*5)))).isoformat() if should_retry else None
        status=JOB_STATUS_PENDING if should_retry else JOB_STATUS_FAILED;message='Waiting' if should_retry else 'Failed';finished=None if should_retry else now
        with get_connection() as connection:
            connection.execute("""UPDATE job_runs SET status=?,message=?,error_message=?,retry_at=?,locked_by=NULL,
                lease_expires_at=NULL,heartbeat_at=NULL,finished_at=?,updated_at=? WHERE id=?""",
                (status,message,error_message[:4000],retry_at,finished,now,job_id))
            row=connection.execute('SELECT * FROM job_runs WHERE id=?',(job_id,)).fetchone()
        return row_to_dict(row)

job_repository=JobRepository()
