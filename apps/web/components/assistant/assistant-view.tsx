"use client";

import React, { useEffect, useRef, useState } from "react";
import { AssistantMessage, AssistantResponse } from "@/lib/schemas/assistant";
import { useAssistantQuery } from "@/hooks/use-assistant";
import { useOptionalAuth } from "@/hooks/use-auth";
import { Icon, IconName } from "@/components/ui/icon";
import { AnswerCard, FailureKind, FailureNotice, failureKind } from "@/components/assistant/assistant-parts";

interface AssistantViewProps {
  orgId: string;
  userRole?: string; // "owner", "manager", "staff"
  token?: string;
  initialPrompt?: string;
}

type Turn =
  | { id: number; kind: "user"; text: string }
  | { id: number; kind: "answer"; response: AssistantResponse }
  | { id: number; kind: "failure"; failure: FailureKind; question: string };

/** Staff may not read expenses (backend `expenses:read`), so that prompt is shown locked. */
const PROMPTS: { text: string; icon: IconName; staffLocked?: boolean }[] = [
  { text: "How are sales doing today?", icon: "orders" },
  { text: "Which products are low on stock?", icon: "inventory" },
  { text: "How much did customers pay this week?", icon: "payments" },
  { text: "What are my expenses this month?", icon: "expenses", staffLocked: true },
  { text: "Show my top-selling products.", icon: "products" },
  { text: "Give me today’s business summary.", icon: "dashboard" },
];

/** The backend reads the last 10 turns; send only finished question/answer pairs. */
function history(turns: Turn[]): AssistantMessage[] {
  return turns.flatMap((t): AssistantMessage[] =>
    t.kind === "user" ? [{ role: "user", content: t.text }] : t.kind === "answer" ? [{ role: "assistant", content: t.response.content }] : []
  );
}

/** Design canvas "26 · BizPilot AI". Read-only; the conversation lives only in memory. */
export function AssistantView({ orgId, userRole = "staff", token, initialPrompt }: AssistantViewProps) {
  const staff = userRole !== "owner" && userRole !== "manager";
  const orgName = useOptionalAuth()?.organizations.find((o) => o.id === orgId)?.display_name;
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const nextId = useRef(1);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const initialSent = useRef(false);
  const mutation = useAssistantQuery(orgId, token);
  const busy = mutation.isPending;

  useEffect(() => {
    if (typeof endRef.current?.scrollIntoView === "function") endRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, busy]);

  function ask(question: string, prior: Turn[] = turns) {
    const text = question.trim();
    if (!text || busy) return;
    const withQuestion: Turn[] = [...prior, { id: nextId.current++, kind: "user", text }];
    setTurns(withQuestion);
    setDraft("");
    mutation.mutate(
      { message: text, conversation_history: history(prior) },
      {
        onSuccess: (response) => setTurns((cur) => [...cur, { id: nextId.current++, kind: "answer", response }]),
        onError: (err) => setTurns((cur) => [...cur, { id: nextId.current++, kind: "failure", failure: failureKind(err), question: text }]),
      }
    );
  }

  function retry(failureId: number, question: string) {
    // Drop the failed attempt (and its question) and ask again from the same point.
    const idx = turns.findIndex((t) => t.id === failureId);
    ask(question, turns.slice(0, Math.max(0, idx - 1)));
  }

  useEffect(() => {
    if (initialPrompt && !initialSent.current) {
      initialSent.current = true;
      ask(initialPrompt, []);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPrompt]);

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0, height: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, padding: "14px 32px", borderBottom: "1px solid var(--border)", background: "var(--surface)", flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
          <span className="orb" aria-hidden="true" />
          <div style={{ minWidth: 0 }}>
            <h1 className="t-h3">BizPilot AI</h1>
            <p className="t-body-sm secondary">Ask questions about your business using your real business data.</p>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span className="badge b-neutral square">
            <Icon name="lock" />
            Read-only
          </span>
          <span className="badge b-brand square">
            <Icon name="check" />
            Grounded in your BizPilot data
          </span>
          {turns.length > 0 && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={busy}
              onClick={() => {
                setTurns([]);
                inputRef.current?.focus();
              }}
            >
              <Icon name="plus" size="sm" />
              New chat
            </button>
          )}
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 0, overflow: "auto", background: "var(--bg)" }}>
        <div style={{ maxWidth: 780, margin: "0 auto", padding: "32px 24px 24px", display: "flex", flexDirection: "column", gap: 22 }} aria-live="polite" aria-busy={busy}>
          {turns.length === 0 && (
            <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 24, paddingTop: 32 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 14, alignItems: "flex-start" }}>
                <span className="orb lg pulse" aria-hidden="true" />
                <h2 className="t-h1">What would you like to know about your business?</h2>
                <p className="t-body secondary">
                  I answer from {orgName ? `${orgName}’s` : "your"} orders, inventory, payments and expenses — and I’ll always show where a number came from.
                </p>
              </div>
              <div className="stagger" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(220px, 100%), 1fr))", gap: 10 }}>
                {PROMPTS.map((p, i) => {
                  const locked = staff && p.staffLocked;
                  return (
                    <button key={p.text} type="button" className="prompt-card" disabled={locked || busy} aria-describedby={locked ? `pl-${i}` : undefined} onClick={() => ask(p.text)}>
                      <Icon name={p.icon} />
                      <span style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <span>{p.text}</span>
                        {locked && (
                          <span className="t-caption" id={`pl-${i}`} style={{ display: "inline-flex", gap: 4, alignItems: "center" }}>
                            <Icon name="lock" size="sm" style={{ color: "var(--text-muted)", margin: 0 }} />
                            Owners &amp; Managers
                          </span>
                        )}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {turns.map((t) =>
            t.kind === "user" ? (
              <div key={t.id} className="bubble-user reveal">
                {t.text}
              </div>
            ) : (
              <div key={t.id} style={{ display: "grid", gridTemplateColumns: "28px minmax(0, 1fr)", gap: 12, alignItems: "start" }}>
                <span className="orb" aria-hidden="true" />
                {t.kind === "answer" ? <AnswerCard response={t.response} /> : <FailureNotice kind={t.failure} onRetry={() => retry(t.id, t.question)} disabled={busy} />}
              </div>
            )
          )}

          {busy && (
            <div style={{ display: "grid", gridTemplateColumns: "28px minmax(0, 1fr)", gap: 12, alignItems: "start" }}>
              <span className="orb pulse" aria-hidden="true" />
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }} role="status">
                <div style={{ display: "flex", alignItems: "center", gap: 10, height: 28 }}>
                  <span className="dots" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </span>
                  <span className="t-body-sm secondary">Checking your records…</span>
                </div>
                <div className="ai-card" aria-hidden="true">
                  <div className="ai-card-b">
                    <span className="skel" style={{ height: 14, width: "70%" }} />
                    <span className="skel" style={{ height: 14, width: "45%" }} />
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div style={{ borderTop: "1px solid var(--border)", background: "var(--surface)", padding: "14px 24px 16px" }}>
        <form
          style={{ maxWidth: 780, margin: "0 auto", display: "flex", flexDirection: "column", gap: 8 }}
          onSubmit={(e) => {
            e.preventDefault();
            ask(draft);
          }}
        >
          <div className="ig" style={{ height: 48, borderRadius: 10 }}>
            <span className="pre plain">
              <Icon name="ai" style={{ color: "var(--brand-text)" }} />
            </span>
            <input ref={inputRef} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Ask about sales, stock, customers, payments…" aria-label="Ask BizPilot AI" maxLength={2000} style={{ fontSize: 15 }} />
            <span className="post plain" style={{ paddingRight: 6 }}>
              <button type="submit" className="btn btn-primary btn-sm icon-btn" aria-label="Send" disabled={!draft.trim() || busy}>
                <Icon name="arrowRight" />
              </button>
            </span>
          </div>
          <p className="t-caption" style={{ textAlign: "center" }}>
            Read-only. BizPilot AI can’t create or change records. Conversations aren’t saved on this device.
          </p>
        </form>
      </div>
    </div>
  );
}
