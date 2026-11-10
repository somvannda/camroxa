import { test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

test("shot brand", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1689, height: 1277 });
  await createStudioProject(page, { title: "Brand" });
  await page.setViewportSize({ width: 1689, height: 1277 });
  await page.screenshot({ path: "test-results/shot-brand.png" });
  // MIDI keyboard
  await page.getByRole("button", { name: /Add new track/ }).click();
  await page.getByRole("menuitem", { name: /MIDI/ }).click();
  await page.waitForTimeout(400);
  await page.screenshot({ path: "test-results/shot-brand-midi.png" });
});
