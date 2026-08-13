import { UploadPage } from "@/features/upload/components/UploadPage";

export default function Page({ params }: { params: { projectId: string } }) {
  return <UploadPage projectId={params.projectId} />;
}
