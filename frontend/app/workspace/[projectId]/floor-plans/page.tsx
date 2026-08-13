import { FloorPlansPage } from "@/features/floor-plans/components/FloorPlansPage";

export default function Page({ params }: { params: { projectId: string } }) {
  return <FloorPlansPage projectId={params.projectId} />;
}
