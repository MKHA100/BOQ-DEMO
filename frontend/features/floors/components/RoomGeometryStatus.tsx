import type { Room } from "../types";

export function RoomGeometryStatus({ room }: { room: Room }) {
  const points = room.point_count ?? room.display_polygon?.points?.length ?? room.geometry.points.length;
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
      <div className="flex justify-between"><span>Shape</span><strong>{room.shape_type || "Polygon"}</strong></div>
      <div className="mt-1 flex justify-between"><span>Points</span><strong>{points}</strong></div>
      <div className="mt-1 flex justify-between"><span>Boundary</span><strong>{room.boundary_source?.replaceAll("_", " ") || "Unknown"}</strong></div>
      <div className="mt-1 flex justify-between"><span>Stage</span><strong>{room.processing_stage?.replaceAll("_", " ") || "Check"}</strong></div>
    </div>
  );
}
