"use client";

import React, { Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { OrderDetail } from "@/components/orders/order-detail";
import { useOrgRole } from "@/hooks/use-org-role";

function OrderDetailPageContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";
  const orderId = typeof params?.orderId === "string" ? params.orderId : "";
  const userRole = useOrgRole(orgId);
  const initialAction = searchParams?.get("action") === "correct" ? "correct" : null;

  return <OrderDetail key={`${orderId}-${userRole}`} orgId={orgId} orderId={orderId} userRole={userRole} initialAction={initialAction} />;
}

export default function OrderDetailPage() {
  return (
    <Suspense fallback={null}>
      <OrderDetailPageContent />
    </Suspense>
  );
}
