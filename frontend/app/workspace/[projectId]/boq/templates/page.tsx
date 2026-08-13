import { BoqTemplatesPage } from "@/features/boq/components/BoqTemplatesPage";

export default function Page({ params }: { params: { projectId: string } }) {
  return <BoqTemplatesPage projectId={params.projectId} />;
}
