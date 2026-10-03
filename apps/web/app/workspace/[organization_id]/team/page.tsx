"use client";

import React from "react";
import { useParams } from "next/navigation";
import { TeamView } from "@/components/team/team-view";

export default function TeamPage() {
  const params = useParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";

  return (
    <div className="flex-1 overflow-y-auto">
      <TeamView orgId={orgId} />
    </div>
  );
}
