import { ProjectOverviewPage } from "@/features/project-overview/components/ProjectOverviewPage";

export default function WorkspacePage({ params }: { params: { projectId: string } }) {
  return <ProjectOverviewPage projectId={params.projectId} />;
}
