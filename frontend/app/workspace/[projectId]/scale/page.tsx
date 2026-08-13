import { ScalePage } from "@/features/scale/components/ScalePage";

export default function Page({ params }: { params: { projectId: string } }) {
  return <ScalePage projectId={params.projectId} />;
}
