"use client";

import React, { Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useOrgRole } from "@/hooks/use-org-role";
import { PaymentsView } from "@/components/payments/payments-view";

function PaymentsPageContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";
  const userRole = useOrgRole(orgId);
  const orderId = searchParams?.get("orderId") || undefined;
  const customerId = searchParams?.get("customerId") || undefined;
  const startRecording = searchParams?.get("record") === "1";

  return (
    <div className="flex-1 overflow-y-auto">
      <PaymentsView
        key={`${orderId ?? ""}-${customerId ?? ""}-${startRecording}`}
        orgId={orgId}
        userRole={userRole}
        initialOrderId={orderId}
        initialCustomerId={customerId}
        startRecording={startRecording}
      />
    </div>
  );
}

export default function PaymentsPage() {
  return (
    <Suspense fallback={null}>
      <PaymentsPageContent />
    </Suspense>
  );
}
