import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Microphone takes (D-020): arming is real, Record runs a MediaRecorder on the armed
 * track, and Stop uploads the take and inserts it as a clip. The upload needs streaming
 * storage (B-006), so the test only runs when STUDIO_EXPECT_UPLOADS=1.
 */

test("arming a track and recording a take inserts a clip", async ({ page }) => {
  test.skip(
    process.env.STUDIO_EXPECT_UPLOADS !== "1",
    "recording uploads need streaming storage (B-006)"
  );
  test.setTimeout(120_000);
  await createStudioProject(page, { title: `Record ${Math.random().toString(36).slice(2, 6)}` });

  const before = await page.locator(".se-clip").count();
  await page.getByRole("button", { name: /^Arm / }).first().click();
  await expect(page.getByRole("button", { name: /^Disarm / }).first()).toBeVisible();

  await page.getByRole("button", { name: "Record", exact: true }).click();
  await expect(page.getByRole("button", { name: "Stop recording", exact: true })).toBeVisible();
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Stop recording", exact: true }).click();
  await expect(page.getByRole("button", { name: "Record", exact: true })).toBeVisible();

  await expect.poll(async () => page.locator(".se-clip").count(), { timeout: 20_000 }).toBe(
    before + 1
  );
  await expect(page.locator(".se-clip", { hasText: /Take \d+/ })).toBeVisible();
});
