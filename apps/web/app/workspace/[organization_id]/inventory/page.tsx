"use client";

import React from "react";
import { useParams } from "next/navigation";
import { InventoryView } from "@/components/inventory/inventory-view";
import { useOrgRole } from "@/hooks/use-org-role";

export default function InventoryPage() {
  const params = useParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";
  const userRole = useOrgRole(orgId);

  return <InventoryView orgId={orgId} userRole={userRole} />;
}
