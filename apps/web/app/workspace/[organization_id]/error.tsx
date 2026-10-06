"use client";

import React from "react";
import { useParams } from "next/navigation";
import { ServerErrorState } from "@/components/ui/page-states";

export default function WorkspaceError({ error, retry, reset }: { error: Error & { digest?: string }; retry?: () => void; reset?: () => void }) {
  const params = useParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";
  return (
    <div className="main page-in">
      <ServerErrorState error={error} onRetry={() => (retry ?? reset)?.()} homeHref={orgId ? `/workspace/${orgId}` : "/workspaces"} />
    </div>
  );
}
