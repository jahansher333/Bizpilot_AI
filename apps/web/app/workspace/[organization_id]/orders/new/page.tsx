"use client";

import React, { Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { OrderPos } from "@/components/orders/order-pos";

function NewOrderPageContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";
  const customerId = searchParams?.get("customerId") || undefined;

  return <OrderPos orgId={orgId} initialCustomerId={customerId} />;
}

export default function NewOrderPage() {
  return (
    <Suspense fallback={null}>
      <NewOrderPageContent />
    </Suspense>
  );
}
