import { WallsPage } from "@/features/walls/components/WallsPage";

export default function Page({ params }: { params: { projectId: string } }) {
  return <WallsPage projectId={params.projectId} />;
}
