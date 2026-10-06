import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { sendAssistantQuery } from "@/lib/api/assistant";

describe("sendAssistantQuery", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    localStorage.clear();
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts to the backend's /api/organizations/{id}/ai/chat route (no /v1 prefix)", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ content: "ok", tool_calls: [], provenance: [], model: "m", latency_ms: 1 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    await sendAssistantQuery("org-1", { message: "Sales today?", conversation_history: [] }, "access-1");

    const [url, init] = fetchMock.mock.calls[0];
    expect(new URL(String(url), "http://localhost").pathname).toBe("/api/organizations/org-1/ai/chat");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ message: "Sales today?", conversation_history: [] });
  });
});
