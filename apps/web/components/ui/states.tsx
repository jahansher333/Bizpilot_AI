import React from "react";
import { Icon, IconName } from "@/components/ui/icon";

interface EmptyStateProps {
  icon: IconName;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

/** Design `.empty`: what is missing, why, and the next step. */
export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="empty">
      <span className="empty-art">
        <Icon name={icon} />
      </span>
      <h3 className="t-h3">{title}</h3>
      {description && (
        <p className="t-body secondary" style={{ maxWidth: 420 }}>
          {description}
        </p>
      )}
      {action && <div style={{ marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center" }}>{action}</div>}
    </div>
  );
}

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

/** Load failure: says what happened and offers a retry, never a blank page. */
export function ErrorState({ title = "Couldn’t load this", message, onRetry }: ErrorStateProps) {
  return (
    <div className="alert a-danger" role="alert">
      <Icon name="alert" />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="a-t">{title}</div>
        {message && <div className="secondary">{message}</div>}
      </div>
      {onRetry && (
        <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
          <Icon name="refresh" size="sm" />
          Try again
        </button>
      )}
    </div>
  );
}

/** Shown when the role may not see a page (deep link or 403), instead of a blank page. */
export function RestrictedState({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return (
    <div className="card">
      <EmptyState icon="lock" title={title} description={description} action={action} />
    </div>
  );
}

export function Skeleton({ width = "100%", height = 14, radius }: { width?: number | string; height?: number | string; radius?: number }) {
  return <span className="skel" aria-hidden="true" style={{ display: "block", width, height, borderRadius: radius }} />;
}
