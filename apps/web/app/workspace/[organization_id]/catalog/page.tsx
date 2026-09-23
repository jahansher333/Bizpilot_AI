import { CatalogView } from "@/components/catalog/catalog-view";

interface CatalogPageProps {
  params: Promise<{ organization_id: string }>;
  searchParams?: Promise<{ role?: string }>;
}

export default async function CatalogPage({ params, searchParams }: CatalogPageProps) {
  const { organization_id } = await params;
  const search = searchParams ? await searchParams : undefined;
  const role = (search?.role as "owner" | "manager" | "staff") || "owner";

  return <CatalogView organizationId={organization_id} initialRole={role} />;
}
