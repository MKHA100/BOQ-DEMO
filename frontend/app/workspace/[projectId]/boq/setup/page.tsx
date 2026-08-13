import { BoqSetupPage } from "@/features/boq/components/BoqSetupPage";

export default function Page({ params }: { params: { projectId: string } }) {
  return <BoqSetupPage projectId={params.projectId} />;
}
