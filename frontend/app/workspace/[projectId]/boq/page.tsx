import { BoqPage } from "@/features/boq/components/BoqPage";

export default function Page({ params }: { params: { projectId: string } }) {
  return <BoqPage projectId={params.projectId} />;
}
