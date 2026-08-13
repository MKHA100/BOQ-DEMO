import { SpecificationsPage } from "@/features/specifications/components/SpecificationsPage";

export default function Page({ params }: { params: { projectId: string } }) {
  return <SpecificationsPage projectId={params.projectId} />;
}
