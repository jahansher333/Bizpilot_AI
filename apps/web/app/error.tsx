"use client";

import React from "react";
import { ServerErrorState } from "@/components/ui/page-states";

export default function Error({ error, retry, reset }: { error: Error & { digest?: string }; retry?: () => void; reset?: () => void }) {
  return (
    <main className="main page-in" style={{ maxWidth: 640, margin: "0 auto", paddingTop: 80 }}>
      <ServerErrorState error={error} onRetry={() => (retry ?? reset)?.()} homeHref="/workspaces" />
    </main>
  );
}
