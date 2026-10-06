"use client";

import React from "react";
import { useParams } from "next/navigation";
import { SettingsView } from "@/components/settings/settings-view";

export default function SettingsPage() {
  const params = useParams();
  const orgId = typeof params?.organization_id === "string" ? params.organization_id : "";

  return (
    <div className="flex-1 overflow-y-auto">
      <SettingsView key={orgId} orgId={orgId} />
    </div>
  );
}
