import { expect, test } from "@playwright/test";

import { clipLeft, createStudioProject, dragFirstClipOneBar, savedClipStart } from "./studio-fixture";

/**
 * Persistence (W2.1/G13): a change made in the editor must survive a reload.
 *
 * The smoke spec proves the UI moves and undo works; this proves the move actually
 * reached the server and comes back, which is the invariant autosave exists for.
 */

test("a moved clip is saved and still moved after a reload", async ({ page }) => {
  test.setTimeout(120_000);

  const projectId = await createStudioProject(page, { title: "Persistence project" });
  const before = await clipLeft(page);

  await dragFirstClipOneBar(page);
  await expect.poll(() => clipLeft(page), { timeout: 10_000 }).toBeGreaterThan(before);

  // Saved server-side, read back through the API rather than trusting the DOM.
  await expect
    .poll(() => savedClipStart(page, projectId), { timeout: 15_000 })
    .toBeGreaterThan(0);

  const persisted = await savedClipStart(page, projectId);
  const movedLeft = await clipLeft(page);

  await page.reload();
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  await expect.poll(() => clipLeft(page), { timeout: 15_000 }).toBe(movedLeft);

  // Nothing pending means no beforeunload trap on the way out.
  await expect(page.getByText("Saved")).toBeVisible();
  expect(persisted).toBeGreaterThan(0);
});
