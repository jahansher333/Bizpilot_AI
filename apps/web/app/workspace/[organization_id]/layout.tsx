import { WorkspaceLayout } from "@/components/shell/workspace-layout";

export default async function Layout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ organization_id: string }>;
}) {
  const { organization_id } = await params;
  return <WorkspaceLayout orgId={organization_id}>{children}</WorkspaceLayout>;
}
