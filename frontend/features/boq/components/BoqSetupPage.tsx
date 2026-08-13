import { BoqDashboard } from "./BoqDashboard";

export function BoqSetupPage({ projectId }: { projectId: string }) {
  return <BoqDashboard projectId={projectId} initialPanel="settings" />;
}
