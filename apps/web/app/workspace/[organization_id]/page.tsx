"use client";

import React from "react";
import { useParams } from "next/navigation";
import { DashboardView } from "@/components/dashboard/dashboard-view";

export default function DashboardPage() {
  const params = useParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";

  return (
    <div className="flex-1 overflow-y-auto">
      <DashboardView orgId={orgId} userRole="owner" />
    </div>
  );
}
