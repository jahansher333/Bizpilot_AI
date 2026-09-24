"use client";

import React from "react";
import { useParams } from "next/navigation";
import { CustomerView } from "@/components/customers/customer-view";

export default function CustomersPage() {
  const params = useParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";

  return (
    <div className="flex-1 overflow-y-auto">
      <CustomerView orgId={orgId} userRole="owner" />
    </div>
  );
}
