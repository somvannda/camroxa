import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getStudioProject,
  listStudioProjects,
  StudioConflictError,
  updateStudioProject,
} from "@/lib/studio-api";

/**
 * Contract tests for the Studio API client (W5.3).
 *
 * The seam is global `fetch`, which is what `musicAuthFetch` calls. These assert the
 * things that break silently: the version field actually leaving the browser, 409
 * mapping to the typed conflict error the editor relies on, server messages surviving,
 * and 204 not being parsed as JSON.
 */

const calls: { url: string; init: RequestInit }[] = [];

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as unknown as Response;
}

beforeEach(() => {
  calls.length = 0;
  vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
    calls.push({ url: String(url), init });
    if (String(url).includes("/projects/missing")) {
      return jsonResponse({ error: { message: "Project not found." } }, 404);
    }
    if (String(url).includes("/projects/stale")) {
      return jsonResponse(
        { error: { code: "CONFLICT", message: "This project changed since you loaded it." } },
        409
      );
    }
    if (init?.method === "DELETE") {
      return { ok: true, status: 204, json: async () => null } as unknown as Response;
    }
    return jsonResponse({
      id: "p1",
      title: "Demo",
      major_version: 2,
      bpm: 120,
      time_signature: "4/4",
      updated_at: "2026-11-04T00:00:00Z",
    });
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("listStudioProjects", () => {
  it("passes paging and archive flags in the query string", async () => {
    await listStudioProjects(25, 50, true);
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toContain("limit=25");
    expect(calls[0].url).toContain("offset=50");
    expect(calls[0].url).toContain("include_archived=true");
  });

  it("defaults to the first page without archived projects", async () => {
    await listStudioProjects();
    expect(calls[0].url).toContain("limit=20");
    expect(calls[0].url).toContain("offset=0");
    expect(calls[0].url).toContain("include_archived=false");
  });
});

describe("updateStudioProject", () => {
  it("only sends expected_updated_at when a version is supplied", async () => {
    await updateStudioProject("p1", { bpm: 130 });
    const withoutVersion = JSON.parse(String(calls[0].init.body));
    expect(withoutVersion).toEqual({ bpm: 130 });
    expect("expected_updated_at" in withoutVersion).toBe(false);

    calls.length = 0;
    await updateStudioProject("p1", { bpm: 130, expectedUpdatedAt: "2026-11-04T00:00:00Z" });
    const withVersion = JSON.parse(String(calls[0].init.body));
    expect(withVersion.expected_updated_at).toBe("2026-11-04T00:00:00Z");
  });

  it("keeps the field name the server expects", async () => {
    await updateStudioProject("p1", { expectedUpdatedAt: "2026-01-01T00:00:00Z" });
    const body = JSON.parse(String(calls[0].init.body));
    expect(Object.keys(body)).toContain("expected_updated_at");
    expect(Object.keys(body)).not.toContain("expectedUpdatedAt");
  });

  it("maps 409 to StudioConflictError so the editor can offer a choice", async () => {
    await expect(updateStudioProject("stale", { bpm: 100 })).rejects.toBeInstanceOf(
      StudioConflictError
    );
  });

  it("surfaces the server message for other failures", async () => {
    await expect(updateStudioProject("missing", { bpm: 100 })).rejects.toThrow("Project not found.");
  });
});

describe("getStudioProject", () => {
  it("encodes the id into the path", async () => {
    await getStudioProject("a b/c");
    expect(calls[0].url).toContain("a%20b%2Fc");
  });
});

describe("204 responses", () => {
  it("does not try to parse an empty body", async () => {
    const { deleteStudioProject } = await import("@/lib/studio-api");
    await expect(deleteStudioProject("p1")).resolves.toBeUndefined();
  });
});
