"use client";

import React from "react";
import { useParams } from "next/navigation";
import { CatalogView } from "@/components/catalog/catalog-view";
import { useOrgRole } from "@/hooks/use-org-role";

export default function CatalogPage() {
  const params = useParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";
  const userRole = useOrgRole(orgId);

  return <CatalogView organizationId={orgId} userRole={userRole} />;
}
