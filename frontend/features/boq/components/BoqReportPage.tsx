import { BoqDashboard } from "./BoqDashboard";

export function BoqReportPage({ projectId }: { projectId: string }) {
  return <BoqDashboard projectId={projectId} />;
}
