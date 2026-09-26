"use client";

import React from "react";
import { useParams } from "next/navigation";
import { AssistantView } from "@/components/assistant/assistant-view";

export default function AssistantPage() {
  const params = useParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";

  return (
    <div className="flex flex-1 flex-col h-full overflow-hidden">
      <AssistantView orgId={orgId} userRole="owner" />
    </div>
  );
}
