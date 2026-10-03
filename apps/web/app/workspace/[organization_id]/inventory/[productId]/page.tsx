"use client";

import React, { Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { StockDetail } from "@/components/inventory/stock-detail";
import { useOrgRole } from "@/hooks/use-org-role";

function StockDetailPageContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";
  const productId = typeof params?.productId === "string" ? params.productId : "";
  const userRole = useOrgRole(orgId);
  const action = searchParams?.get("action");
  const initialAction = action === "adjust" || action === "correct" || action === "opening" ? action : null;

  return <StockDetail key={`${productId}-${userRole}`} orgId={orgId} productId={productId} userRole={userRole} initialAction={initialAction} />;
}

export default function StockDetailPage() {
  return (
    <Suspense fallback={null}>
      <StockDetailPageContent />
    </Suspense>
  );
}
