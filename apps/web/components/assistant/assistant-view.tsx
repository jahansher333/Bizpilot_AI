"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  AssistantMessage,
  AssistantResponse,
  getSuggestedPrompts,
} from "@/lib/schemas/assistant";
import { useAssistantQuery } from "@/hooks/use-assistant";

interface AssistantViewProps {
  orgId: string;
  userRole?: string; // "owner", "manager", "staff"
  token?: string;
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
}: AssistantViewProps) {
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [lastPrompt, setLastPrompt] = useState<string | null>(null);

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

  const handleSendMessage = (textToSend?: string) => {
    const text = (textToSend ?? inputMessage).trim();
    if (!text || assistantMutation.isPending) return;

    const userMsgId = `user_${Date.now()}`;
    const newMsg: MessageItem = {
      id: userMsgId,
      role: "user",
      content: text,
    };

    setMessages((prev) => [...prev, newMsg]);
    setInputMessage("");
    setLastPrompt(text);

    // Build bounded conversation history (transient, max 6 items)
    const historyPayload: AssistantMessage[] = messages.slice(-6).map((m) => ({
      role: m.role,
      content: m.content,
    }));

    assistantMutation.mutate(
      {
        message: text,
        conversation_history: historyPayload,
      },
      {
        onSuccess: (data: AssistantResponse) => {
          setMessages((prev) => [
            ...prev,
            {
              id: `asst_${Date.now()}`,
              role: "assistant",
              content: data.content,
              responseMeta: data,
            },
          ]);
        },
        onError: (err: Error) => {
          setMessages((prev) => [
            ...prev,
            {
              id: `asst_err_${Date.now()}`,
              role: "assistant",
              content:
                err.message ||
                "The AI assistant encountered a temporary connectivity issue. Core operations remain unaffected.",
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
    <div className="flex h-full max-h-screen flex-col bg-gray-50">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between border-b border-gray-200 bg-white px-6 py-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-gray-900">
              BizPilot Copilot
            </h1>
            <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-800">
              Read-Only Business Copilot (P0)
            </span>
          </div>
          <p className="mt-0.5 text-xs text-gray-500">
            Grounded in your PostgreSQL business records. Role:{" "}
            <span className="font-semibold uppercase text-gray-700">{userRole}</span>
          </p>
        </div>

        {messages.length > 0 && (
          <button
            type="button"
            onClick={handleClearThread}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Clear Thread
          </button>
        )}
      </header>

      {/* Main Conversation Container */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-4">
          {/* Welcome State when no messages */}
          {messages.length === 0 && (
            <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
              <div className="max-w-2xl">
                <h2 className="text-lg font-semibold text-gray-900">
                  Welcome to BizPilot Copilot
                </h2>
                <p className="mt-1 text-sm text-gray-600">
                  I can answer factual questions about your sales, inventory stock levels,
                  recorded payments, customer balances, and operational summaries.
                </p>
                <div className="mt-3 rounded-md bg-blue-50 p-3 text-xs text-blue-800">
                  <span className="font-semibold">Note:</span> BizPilot AI is strictly
                  read-only. To record orders, adjust inventory, or record payments,
                  please use the workspace forms.
                </div>
              </div>

              <div className="mt-6">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Suggested Business Questions
                </h3>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {suggestedPrompts.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => handleSendMessage(prompt)}
                      className="flex items-center justify-between rounded-lg border border-gray-200 bg-gray-50 p-3 text-left text-xs font-medium text-gray-800 transition hover:border-blue-300 hover:bg-blue-50/50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <span>{prompt}</span>
                      <span className="text-blue-600 font-bold ml-2">→</span>
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
                className={`max-w-2xl rounded-xl p-4 shadow-sm ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white"
                    : msg.isError
                    ? "border border-red-200 bg-red-50 text-red-900"
                    : "border border-gray-200 bg-white text-gray-900"
                }`}
              >
                <div className="mb-1 flex items-center justify-between gap-4 text-[11px] opacity-75">
                  <span className="font-semibold uppercase tracking-wider">
                    {msg.role === "user" ? "You" : "BizPilot AI"}
                  </span>
                  {msg.responseMeta?.model && (
                    <span className="text-[10px] text-gray-400">
                      {msg.responseMeta.model}
                    </span>
                  )}
                </div>

                <div className="whitespace-pre-wrap text-sm leading-relaxed">
                  {msg.content}
                </div>

                {/* Grounding & Provenance Metadata Citation */}
                {msg.responseMeta && (
                  <div className="mt-3 border-t border-gray-100 pt-2">
                    {msg.responseMeta.provenance &&
                      msg.responseMeta.provenance.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-[11px] font-medium text-gray-500">
                            Grounded by:
                          </span>
                          {msg.responseMeta.provenance.map((p, idx) => (
                            <span
                              key={idx}
                              className="inline-flex items-center rounded bg-green-50 px-2 py-0.5 text-[10px] font-semibold text-green-700 border border-green-200"
                            >
                              {p.source_tool}
                              {p.period_applied ? ` (${p.period_applied})` : ""}
                            </span>
                          ))}
                        </div>
                      )}

                    {msg.responseMeta.tool_calls &&
                      msg.responseMeta.tool_calls.some((t) => t.status === "denied") && (
                        <div className="mt-1 inline-flex items-center rounded bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-800 border border-amber-200">
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
              <div className="flex items-center gap-2 rounded-xl border border-gray-200 bg-white p-3.5 shadow-sm text-xs font-medium text-gray-600">
                <span className="h-2 w-2 animate-ping rounded-full bg-blue-600" />
                <span>Consulting deterministic business records...</span>
              </div>
            </div>
          )}

          {/* Failure & Retry Action */}
          {assistantMutation.isError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800 flex items-center justify-between">
              <span>
                Unable to complete request. Please check your connection or try again.
              </span>
              <button
                type="button"
                onClick={handleRetry}
                className="ml-3 rounded bg-red-100 px-2.5 py-1 font-semibold text-red-900 hover:bg-red-200"
              >
                Retry
              </button>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Composer */}
      <footer className="border-t border-gray-200 bg-white p-4">
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
              className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm text-gray-900 placeholder-gray-500 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
            />
            <button
              type="submit"
              disabled={!inputMessage.trim() || assistantMutation.isPending}
              className="inline-flex items-center justify-center rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-blue-300"
            >
              Send
            </button>
          </form>
          <p className="mt-2 text-center text-[11px] text-gray-400">
            BizPilot AI answers are grounded in database evidence. Conversational context is transient.
          </p>
        </div>
      </footer>
    </div>
  );
}
