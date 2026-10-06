"use client";

import React from "react";
import { useParams } from "next/navigation";
import { CustomerDetail } from "@/components/customers/customer-detail";
import { useOrgRole } from "@/hooks/use-org-role";

export default function CustomerDetailPage() {
  const params = useParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";
  const customerId = typeof params?.customerId === "string" ? params.customerId : "";
  const userRole = useOrgRole(orgId);

  return <CustomerDetail orgId={orgId} customerId={customerId} userRole={userRole} />;
}
