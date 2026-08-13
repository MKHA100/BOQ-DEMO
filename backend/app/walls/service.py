from __future__ import annotations

import math
import json
from typing import Any

from app.core.errors import bad_request,not_found
from app.database.session import get_connection
from app.jobs.job_service import job_service
from app.walls.geometry import bbox_center,bbox_centerline,farthest_line,line_length,point_line_distance
from app.walls.repo import walls_repository
from app.walls.rules import deduction,gross_area,opening_area
from app.walls.topology_service import wall_topology_service
from app.walls.validation_service import wall_validation_service
from app.workflow.repo import workflow_repository


class WallsService:
    def geometry_context(self, project_id: str, floor_id: str) -> dict[str, Any]:
        return walls_repository.geometry_context(project_id, floor_id)

    def get_state(self,project:dict,floor_id:str|None=None)->dict:
        floors=[]; active=job_service.list_project_jobs(project_id=project["id"],active_only=True,limit=200)
        for row in walls_repository.floor_rows(project["id"]):
            rect=((row.get("coordinates") or {}).get("original_rect") or {})
            floor_walls=walls_repository.list_walls(project["id"],row["id"])
            confirmed=bool(floor_walls) and all(bool(item.get("user_confirmed")) or item.get("status")=="confirmed" for item in floor_walls)
            floor_jobs=[job for job in active if job.get("floor_id")==row["id"] and job.get("category")=="walls"]
            floors.append({"id":row["id"],"name":row["name"],"level_index":int(row["level_index"]),"crop_version":int(row.get("crop_version") or 0),"scale_version":int(row.get("scale_version") or 0),"element_version":int(row.get("element_version") or 0),"wall_version":int(row.get("wall_version") or 0),"mm_per_pixel":row.get("mm_per_pixel"),"drawing_url":f"/api/v1/projects/{project['id']}/floor-plans/floors/{row['id']}/crop-asset" if row.get("crop_asset_key") else None,"drawing_width":float(rect.get("width") or 1),"drawing_height":float(rect.get("height") or 1),"effective_height_mm":float(row.get("wall_height_mm") or project.get("default_wall_height_mm") or 2700),"active_jobs":floor_jobs,"walls_confirmed":confirmed,"wall_status":"processing" if floor_jobs else ("confirmed" if confirmed else "not_ready")})
        selected=floor_id or (floors[0]["id"] if floors else None)
        walls=walls_repository.list_walls(project["id"],selected) if selected else []
        openings=walls_repository.list_opening_elements(project["id"],selected) if selected else []
        selected_floor=next((item for item in floors if item["id"]==selected),None)
        validation=self._validation(walls,openings,selected_floor)
        warning_map=validation.get("warnings_by_wall") or {}
        for wall in walls:
            wall["source"]="model" if wall.get("source_element_id") else "manual"
            wall["manually_edited"]=self._is_manually_edited(wall)
            wall["validation_warnings"]=warning_map.get(str(wall["id"]),[])
        return {"project_id":project["id"],"floors":floors,"selected_floor_id":selected,"walls":walls,"openings":openings,"validation":validation}

    def build_lines(self,project_id:str,floor_id:str,created_by:str|None=None)->dict:
        floor=next((item for item in walls_repository.floor_rows(project_id) if item["id"]==floor_id),None)
        if not floor:raise not_found("Floor not found.")
        with get_connection() as connection:
            versions=workflow_repository.increment_floor_version(connection,project_id,floor_id,"wall_version")
            element_rows=connection.execute("""SELECT * FROM elements e
                WHERE project_id=? AND floor_id=? AND element_type='wall' AND excluded=0
                  AND (COALESCE(e.is_manual,0)=1 OR COALESCE(e.generated_status,'current')='current')
                  AND (e.crop_version IS NULL OR e.crop_version=(SELECT crop_version FROM floor_versions fv
                       WHERE fv.project_id=e.project_id AND fv.floor_id=e.floor_id))""",
                (project_id,floor_id)).fetchall()
        elements=[]
        for row in element_rows:
            element=dict(row)
            element["geometry"]=json.loads(element.get("geometry_json") or "{}")
            elements.append(element)
        existing=walls_repository.list_wall_records(project_id,floor_id,include_inactive=True)
        by_source={str(item.get("source_element_id")):item for item in existing if item.get("source_element_id")}
        mm_per_pixel=float(floor.get("mm_per_pixel") or 0) or None
        height_mm=float(floor.get("wall_height_mm") or 2700)
        source_versions=self._versions(versions)
        created=[]; refreshed=[]; suppressed=0; rejected=0
        accepted_elements=[]
        for element in elements:
            if not self._wall_candidate_is_plausible(element, mm_per_pixel):
                rejected += 1
                continue
            accepted_elements.append(element)
        active_source_ids={str(element["id"]) for element in accepted_elements}
        for element in accepted_elements:
            source_id=str(element["id"]); geometry=element["geometry"]
            generated=bbox_centerline(geometry)
            minor=min(abs(float(geometry.get("width") or 0)),abs(float(geometry.get("height") or 0)))
            thickness_mm=minor*mm_per_pixel if minor>0 and mm_per_pixel else None
            current=by_source.get(source_id)
            if current and current.get("generated_status")=="rejected":
                suppressed+=1; continue
            if current:
                manual=self._is_manually_edited(current)
                refreshed.append(walls_repository.reconcile_generated_wall(
                    project_id=project_id,floor_id=floor_id,wall_id=current["id"],
                    generated_centerline=generated,centerline=None if manual else generated,
                    thickness_mm=thickness_mm,height_mm=height_mm,
                    wall_version=int(versions["wall_version"]),source_versions=source_versions,
                    item_number=element.get("item_number"),
                    preserve_user_confirmation=manual,
                ))
            else:
                created.append(walls_repository.create_wall(
                    project_id=project_id,floor_id=floor_id,centerline=generated,
                    generated_centerline=generated,wall_type=None,classification=None,
                    thickness_mm=thickness_mm,height_mm=height_mm,
                    wall_version=int(versions["wall_version"]),created_by=created_by,
                    source_versions=source_versions,source_element_id=source_id,
                    item_number=element.get("item_number"),status="ready",user_confirmed=False,
                ))
        superseded=walls_repository.supersede_missing_generated(project_id,floor_id,active_source_ids)
        return {"created":len(created),"refreshed":len(refreshed),"rejected":rejected,"suppressed":suppressed,"superseded":superseded,"walls":walls_repository.list_walls(project_id,floor_id)}

    def process_floor(self,project_id:str,floor_id:str,created_by:str|None=None)->dict:
        """Run the complete idempotent wall pipeline after model detection."""
        built=self.build_lines(project_id,floor_id,created_by)
        fixed=self.auto_fix(project_id,floor_id,created_by)
        return {
            "created":built.get("created",0),
            "refreshed":built.get("refreshed",0),
            "rejected":built.get("rejected",0),
            "suppressed":built.get("suppressed",0),
            "superseded":built.get("superseded",0),
            "topology":fixed.get("topology",{}),
            "validation":fixed.get("validation",{}),
            "walls":fixed.get("walls",[]),
        }

    def auto_fix(self,project_id:str,floor_id:str,created_by:str|None=None)->dict:
        floor=next((item for item in walls_repository.floor_rows(project_id) if item["id"]==floor_id),None)
        if not floor:raise not_found("Floor not found.")
        walls=walls_repository.list_walls(project_id,floor_id)
        openings=walls_repository.list_opening_elements(project_id,floor_id)
        mm_per_pixel=float(floor.get("mm_per_pixel") or 0) or None
        prepared=[]
        for wall in walls:
            item=dict(wall)
            item["manually_edited"]=self._is_manually_edited(wall)
            item["source"]="model" if wall.get("source_element_id") else "manual"
            # Generated walls are active/confirmed by default for the user, but
            # topology still needs to clean them on first run. Only a real
            # geometry deviation from generated_centerline is protected.
            if wall.get("source_element_id") and not item["manually_edited"]:
                item["user_confirmed"]=False
            if mm_per_pixel and float(wall.get("thickness_mm") or 0)>0:
                item["detected_thickness_px"]=float(wall["thickness_mm"])/mm_per_pixel
            prepared.append(item)
        topology=wall_topology_service.clean(
            prepared,
            drawing_width=float(floor.get("drawing_width") or 0) or None,
            drawing_height=float(floor.get("drawing_height") or 0) or None,
            preserve_manual=True,
            openings=openings,
            mm_per_pixel=mm_per_pixel,
        )
        with get_connection() as connection:
            versions=workflow_repository.increment_floor_version(connection,project_id,floor_id,"wall_version")
        source_versions=self._versions(versions)
        existing_by_id={str(item["id"]):item for item in walls}
        for cleaned in topology.get("walls") or []:
            wall_id=str(cleaned["id"]); existing=existing_by_id.get(wall_id)
            if not existing or cleaned.get("manually_edited"):
                continue
            line=cleaned.get("centerline") or existing.get("centerline") or {}
            walls_repository.reconcile_generated_wall(
                project_id=project_id,floor_id=floor_id,wall_id=wall_id,
                generated_centerline=line,centerline=line,
                thickness_mm=cleaned.get("thickness_mm") or existing.get("thickness_mm"),
                height_mm=existing.get("height_mm"),wall_version=int(versions["wall_version"]),
                source_versions=source_versions,item_number=existing.get("item_number"),
                preserve_user_confirmation=False,
            )
        for removed_id,survivor_id in (topology.get("merged_wall_ids") or {}).items():
            walls_repository.mark_merged(project_id,floor_id,str(removed_id),str(survivor_id))
        self.classify(project_id,floor_id)
        self.auto_assign_openings(project_id,floor_id)
        self.calculate(project_id,floor_id)
        current=walls_repository.list_walls(project_id,floor_id)
        current_openings=walls_repository.list_opening_elements(project_id,floor_id)
        validation=self._validation(current,current_openings,floor)
        self._apply_validation_status(project_id,floor_id,current,validation,int(versions["wall_version"]))
        current=walls_repository.list_walls(project_id,floor_id)
        anchor_id=str(current[0]["id"]) if current else floor_id
        jobs=self._downstream(project_id,floor_id,anchor_id,versions,created_by,geometry_changed=True)
        return {"topology":topology.get("summary") or topology.get("stats") or {},"validation":validation,"walls":current,"jobs":jobs}

    def create(self,project_id:str,floor_id:str,payload:dict,created_by:str|None)->dict:
        floor=next((item for item in walls_repository.floor_rows(project_id) if item["id"]==floor_id),None)
        if not floor:raise not_found("Floor not found.")
        line=payload.get("centerline") or {}
        with get_connection() as connection:
            versions=workflow_repository.increment_floor_version(connection,project_id,floor_id,"wall_version")
        existing=walls_repository.list_walls(project_id,floor_id)
        known=[float(item.get("thickness_mm") or 0) for item in existing if float(item.get("thickness_mm") or 0)>0]
        thickness=payload.get("thickness_mm") or (sum(known)/len(known) if known else 100.0)
        record=walls_repository.create_wall(
            project_id=project_id,floor_id=floor_id,centerline=line,generated_centerline=line,
            wall_type=payload.get("wall_type"),classification=payload.get("classification") or "internal",
            thickness_mm=float(thickness),height_mm=float(payload.get("height_mm") or floor.get("wall_height_mm") or 2700),
            wall_version=int(versions["wall_version"]),created_by=created_by,
            source_versions=self._versions(versions),status="confirmed",user_confirmed=True,
        )
        self.calculate(project_id,floor_id,[record["id"]])
        jobs=self._downstream(project_id,floor_id,record["id"],versions,created_by,geometry_changed=True)
        return {"record":walls_repository.get_wall(project_id,floor_id,record["id"]),"versions":self._versions(versions),"jobs":jobs}

    def delete(self,project_id:str,floor_id:str,wall_id:str,created_by:str|None)->dict:
        wall=walls_repository.get_wall(project_id,floor_id,wall_id)
        if not wall:raise not_found("Wall not found.")
        with get_connection() as connection:
            versions=workflow_repository.increment_floor_version(connection,project_id,floor_id,"wall_version")
        walls_repository.delete_wall(project_id,floor_id,wall_id)
        jobs=self._downstream(project_id,floor_id,wall_id,versions,created_by,geometry_changed=True)
        return {"deleted":True,"wall_id":wall_id,"suppressed":bool(wall.get("source_element_id")),"versions":self._versions(versions),"jobs":jobs}

    def confirm_all(self,project_id:str,floor_id:str,created_by:str|None)->dict:
        if not any(item["id"]==floor_id for item in walls_repository.floor_rows(project_id)):
            raise not_found("Floor not found.")
        with get_connection() as connection:
            versions=workflow_repository.increment_floor_version(connection,project_id,floor_id,"wall_version")
        count=walls_repository.confirm_all(project_id,floor_id,int(versions["wall_version"]))
        walls=walls_repository.list_walls(project_id,floor_id)
        return {"confirmed":count,"walls":walls,"versions":self._versions(versions)}

    def classify(self,project_id:str,floor_id:str)->dict:
        walls=walls_repository.list_walls(project_id,floor_id)
        if not walls:return {"updated":0}
        points=[point for wall in walls for point in ((wall.get("centerline") or {}).get("start",{}),(wall.get("centerline") or {}).get("end",{})) if point]
        min_x=min(float(point["x"]) for point in points); max_x=max(float(point["x"]) for point in points); min_y=min(float(point["y"]) for point in points); max_y=max(float(point["y"]) for point in points)
        tolerance=max(max_x-min_x,max_y-min_y)*0.06
        with get_connection() as connection:versions=workflow_repository.increment_floor_version(connection,project_id,floor_id,"wall_version")
        updated=0
        for wall in walls:
            line=wall.get("centerline") or {}; midpoint={"x":((line.get("start") or {}).get("x",0)+(line.get("end") or {}).get("x",0))/2,"y":((line.get("start") or {}).get("y",0)+(line.get("end") or {}).get("y",0))/2}
            external=min(abs(midpoint["x"]-min_x),abs(midpoint["x"]-max_x),abs(midpoint["y"]-min_y),abs(midpoint["y"]-max_y))<=tolerance
            walls_repository.update_wall(project_id,floor_id,wall["id"],{"classification":"external" if external else "internal","boundary_role":"outer" if external else "internal","status":"confirmed" if wall.get("user_confirmed") else "ready"},int(versions["wall_version"]),user_confirmed=bool(wall.get("user_confirmed"))); updated+=1
        return {"updated":updated}

    def auto_assign_openings(self,project_id:str,floor_id:str)->dict:
        walls=walls_repository.list_walls(project_id,floor_id); openings=walls_repository.list_opening_elements(project_id,floor_id)
        assigned=0
        for element in openings:
            if not walls:break
            center=bbox_center(element.get("geometry") or {})
            wall=min(walls,key=lambda item:point_line_distance(center,item.get("centerline") or {"start":{"x":0,"y":0},"end":{"x":0,"y":0}}))
            geometry=element.get("geometry") or {}
            threshold=max(12.0,min(abs(float(geometry.get("width") or 0)),abs(float(geometry.get("height") or 0)))*2.0)
            if point_line_distance(center,wall.get("centerline") or {"start":{"x":0,"y":0},"end":{"x":0,"y":0}})>threshold:
                continue
            width=self._number((element.get("dimensions") or {}).get("width_mm"))
            height=self._number((element.get("dimensions") or {}).get("height_mm"))
            area=opening_area(width,height)
            walls_repository.assign_opening(
                project_id=project_id,floor_id=floor_id,wall_id=wall["id"],element=element,
                width_mm=width,height_mm=height,opening_area_m2=area,
                deduction_area_m2=deduction(area),created_by=None,
            )
            assigned+=1
        return {"assigned":assigned}

    def calculate(self,project_id:str,floor_id:str,wall_ids:list[str]|None=None)->dict:
        floor=next((item for item in walls_repository.floor_rows(project_id) if item["id"]==floor_id),None)
        if not floor:raise not_found("Floor not found.")
        mm_per_pixel=float(floor.get("mm_per_pixel") or 0); default_height=float(floor.get("wall_height_mm") or 2700)
        walls=walls_repository.list_walls(project_id,floor_id)
        if wall_ids:walls=[wall for wall in walls if wall["id"] in wall_ids]
        with get_connection() as connection:versions=workflow_repository.increment_floor_version(connection,project_id,floor_id,"wall_version")
        updated=[]
        for wall in walls:
            length_mm=line_length(wall.get("centerline") or {"start":{"x":0,"y":0},"end":{"x":0,"y":0}})*mm_per_pixel if mm_per_pixel else None
            height_mm=float(wall.get("height_override_mm") or wall.get("height_mm") or default_height)
            gross=gross_area(length_mm,height_mm); deduction_total=round(sum(float(item.get("deduction_area_m2") or 0) for item in wall.get("openings",[])),4); net=round(max((gross or 0)-deduction_total,0),4) if gross is not None else None
            status="confirmed" if wall.get("user_confirmed") else ("ready" if length_mm and wall.get("classification") and wall.get("thickness_mm") else "needs_review")
            updated.append(walls_repository.update_wall(project_id,floor_id,wall["id"],{"length_mm":length_mm,"height_mm":height_mm,"gross_area_m2":gross,"deduction_area_m2":deduction_total,"net_area_m2":net,"is_stale":0,"status":status},int(versions["wall_version"]),user_confirmed=bool(wall.get("user_confirmed"))))
        return {"updated":len(updated),"walls":updated}

    def update(self,*,project_id:str,floor_id:str,wall_id:str,payload:dict[str,Any],created_by:str|None)->dict:
        wall=walls_repository.get_wall(project_id,floor_id,wall_id)
        if not wall:raise not_found("Wall not found.")
        updates={}
        if payload.get("centerline") is not None:updates["centerline"]=payload["centerline"]
        for key in ("classification","wall_type","thickness_mm","side_1_finish","side_2_finish"):
            if key in payload:updates[key]=payload[key]
        if payload.get("use_floor_height") is True:updates.update({"height_override_mm":None,"height_source":"floor"})
        elif payload.get("height_override_mm") is not None:updates.update({"height_override_mm":payload["height_override_mm"],"height_source":"wall"})
        if payload.get("review_status") is not None:updates["status"]=payload["review_status"]
        updates["is_stale"]=1
        with get_connection() as connection:versions=workflow_repository.increment_floor_version(connection,project_id,floor_id,"wall_version")
        record=walls_repository.update_wall(project_id,floor_id,wall_id,updates,int(versions["wall_version"]),user_confirmed=True)
        self.calculate(project_id,floor_id,[wall_id])
        jobs=self._downstream(project_id,floor_id,wall_id,versions,created_by,geometry_changed=payload.get("centerline") is not None)
        return {"record":walls_repository.get_wall(project_id,floor_id,wall_id),"jobs":jobs,"versions":self._versions(versions)}

    def assign_opening(self,project_id:str,floor_id:str,wall_id:str,element_id:str,created_by:str|None)->dict:
        wall=walls_repository.get_wall(project_id,floor_id,wall_id); element=next((item for item in walls_repository.list_opening_elements(project_id,floor_id) if item["id"]==element_id),None)
        if not wall or not element:raise not_found("Wall or opening not found.")
        old_wall_id=element.get("wall_id")
        width=self._number((element.get("dimensions") or {}).get("width_mm")); height=self._number((element.get("dimensions") or {}).get("height_mm")); area=opening_area(width,height); deduct=deduction(area)
        relation=walls_repository.assign_opening(project_id=project_id,floor_id=floor_id,wall_id=wall_id,element=element,width_mm=width,height_mm=height,opening_area_m2=area,deduction_area_m2=deduct,created_by=created_by)
        affected=list({item for item in (old_wall_id,wall_id) if item}); self.calculate(project_id,floor_id,affected)
        with get_connection() as connection:versions=workflow_repository.increment_floor_version(connection,project_id,floor_id,"wall_version")
        jobs=[]
        for affected_wall in affected:jobs.extend(self._downstream(project_id,floor_id,affected_wall,versions,created_by,geometry_changed=True))
        return {"relation":relation,"walls":[walls_repository.get_wall(project_id,floor_id,item) for item in affected],"jobs":jobs}

    def refresh_opening_deduction(
        self,
        project_id: str,
        floor_id: str,
        element_id: str,
        wall_id: str | None = None,
    ) -> dict:
        """Refresh one opening relation from the canonical element dimensions."""
        element = next(
            (item for item in walls_repository.list_opening_elements(project_id, floor_id) if item["id"] == element_id),
            None,
        )
        if not element:
            raise not_found("Opening not found.")
        resolved_wall_id = wall_id or element.get("wall_id")
        if not resolved_wall_id or not walls_repository.get_wall(project_id, floor_id, resolved_wall_id):
            return {"updated": 0, "wall_id": resolved_wall_id, "element_id": element_id}
        width = self._number((element.get("dimensions") or {}).get("width_mm"))
        height = self._number((element.get("dimensions") or {}).get("height_mm"))
        area = opening_area(width, height)
        relation = walls_repository.assign_opening(
            project_id=project_id,
            floor_id=floor_id,
            wall_id=resolved_wall_id,
            element=element,
            width_mm=width,
            height_mm=height,
            opening_area_m2=area,
            deduction_area_m2=deduction(area),
            created_by=None,
        )
        calculated = self.calculate(project_id, floor_id, [resolved_wall_id])
        return {
            "updated": 1,
            "relation": relation,
            "walls": calculated.get("walls", []),
            "wall_id": resolved_wall_id,
            "element_id": element_id,
        }

    def split(self,project_id:str,floor_id:str,wall_id:str,payload:dict,created_by:str|None)->dict:
        wall=walls_repository.get_wall(project_id,floor_id,wall_id)
        if not wall:raise not_found("Wall not found.")
        line=wall.get("centerline") or {}; start=line["start"]; end=line["end"]
        point=payload.get("point") or {"x":start["x"]+(end["x"]-start["x"])*payload.get("ratio",0.5),"y":start["y"]+(end["y"]-start["y"])*payload.get("ratio",0.5)}
        with get_connection() as connection:versions=workflow_repository.increment_floor_version(connection,project_id,floor_id,"wall_version")
        first=walls_repository.update_wall(project_id,floor_id,wall_id,{"centerline":{"start":start,"end":point},"is_stale":1,"status":"needs_review"},int(versions["wall_version"]))
        second=walls_repository.create_wall(project_id=project_id,floor_id=floor_id,centerline={"start":point,"end":end},wall_type=wall.get("wall_type"),classification=wall.get("classification"),thickness_mm=wall.get("thickness_mm"),height_mm=wall.get("height_mm"),wall_version=int(versions["wall_version"]),created_by=created_by,source_versions=self._versions(versions))
        self.calculate(project_id,floor_id,[first["id"],second["id"]])
        jobs = self._downstream(project_id, floor_id, first["id"], versions, created_by, geometry_changed=True)
        jobs.extend(self._downstream(project_id, floor_id, second["id"], versions, created_by, geometry_changed=True))
        return {"walls":[walls_repository.get_wall(project_id,floor_id,first["id"]),walls_repository.get_wall(project_id,floor_id,second["id"])], "jobs": jobs}

    def merge(self,project_id:str,floor_id:str,wall_id:str,other_wall_id:str,created_by:str|None)->dict:
        first=walls_repository.get_wall(project_id,floor_id,wall_id); second=walls_repository.get_wall(project_id,floor_id,other_wall_id)
        if not first or not second:raise not_found("Wall not found.")
        merged=farthest_line([first.get("centerline") or {},second.get("centerline") or {}])
        with get_connection() as connection:versions=workflow_repository.increment_floor_version(connection,project_id,floor_id,"wall_version")
        walls_repository.update_wall(project_id,floor_id,wall_id,{"centerline":merged,"is_stale":1,"status":"needs_review"},int(versions["wall_version"]))
        walls_repository.move_openings(project_id,floor_id,other_wall_id,wall_id)
        walls_repository.delete_wall(project_id,floor_id,other_wall_id)
        self.calculate(project_id,floor_id,[wall_id])
        jobs = self._downstream(project_id, floor_id, wall_id, versions, created_by, geometry_changed=True)
        return {"wall":walls_repository.get_wall(project_id,floor_id,wall_id), "jobs": jobs}

    def restore(self,project_id:str,floor_id:str,wall_id:str,created_by:str|None)->dict:
        with get_connection() as connection:versions=workflow_repository.increment_floor_version(connection,project_id,floor_id,"wall_version")
        record=walls_repository.restore_generated(project_id,floor_id,wall_id,int(versions["wall_version"])); self.calculate(project_id,floor_id,[wall_id]); return {"record":record}

    def _downstream(self,project_id:str,floor_id:str,wall_id:str,versions:dict,created_by:str|None,geometry_changed:bool)->list[dict]:
        # A wall can create or remove a complete room, so geometry changes must
        # rebuild the floor, not only rooms that already have a wall relation.
        # Rebuild existing dependent rooms immediately and also run the full
        # cell pass so a wall change can create or remove a room.
        tasks=["rooms.rebuild_touching", "rooms.prepare_lines"] if geometry_changed else ["review.refresh","boq.refresh"]
        with get_connection() as connection:
            current_versions = workflow_repository.get_versions(connection, project_id, floor_id)
        version_values = self._versions(current_versions or versions)
        jobs=[]
        for task in tasks:
            payload={"entity_type":"wall","entity_id":wall_id,"wall_id":wall_id}
            job,created=job_service.enqueue(task_type=task,project_id=project_id,floor_id=floor_id,entity_id=wall_id,payload=payload,input_versions=version_values,created_by=created_by); jobs.append({**job,"created":created})
        return jobs

    def _validation(self,walls:list[dict],openings:list[dict],floor:dict|None)->dict:
        width=height=None
        validation_walls=[dict(item) for item in walls]
        if floor:
            rect=((floor.get("coordinates") or {}).get("original_rect") or {})
            width=float(floor.get("drawing_width") or rect.get("width") or 0) or None
            height=float(floor.get("drawing_height") or rect.get("height") or 0) or None
            mm_per_pixel=float(floor.get("mm_per_pixel") or 0) or None
            if mm_per_pixel:
                for item in validation_walls:
                    if float(item.get("thickness_mm") or 0)>0:
                        item["detected_thickness_px"]=float(item["thickness_mm"])/mm_per_pixel
        result=wall_validation_service.validate(
            validation_walls,openings=openings,drawing_width=width,drawing_height=height
        )
        summary=result.get("summary") or {}
        result["blocking_issues"]=int(summary.get("error_count") or 0)
        result["warning_count"]=int(summary.get("warning_count") or 0)
        return result

    @staticmethod
    def _wall_candidate_is_plausible(element: dict, mm_per_pixel: float | None) -> bool:
        """Reject obvious annotation strokes before they enter wall topology."""
        if bool(element.get("is_manual")):
            return True
        geometry=element.get("geometry") or {}
        try:
            width=abs(float(geometry.get("width") or 0))
            height=abs(float(geometry.get("height") or 0))
        except (TypeError,ValueError):
            return False
        major=max(width,height); minor=min(width,height)
        if major < 8 or minor <= 0 or major / max(minor,1e-6) < 1.8:
            return False
        if mm_per_pixel and mm_per_pixel > 0:
            length_mm=major*mm_per_pixel
            thickness_mm=minor*mm_per_pixel
            if length_mm < 150 or not 45 <= thickness_mm <= 750:
                return False
        return True

    @staticmethod
    def _apply_validation_status(
        project_id:str,
        floor_id:str,
        walls:list[dict],
        validation:dict,
        wall_version:int,
    )->None:
        error_ids={
            str(wall_id)
            for warning in validation.get("warnings") or []
            if isinstance(warning,dict) and warning.get("severity")=="error"
            for wall_id in warning.get("wall_ids") or []
        }
        for wall in walls:
            if wall.get("user_confirmed"):
                continue
            status="needs_review" if str(wall["id"]) in error_ids else "confirmed"
            if wall.get("status")==status:
                continue
            walls_repository.update_wall(
                project_id,floor_id,str(wall["id"]),{"status":status},wall_version,
                user_confirmed=False,
            )

    @staticmethod
    def _is_manually_edited(wall:dict)->bool:
        if not wall.get("source_element_id"):
            return True
        current=wall.get("centerline") or {}
        generated=wall.get("generated_centerline") or {}
        try:
            direct=math.dist((float(current["start"]["x"]),float(current["start"]["y"])),(float(generated["start"]["x"]),float(generated["start"]["y"])))+math.dist((float(current["end"]["x"]),float(current["end"]["y"])),(float(generated["end"]["x"]),float(generated["end"]["y"])))
            reverse=math.dist((float(current["start"]["x"]),float(current["start"]["y"])),(float(generated["end"]["x"]),float(generated["end"]["y"])))+math.dist((float(current["end"]["x"]),float(current["end"]["y"])),(float(generated["start"]["x"]),float(generated["start"]["y"])))
            return min(direct,reverse)>1.0
        except (KeyError,TypeError,ValueError):
            return False

    @staticmethod
    def _number(value:Any)->float|None:
        try:return float(value) if value not in (None,"") else None
        except (TypeError,ValueError):return None
    @staticmethod
    def _versions(versions:dict)->dict:return {key:int(value or 0) for key,value in versions.items() if key.endswith("_version")}


walls_service=WallsService()
