"use client";

import React from "react";
import { useParams } from "next/navigation";
import { OrdersView } from "@/components/orders/orders-view";

export default function OrdersPage() {
  const params = useParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";

  return (
    <div className="flex-1 overflow-y-auto">
      <OrdersView orgId={orgId} userRole="owner" />
    </div>
  );
}
