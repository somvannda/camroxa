import { expect, test } from "@playwright/test";

import { draftKey } from "@/lib/studio-draft";

import { createStudioProject } from "./studio-fixture";

/**
 * Offline draft recovery (W2.3), including the reconnect path.
 *
 * The old behaviour flipped the chip back to "Saved" as soon as the browser reported
 * itself online, even though the edit only lived in localStorage. The editor now
 * replays the unsaved document and only says "Saved" once the server has it.
 */

test("an offline edit is replayed when the connection returns", async ({ page, context }) => {
  test.setTimeout(120_000);

  const projectId = await createStudioProject(page, { title: "Offline probe" });

  await context.setOffline(true);
  await page.keyboard.press("a");
  await expect(page.getByText("Offline · changes not saved")).toBeVisible({ timeout: 10_000 });
  // The edit is present locally, so the user keeps working.
  await expect(page.locator(".se-track")).toHaveCount(2);
  // The chip can appear from the browser's own `offline` event, before the write has
  // failed. Wait for the captured draft: only then is the replay guaranteed to have
  // something to send when the connection returns.
  await expect
    .poll(
      () =>
        page.evaluate(
          (key) => Boolean(window.localStorage.getItem(key)),
          draftKey(projectId)
        ),
      { timeout: 10_000, intervals: [100] }
    )
    .toBe(true);

  await context.setOffline(false);
  // Only after the replay does the chip tell the truth.
  await expect(page.getByText("Saved", { exact: true })).toBeVisible({ timeout: 20_000 });

  const tracks = await page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    const project = (await response.json()) as { data?: { tracks?: unknown[] } };
    return project.data?.tracks?.length ?? 0;
  }, projectId);
  expect(tracks).toBe(2);
});

test("a draft from a failed write is offered after a reload", async ({ page }) => {
  test.setTimeout(120_000);

  const projectId = await createStudioProject(page, { title: "Draft probe" });

  // Fail the write at the network layer while the browser still reports online, which
  // is the failed-write path rather than the offline one.
  await page.route("**/api/v3/web-music/studio/projects/*", async (route) => {
    if (route.request().method() === "PATCH") {
      await route.abort("failed");
      return;
    }
    await route.continue();
  });

  await page.keyboard.press("a");
  await expect(page.getByText(/Save failed/)).toBeVisible({ timeout: 15_000 });

  await page.unroute("**/api/v3/web-music/studio/projects/*");
  await page.reload();
  await expect(page.getByRole("alert", { name: "Recovered draft" })).toBeVisible({
    timeout: 30_000,
  });
  await page.getByRole("button", { name: "Restore draft" }).click();
  await expect(page.getByText("Saved", { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".se-track")).toHaveCount(2);
});
