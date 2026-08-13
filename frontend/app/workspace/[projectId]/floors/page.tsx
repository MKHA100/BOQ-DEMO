import { FloorsPage } from "@/features/floors/components/FloorsPage";

export default function Page({ params }: { params: { projectId: string } }) {
  return <FloorsPage projectId={params.projectId} />;
}
