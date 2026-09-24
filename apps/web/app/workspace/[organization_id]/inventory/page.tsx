import { InventoryView } from "@/components/inventory/inventory-view";

interface InventoryPageProps {
  params: Promise<{ organization_id: string }>;
  searchParams?: Promise<{ role?: string }>;
}

export default async function InventoryPage({ params, searchParams }: InventoryPageProps) {
  const { organization_id } = await params;
  const search = searchParams ? await searchParams : undefined;
  const role = search?.role || "owner";

  return <InventoryView orgId={organization_id} userRole={role} />;
}
