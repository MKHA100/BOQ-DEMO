import { ReviewClassificationPage } from "@/features/review/components/ReviewClassificationPage";

export default function Page({ params }: { params: { projectId: string } }) {
  return <ReviewClassificationPage projectId={params.projectId} />;
}
