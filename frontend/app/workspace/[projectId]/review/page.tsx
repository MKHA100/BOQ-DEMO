import { ReviewPage } from "@/features/review/components/ReviewPage";

export default function Page({ params }: { params: { projectId: string } }) {
  return <ReviewPage projectId={params.projectId} />;
}
