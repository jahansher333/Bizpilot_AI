"use client";

import React, { Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useOrgRole } from "@/hooks/use-org-role";
import { OrdersView } from "@/components/orders/orders-view";

function OrdersPageContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";
  const userRole = useOrgRole(orgId);
  const customerId = searchParams?.get("customerId") || undefined;

  return (
    <div className="flex-1 overflow-y-auto">
      <OrdersView key={customerId ?? "all"} orgId={orgId} userRole={userRole} initialCustomerId={customerId} />
    </div>
  );
}

export default function OrdersPage() {
  return (
    <Suspense fallback={null}>
      <OrdersPageContent />
    </Suspense>
  );
}
