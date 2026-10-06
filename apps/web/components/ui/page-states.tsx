"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/ui/icon";

/** Design "18 · Error states": what happened, and what you can do next. */
export function NotFoundState({ homeHref }: { homeHref: string }) {
  return (
    <div className="card empty" role="alert" style={{ padding: "56px 24px" }}>
      <span className="empty-art">
        <Icon name="search" />
      </span>
      <h1 className="t-h2">We couldn’t find that page</h1>
      <p className="t-body-sm secondary" style={{ maxWidth: 360 }}>
        The link may be old, or the record was removed from this workspace.
      </p>
      <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
        <Link className="btn btn-primary btn-sm" href={homeHref}>
          Go to dashboard
        </Link>
      </div>
    </div>
  );
}

/** Short, shareable reference for support; never the raw error message. */
export function errorReference(error: { digest?: string }): string {
  return (error.digest ?? "").slice(0, 8).toUpperCase() || "CLIENT";
}

export function ServerErrorState({ error, onRetry, homeHref }: { error: Error & { digest?: string }; onRetry: () => void; homeHref: string }) {
  return (
    <div className="card empty" role="alert" style={{ padding: "56px 24px" }}>
      <span className="empty-art" style={{ color: "var(--danger)", background: "var(--danger-bg)", borderColor: "var(--danger-border)" }}>
        <Icon name="alert" />
      </span>
      <h1 className="t-h2">Something went wrong on our side</h1>
      <p className="t-body-sm secondary" style={{ maxWidth: 380 }}>
        Your data is safe. Try again in a moment; if it keeps happening, share code <span className="mono">{errorReference(error)}</span> with support.
      </p>
      <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
          <Icon name="refresh" size="sm" />
          Retry
        </button>
        <Link className="btn btn-ghost btn-sm" href={homeHref}>
          Dashboard
        </Link>
      </div>
    </div>
  );
}

/** Tracks the browser's connection; true while offline. */
export function useOffline(): boolean {
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    const update = () => setOffline(typeof navigator !== "undefined" && navigator.onLine === false);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return offline;
}

export function OfflineNotice() {
  const offline = useOffline();
  if (!offline) return null;
  return (
    <div className="alert a-warning" role="status" style={{ margin: "12px 32px 0" }}>
      <Icon name="alert" />
      <div>
        <div className="a-t">You’re offline</div>
        We can’t reach BizPilot. Anything you were typing is kept on this screen — try again when you’re back online.
      </div>
    </div>
  );
}
