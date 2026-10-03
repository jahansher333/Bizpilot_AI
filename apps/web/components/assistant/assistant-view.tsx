"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  AssistantMessage,
  AssistantResponse,
  getSuggestedPrompts,
} from "@/lib/schemas/assistant";
import { useAssistantQuery } from "@/hooks/use-assistant";
import { BizPilotLogo } from "@/components/ui/bizpilot-logo";

interface AssistantViewProps {
  orgId: string;
  userRole?: string; // "owner", "manager", "staff"
  token?: string;
  initialPrompt?: string;
}

interface MessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  responseMeta?: AssistantResponse;
  isError?: boolean;
}

export function AssistantView({
  orgId,
  userRole = "owner",
  token,
  initialPrompt,
}: AssistantViewProps) {
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [lastPrompt, setLastPrompt] = useState<string | null>(null);
  const initialSentRef = useRef(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const suggestedPrompts = getSuggestedPrompts(userRole);
  const assistantMutation = useAssistantQuery(orgId, token);

  const scrollToBottom = () => {
    if (typeof messagesEndRef.current?.scrollIntoView === "function") {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, assistantMutation.isPending]);

  useEffect(() => {
    if (initialPrompt && !initialSentRef.current && messages.length === 0) {
      initialSentRef.current = true;
      handleSendMessage(initialPrompt);
    }
  }, [initialPrompt]);

  const handleSendMessage = (textToSend?: string) => {
    const text = (textToSend !== undefined ? textToSend : inputMessage).trim();
    if (!text || assistantMutation.isPending) return;

    setLastPrompt(text);
    const userMsgId = `user-${Date.now()}`;
    const newMessages: MessageItem[] = [
      ...messages,
      { id: userMsgId, role: "user", content: text },
    ];
    setMessages(newMessages);
    setInputMessage("");

    // Prepare message payload
    const queryPayload: AssistantMessage[] = newMessages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    assistantMutation.mutate(
      { message: text, conversation_history: queryPayload },
      {
        onSuccess: (data: AssistantResponse) => {
          setMessages((prev) => [
            ...prev,
            {
              id: `assistant-${Date.now()}`,
              role: "assistant",
              content: data.content,
              responseMeta: data,
            },
          ]);
        },
        onError: (err: unknown) => {
          const errMessage =
            err instanceof Error ? err.message : "Failed to obtain response from assistant.";
          setMessages((prev) => [
            ...prev,
            {
              id: `err-${Date.now()}`,
              role: "assistant",
              content: errMessage,
              isError: true,
            },
          ]);
        },
      }
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleRetry = () => {
    if (lastPrompt) {
      handleSendMessage(lastPrompt);
    }
  };

  const handleClearThread = () => {
    setMessages([]);
    setLastPrompt(null);
  };

  return (
    <div className="flex h-full max-h-screen flex-col bg-surface">
      {/* Header (Stitch Flagship Intelligence Top Bar) */}
      <header className="flex flex-wrap items-center justify-between border-b border-surface-container-high/60 bg-surface/90 px-6 py-4 shadow-xs backdrop-blur-md">
        <div>
          <div className="flex items-center gap-2.5">
            <BizPilotLogo size={24} className="w-6 h-6" />
            <h1 className="font-headline-sm text-headline-sm font-semibold tracking-tight text-on-surface">
              BizPilot Copilot
            </h1>
            <span className="rounded-full bg-primary-fixed px-2.5 py-0.5 font-data-badge text-data-badge font-semibold text-primary">
              Read-Only Business Copilot (P0)
            </span>
          </div>
          <p className="mt-0.5 font-label-md text-label-md text-on-surface-variant">
            Grounded in your PostgreSQL business records. Role:{" "}
            <span className="font-semibold uppercase text-on-surface">{userRole}</span>
          </p>
        </div>

        {messages.length > 0 && (
          <button
            type="button"
            onClick={handleClearThread}
            className="rounded-xl border border-outline-variant/60 bg-surface-container-lowest px-3 py-1.5 font-label-md text-label-md font-semibold text-on-surface hover:bg-surface-container transition-colors shadow-xs"
          >
            Clear Thread
          </button>
        )}
      </header>

      {/* Main Conversation Container */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
        <div className="mx-auto max-w-4xl space-y-4">
          {/* Welcome State when no messages */}
          {messages.length === 0 && (
            <div className="rounded-2xl border border-surface-container-high/80 bg-surface-container-lowest p-6 sm:p-8 shadow-xs relative overflow-hidden">
              <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-primary via-secondary to-tertiary" />
              <div className="max-w-2xl">
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-data-badge text-data-badge px-2 py-0.5 rounded bg-surface-container-high text-primary font-semibold">
                    Read-only assistant
                  </span>
                </div>
                <h2 className="font-headline-lg text-headline-lg font-bold text-on-surface tracking-tight">
                  Welcome to BizPilot Copilot
                </h2>
                <p className="mt-2 font-body-md text-body-md text-on-surface-variant leading-relaxed">
                  I can answer factual questions about your sales, inventory stock levels,
                  recorded payments, customer balances, and operational summaries.
                </p>
                <div className="mt-4 rounded-xl bg-surface-container-low p-3.5 text-xs text-on-surface-variant flex items-center gap-2 border border-surface-container-high/40">
                  <span className="font-semibold text-primary font-mono">ℹ️ Note:</span>
                  <span>
                    BizPilot AI is strictly read-only. To record orders, adjust inventory, or record payments,
                    please use the workspace forms.
                  </span>
                </div>
              </div>

              <div className="mt-6">
                <h3 className="font-label-caps text-label-caps uppercase text-outline tracking-wider text-[11px]">
                  Suggested Business Questions
                </h3>
                <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
                  {suggestedPrompts.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => handleSendMessage(prompt)}
                      className="flex items-center justify-between rounded-xl border border-surface-container-high/70 bg-surface-container-low/60 p-3.5 text-left text-xs font-medium text-on-surface transition hover:border-primary hover:bg-surface-container-high shadow-xs group"
                    >
                      <span className="font-body-sm text-body-sm">{prompt}</span>
                      <span className="text-primary font-bold ml-2 group-hover:translate-x-0.5 transition-transform">
                        →
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Messages List */}
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${
                msg.role === "user" ? "items-end" : "items-start"
              }`}
            >
              <div
                className={`max-w-2xl rounded-2xl p-4 sm:p-5 shadow-xs ${
                  msg.role === "user"
                    ? "bg-primary-container text-on-primary rounded-tr-xs font-body-md shadow-sm"
                    : msg.isError
                    ? "border border-error/30 bg-error-container/30 text-on-error-container"
                    : "border border-surface-container-high/80 bg-surface-container-lowest text-on-surface"
                }`}
              >
                <div className="mb-2 flex items-center justify-between gap-4 text-[11px] opacity-80">
                  <span className="font-semibold uppercase tracking-wider font-label-caps">
                    {msg.role === "user" ? "You" : "BizPilot AI"}
                  </span>
                  {msg.responseMeta?.model && (
                    <span className="font-mono text-[10px] text-outline">
                      {msg.responseMeta.model}
                    </span>
                  )}
                </div>

                <div className="whitespace-pre-wrap font-body-md text-body-md leading-relaxed">
                  {msg.content}
                </div>

                {/* Grounding & Provenance Metadata Citation */}
                {msg.responseMeta && (
                  <div className="mt-3 border-t border-surface-container-high/60 pt-2.5">
                    {msg.responseMeta.provenance &&
                      msg.responseMeta.provenance.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="font-label-md text-[11px] font-medium text-on-surface-variant">
                            Grounded by:
                          </span>
                          {msg.responseMeta.provenance.map((p, idx) => (
                            <span
                              key={idx}
                              className="inline-flex items-center rounded-lg bg-surface-container px-2 py-0.5 font-data-cell text-[10px] font-semibold text-primary border border-outline-variant/40"
                            >
                              {p.source_tool}
                              {p.period_applied ? ` (${p.period_applied})` : ""}
                            </span>
                          ))}
                        </div>
                      )}

                    {msg.responseMeta.tool_calls &&
                      msg.responseMeta.tool_calls.some((t) => t.status === "denied") && (
                        <div className="mt-1.5 inline-flex items-center rounded-lg bg-amber-100 px-2 py-0.5 font-data-badge text-[10px] font-semibold text-amber-900 border border-amber-300">
                          Role restriction: restricted data omitted
                        </div>
                      )}
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Loading Indicator */}
          {assistantMutation.isPending && (
            <div className="flex items-start">
              <div className="flex items-center gap-2 rounded-2xl border border-surface-container-high bg-surface-container-lowest p-4 shadow-xs text-xs font-medium text-on-surface-variant">
                <span className="h-2 w-2 animate-ping rounded-full bg-primary" />
                <span>Consulting deterministic business records...</span>
              </div>
            </div>
          )}

          {/* Failure & Retry Action */}
          {assistantMutation.isError && (
            <div className="rounded-2xl border border-error/30 bg-error-container/20 p-4 text-xs text-on-error-container flex items-center justify-between">
              <span>
                Unable to complete request. Please check your connection or try again.
              </span>
              <button
                type="button"
                onClick={handleRetry}
                className="ml-3 rounded-lg bg-error-container px-3 py-1 font-semibold text-on-error-container hover:bg-error-container/80 transition-colors"
              >
                Retry
              </button>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Composer (Stitch Floating Input Ribbon) */}
      <footer className="border-t border-surface-container-high/60 bg-surface-container-lowest p-4 shadow-sm">
        <div className="mx-auto max-w-4xl">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-center gap-2"
          >
            <input
              ref={inputRef}
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={assistantMutation.isPending}
              placeholder="Ask a question about your sales, stock, customers, or payments..."
              className="flex-1 rounded-xl border border-outline-variant/60 bg-surface-container-low px-4 py-2.5 font-body-md text-sm text-on-surface placeholder:text-outline shadow-inner focus:border-primary focus:bg-surface-container-lowest focus:outline-none focus:ring-2 focus:ring-primary/10 disabled:opacity-50 transition-all"
            />
            <button
              type="submit"
              disabled={!inputMessage.trim() || assistantMutation.isPending}
              className="inline-flex items-center justify-center rounded-xl bg-primary hover:bg-primary-container px-5 py-2.5 font-body-sm text-sm font-semibold text-on-primary shadow-xs transition-all active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40"
            >
              Send
            </button>
          </form>
          <p className="mt-2 text-center font-label-md text-[11px] text-outline">
            BizPilot AI answers are grounded in database evidence. Conversational context is transient.
          </p>
        </div>
      </footer>
    </div>
  );
}
