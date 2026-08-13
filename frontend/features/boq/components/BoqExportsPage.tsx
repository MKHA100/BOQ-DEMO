import { BoqDashboard } from "./BoqDashboard";

export function BoqExportsPage({ projectId }: { projectId: string }) {
  return <BoqDashboard projectId={projectId} initialPanel="exports" />;
}
