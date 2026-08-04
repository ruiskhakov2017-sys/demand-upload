import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setCsrfToken, streamAiMessage } from "./client";

describe("AI streaming client", () => {
  beforeEach(() => {
    const values = new Map<string, string>();
    vi.stubGlobal("sessionStorage", {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
      clear: () => values.clear()
    });
  });
  afterEach(() => {
    sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("parses named SSE events and sends CSRF without exposing credentials", async () => {
    setCsrfToken("csrf-test-token");
    const payload = [
      'event: connected\ndata: {"run_id":"run-1"}\n\n',
      'event: message.delta\ndata: {"text":"Hello"}\n\n',
      'event: message.completed\ndata: {"answer":"Done"}\n\n'
    ].join("");
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      expect(headers.get("X-CSRF-Token")).toBe("csrf-test-token");
      expect(init?.credentials).toBe("include");
      expect(String(init?.body)).not.toContain("api_key");
      return new Response(payload, { status: 200, headers: { "Content-Type": "text/event-stream" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    const events: Array<[string, Record<string, unknown>]> = [];

    await streamAiMessage(
      "conversation-1",
      { content: "test", model_profile: "FAST", idempotency_key: "1234567890abcdef" },
      (event, data) => events.push([event, data])
    );

    expect(events.map(([event]) => event)).toEqual(["connected", "message.delta", "message.completed"]);
    expect(events[1][1].text).toBe("Hello");
  });

  it("returns the exact backend error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "OPENAI_NOT_CONFIGURED" }), {
      status: 503,
      headers: { "Content-Type": "application/json" }
    })));
    await expect(streamAiMessage(
      "conversation-1",
      { content: "test", model_profile: "FAST", idempotency_key: "1234567890abcdef" },
      () => undefined
    )).rejects.toThrow("OPENAI_NOT_CONFIGURED");
  });
});
