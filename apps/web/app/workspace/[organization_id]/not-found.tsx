"use client";

import React from "react";
import { useParams } from "next/navigation";
import { NotFoundState } from "@/components/ui/page-states";

export default function WorkspaceNotFound() {
  const params = useParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";
  return (
    <div className="main page-in">
      <NotFoundState homeHref={orgId ? `/workspace/${orgId}` : "/workspaces"} />
    </div>
  );
}
