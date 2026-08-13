import { BoqDashboard } from "./BoqDashboard";

export function BoqPage({ projectId }: { projectId: string }) {
  return <BoqDashboard projectId={projectId} />;
}
