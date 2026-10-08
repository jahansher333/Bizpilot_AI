import React from "react";
import { AssistantResponse, ProvenanceMeta } from "@/lib/schemas/assistant";
import { Icon, IconName } from "@/components/ui/icon";

/** What each approved read-only tool reads, in the user's words. */
const TOOL_SOURCE: Record<string, { source: string; area: string; method?: string }> = {
  get_sales_summary: { source: "Orders", area: "sales", method: "Completed orders" },
  get_inventory_status: { source: "Inventory", area: "stock" },
  get_customer_balance: { source: "Orders · Payments", area: "customer balances", method: "Active records only" },
  get_order_details: { source: "Orders", area: "order details" },
  get_top_products: { source: "Orders", area: "product sales", method: "Completed orders" },
  get_expense_summary: { source: "Expenses", area: "expense information" },
  get_payment_summary: { source: "Payments", area: "payment information" },
  get_dashboard_summary: { source: "Orders · Payments · Inventory", area: "the business summary" },
};

export function toolArea(toolName: string): string {
  return TOOL_SOURCE[toolName]?.area ?? "that information";
}

/** "this_week" → "This week"; date ranges pass through. */
export function humanPeriod(period: string): string {
  const s = period.replace(/_/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function asOf(iso?: string): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Karachi", hour: "2-digit", minute: "2-digit" }).format(d);
}

/** Grounding footer: where each figure came from, for which period, and any caveats from the backend. */
export function ProvenanceFooter({ provenance }: { provenance: ProvenanceMeta[] }) {
  if (provenance.length === 0) return null;
  const seen = new Set<string>();
  const chips: { key: string; verified?: boolean; label: string; value: string }[] = [];
  for (const p of provenance) {
    const meta = TOOL_SOURCE[p.source_tool];
    const add = (key: string, label: string, value: string, verified = false) => {
      if (seen.has(key)) return;
      seen.add(key);
      chips.push({ key, label, value, verified });
    };
    add(`src-${p.source_tool}`, "Verified from", meta?.source ?? p.source_tool, true);
    if (p.period_applied) add(`period-${p.period_applied}`, "Period", humanPeriod(p.period_applied));
    if (meta?.method) add(`method-${meta.method}`, "Calculated from", meta.method);
    const time = asOf(p.freshness_timestamp);
    if (time) add("asof", "As of", time);
    for (const c of p.caveats ?? []) add(`caveat-${c}`, "Note", c);
  }
  return (
    <div className="ai-card-f fade-in" aria-label="Where this answer came from">
      {chips.map((c) => (
        <span key={c.key} className={`prov${c.verified ? " verified" : ""}`}>
          {c.verified && <Icon name="check" />}
          {c.label} <b>{c.value}</b>
        </span>
      ))}
    </div>
  );
}

/** One assistant answer: the text, any role denials, and the grounding footer. */
export function AnswerCard({ response }: { response: AssistantResponse }) {
  const denied = Array.from(new Set(response.tool_calls.filter((t) => t.status === "denied").map((t) => t.tool_name)));
  const failed = response.tool_calls.some((t) => t.status === "error");
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {denied.map((tool) => (
        <NoticeCard key={tool} icon="lock" title={`I can’t access ${toolArea(tool)} with your current role.`} body="I can still help with sales, stock, customers and payments." />
      ))}
      <div className="ai-card reveal">
        <div className="ai-card-b" style={{ whiteSpace: "pre-wrap", font: "400 14.5px/22px var(--font)" }}>
          {response.content}
        </div>
        {failed && (
          <div className="t-caption" style={{ padding: "0 16px 12px" }}>
            Some of your records couldn’t be checked, so this answer may be incomplete.
          </div>
        )}
        <ProvenanceFooter provenance={response.provenance} />
      </div>
    </div>
  );
}

export function NoticeCard({ icon, title, body }: { icon: IconName; title: string; body?: string }) {
  return (
    <div className="ai-card reveal">
      <div className="ai-card-b" style={{ flexDirection: "row", gap: 12 }}>
        <span className="dlg-icon neutral" style={{ width: 32, height: 32 }}>
          <Icon name={icon} />
        </span>
        <div>
          <div className="t-h4">{title}</div>
          {body && (
            <p className="t-body-sm secondary" style={{ marginTop: 4 }}>
              {body}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export type FailureKind = "unavailable" | "timeout" | "offline" | "limit";

/** Request failures: calm, never blame the user, always a next step. */
export function FailureNotice({ kind, onRetry, disabled }: { kind: FailureKind; onRetry: () => void; disabled?: boolean }) {
  const copy = {
    unavailable: { cls: "a-warning", icon: "alert" as IconName, title: "BizPilot AI is temporarily unavailable.", body: "Your core business operations are still working." },
    timeout: { cls: "a-neutral", icon: "info" as IconName, title: "That request took longer than expected.", body: "Nothing was changed." },
    offline: { cls: "a-neutral", icon: "info" as IconName, title: "Couldn’t reach BizPilot AI.", body: "Check your connection. Nothing was changed." },
    limit: { cls: "a-neutral", icon: "info" as IconName, title: "Your business has used today’s BizPilot AI questions.", body: "They reset at midnight. Your core business operations are still working." },
  }[kind];
  return (
    <div className={`alert ${copy.cls} reveal`} role="alert">
      <Icon name={copy.icon} />
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div>
          <div className="a-t">{copy.title}</div>
          {copy.body}
        </div>
        {/* Retrying cannot help once the daily allowance is used up. */}
        {kind !== "limit" && (
          <div>
            <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry} disabled={disabled}>
              <Icon name="refresh" size="sm" />
              Retry
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export function failureKind(err: unknown): FailureKind {
  const status = (err as { status?: number } | null)?.status;
  if (status === 504 || status === 408) return "timeout";
  if (status === 429) return "limit";
  if (typeof status === "number") return "unavailable";
  return "offline";
}
