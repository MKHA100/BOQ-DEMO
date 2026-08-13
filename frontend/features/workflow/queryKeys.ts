export const workflowQueryKeys = {
  root: (projectId: string) => ["workflow", projectId] as const,
  summary: (projectId: string) => ["workflow", projectId, "summary"] as const,
  floors: (projectId: string) => ["workflow", projectId, "floors"] as const,
  floor: (projectId: string, floorId: string) => ["workflow", projectId, "floor", floorId] as const,
  crop: (projectId: string, floorId: string) => ["workflow", projectId, "floor", floorId, "crop"] as const,
  calibration: (projectId: string, floorId: string) => ["workflow", projectId, "floor", floorId, "calibration"] as const,
  elements: (projectId: string, floorId: string) => ["workflow", projectId, "floor", floorId, "elements"] as const,
  walls: (projectId: string, floorId: string) => ["workflow", projectId, "floor", floorId, "walls"] as const,
  rooms: (projectId: string, floorId: string) => ["workflow", projectId, "floor", floorId, "rooms"] as const,
  roomInterpretation: (projectId: string, floorId: string) => ["workflow", projectId, "floor", floorId, "room-interpretation"] as const,
  review: (projectId: string, floorId?: string) => ["workflow", projectId, "review", floorId ?? "all"] as const,
  boq: (projectId: string, floorId?: string) => ["workflow", projectId, "boq", floorId ?? "all"] as const,
};
