import { ModelReviewPage } from "@/features/model-review/components/ModelReviewPage";

export default function Page({ params }: { params: { projectId: string } }) {
  return <ModelReviewPage projectId={params.projectId} />;
}
