import { expect, test } from "@playwright/test";

import { createStudioProject, dragFirstClipOneBar } from "./studio-fixture";

/**
 * Write serialization (W2.2 regression).
 *
 * Two edits in quick succession used to send the same `expected_updated_at`, so the
 * second was rejected as a 409 conflict the user never caused — trivially reproducible
 * on a slow connection. The editor now keeps one write in flight and coalesces the
 * newest pending one, reading the version from the previous response.
 */

test("a second edit during an in-flight save does not conflict", async ({ page }) => {
  test.setTimeout(120_000);

  const projectId = await createStudioProject(page, { title: "Write queue" });

  // Slow project writes down so the second action lands mid-flight, like a slow network.
  await page.route("**/api/v3/web-music/studio/projects/*", async (route) => {
    if (route.request().method() === "PATCH") {
      await new Promise((resolve) => setTimeout(resolve, 600));
    }
    await route.continue();
  });

  await dragFirstClipOneBar(page);
  await page.keyboard.press("a");

  await expect(page.locator(".se-track")).toHaveCount(2, { timeout: 15_000 });
  await expect(page.getByText(/changed since you loaded/)).toHaveCount(0);
  await expect(page.getByText("Saved")).toBeVisible({ timeout: 15_000 });

  // Both edits reached the server, not just the last one: the coalesced write carries
  // the full document (moved clip + two tracks).
  const saved = await page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    const project = (await response.json()) as {
      data?: { lanes?: Array<{ start?: number }>; tracks?: unknown[] };
    };
    return {
      lanes: project.data?.lanes?.length ?? 0,
      tracks: project.data?.tracks?.length ?? 0,
      start: project.data?.lanes?.[0]?.start ?? 0,
    };
  }, projectId);

  expect(saved.tracks).toBe(2);
  expect(saved.lanes).toBe(1);
  expect(saved.start).toBeGreaterThan(0);
});

test("undo during an in-flight save lands at the origin and persists", async ({ page }) => {
  test.setTimeout(120_000);

  const projectId = await createStudioProject(page, { title: "Undo race" });

  await page.route("**/api/v3/web-music/studio/projects/*", async (route) => {
    if (route.request().method() === "PATCH") {
      await new Promise((resolve) => setTimeout(resolve, 600));
    }
    await route.continue();
  });

  const clip = page.locator(".se-clip").first();
  const left = () => clip.evaluate((element) => (element as HTMLElement).style.left);

  await dragFirstClipOneBar(page);
  await expect.poll(left, { timeout: 10_000 }).not.toBe("0px");
  await page.keyboard.press("Control+z");

  await expect(page.getByText(/changed since you loaded/)).toHaveCount(0);
  await expect.poll(left, { timeout: 10_000 }).toBe("0px");
  await expect(page.getByText("Saved")).toBeVisible({ timeout: 15_000 });

  const start = await page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    const project = (await response.json()) as { data?: { lanes?: Array<{ start?: number }> } };
    return project.data?.lanes?.[0]?.start ?? null;
  }, projectId);
  expect(start).toBe(0);
});
