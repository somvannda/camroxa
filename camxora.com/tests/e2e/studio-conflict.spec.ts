import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Optimistic-concurrency UI (W2.2): a write based on a stale version must offer the
 * choice the API documents — reload theirs, or overwrite with mine.
 *
 * The second writer is simulated with a plain fetch in the page (another tab/device
 * edits the same project), which bumps `updated_at` behind the editor's back.
 */

test("a stale write opens the conflict panel and overwrite keeps local work", async ({ page }) => {
  test.setTimeout(120_000);

  const projectId = await createStudioProject(page, { title: "Conflict probe" });

  // Another writer changes the project without the editor knowing.
  const bumped = await page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: { lanes: [], tracks: [], note: "other tab" } }),
    });
    return response.status;
  }, projectId);
  expect(bumped).toBe(200);

  // The editor still holds the old version, so its next write is rejected.
  await page.keyboard.press("a");

  const panel = page.getByRole("alertdialog", { name: "Project changed elsewhere" });
  await expect(panel).toBeVisible({ timeout: 15_000 });
  await expect(panel).toContainText("changed since you loaded");

  // Overwrite: send the local document without a version check.
  await panel.getByRole("button", { name: "Keep mine" }).click();
  await expect(panel).toHaveCount(0);
  await expect(page.getByText("Saved")).toBeVisible({ timeout: 15_000 });

  const saved = await page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    const project = (await response.json()) as { data?: { tracks?: unknown[]; note?: string } };
    return { tracks: project.data?.tracks?.length ?? 0, note: project.data?.note ?? null };
  }, projectId);

  // The local document won, and the other writer's marker is gone.
  expect(saved.tracks).toBe(2);
  expect(saved.note).toBeNull();
});

test("reload theirs restores the server document", async ({ page }) => {
  test.setTimeout(120_000);

  const projectId = await createStudioProject(page, { title: "Conflict reload" });

  await page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        data: {
          lanes: [{ id: "theirs", title: "Theirs", start: 4, duration: 4, volume: 1, pan: 0 }],
          tracks: [
            {
              id: "their-track",
              name: "Theirs",
              color: "#a78bfa",
              index: 0,
              volume: 80,
              pan: 0,
              muted: false,
              solo: false,
              hidden: false,
              groupId: null,
              chain: [],
              clipIds: ["theirs"],
            },
          ],
        },
      }),
    });
    return response.status;
  }, projectId);

  await page.keyboard.press("a");
  const panel = page.getByRole("alertdialog", { name: "Project changed elsewhere" });
  await expect(panel).toBeVisible({ timeout: 15_000 });

  await panel.getByRole("button", { name: "Reload theirs" }).click();
  await expect(panel).toHaveCount(0);

  // The server's single (renamed) track replaced the local pair.
  await expect(page.getByRole("button", { name: /Options for Theirs/ })).toBeVisible({
    timeout: 10_000,
  });
  await expect(page.locator(".se-track")).toHaveCount(1);
});
