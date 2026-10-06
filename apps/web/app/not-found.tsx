import React from "react";
import { NotFoundState } from "@/components/ui/page-states";

export default function NotFound() {
  return (
    <main className="main page-in" style={{ maxWidth: 640, margin: "0 auto", paddingTop: 80 }}>
      <NotFoundState homeHref="/workspaces" />
    </main>
  );
}
