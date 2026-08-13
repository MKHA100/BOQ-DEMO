import { PlatformShell } from "@/features/platform/components/PlatformShell";
import { ProjectCreateForm } from "@/features/project-create/components/ProjectCreateForm";
import { appRoutes } from "@/shared/constants/appRoutes";

export default function CreateProjectPage() {
  return (
    <PlatformShell title="New Project" eyebrow="Project Library" activeNavHref={appRoutes.projects}>
      <ProjectCreateForm />
    </PlatformShell>
  );
}
