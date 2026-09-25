"use client";

import React from "react";
import { useParams } from "next/navigation";
import { ExpensesView } from "@/components/expenses/expenses-view";

export default function ExpensesPage() {
  const params = useParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";

  return (
    <div className="flex-1 overflow-y-auto">
      <ExpensesView orgId={orgId} userRole="owner" />
    </div>
  );
}
