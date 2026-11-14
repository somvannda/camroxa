import { expect, test } from "@playwright/test";

import { clipLeft, createStudioProject, dragFirstClipOneBar } from "./studio-fixture";

/**
 * Studio smoke (roadmap W5.4): create a project, move a clip, undo it, open export.
 *
 * The fixture comes from `studio-fixture.ts`, so this spec does not depend on leftover
 * projects or on a UI login. It needs a dev server on BASE_URL with the sandbox API
 * running; the account is the local sandbox user and must never point at production.
 */

test("studio smoke: move, undo, export", async ({ page }) => {
  test.setTimeout(120_000);

  await createStudioProject(page, { title: "Smoke project" });
  const before = await clipLeft(page);

  // Drag it exactly one bar (96px at the default zoom).
  await dragFirstClipOneBar(page);
  await expect.poll(() => clipLeft(page), { timeout: 10_000 }).not.toBe(before);

  // The save chip settles, then undo restores the original position.
  await expect(page.getByText("Saved")).toBeVisible({ timeout: 15_000 });
  await page.keyboard.press("Control+z");
  await expect.poll(() => clipLeft(page), { timeout: 10_000 }).toBe(before);

  // The export menu opens with its scopes (and the G11 normalise toggle).
  await page.getByLabel("Export menu").click();
  await expect(page.getByRole("menuitem", { name: /Full Song/ })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: /Selected Time Range/ })).toBeVisible();
  await expect(page.getByRole("menuitemcheckbox", { name: /Normalise mix/ })).toBeVisible();
});
