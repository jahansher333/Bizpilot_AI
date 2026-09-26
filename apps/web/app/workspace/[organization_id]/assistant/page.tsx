"use client";

import React, { Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { AssistantView } from "@/components/assistant/assistant-view";

function AssistantPageContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";
  const initialPrompt = searchParams?.get("prompt") || undefined;

  return (
    <div className="flex flex-1 flex-col h-full overflow-hidden">
      <AssistantView orgId={orgId} userRole="owner" initialPrompt={initialPrompt} />
    </div>
  );
}

export default function AssistantPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-gray-500">Loading assistant...</div>}>
      <AssistantPageContent />
    </Suspense>
  );
}
