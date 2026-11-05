import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchGenerations } from "@/lib/library-api";

/**
 * Library API contract (G12): the songs list must be able to ask for one workspace.
 * The Studio library's workspace filter depends on this query string reaching the
 * server, and a silently dropped parameter would show every song as if filtered.
 */

const calls: string[] = [];

function jsonResponse(body: unknown) {
  return {
    ok: true,
    status: 200,
    json: async () => body,
  } as unknown as Response;
}

beforeEach(() => {
  calls.length = 0;
  vi.stubGlobal("fetch", async (url: string) => {
    calls.push(String(url));
    return jsonResponse({ items: [{ id: "s1", title: "Song", style: "", status: "success", clips: [] }] });
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchGenerations", () => {
  it("asks for the newest songs of a limit", async () => {
    const items = await fetchGenerations(20);
    expect(calls[0]).toContain("/api/v3/web-music/generations?limit=20");
    expect(calls[0]).not.toContain("workspace_id");
    expect(items[0].title).toBe("Song");
  });

  it("passes the workspace filter through", async () => {
    await fetchGenerations(20, "w 1/2");
    expect(calls[0]).toContain("workspace_id=w+1%2F2");
  });

  it("omits the filter for null so 'all songs' stays unfiltered", async () => {
    await fetchGenerations(20, null);
    expect(calls[0]).not.toContain("workspace_id");
  });
});
