import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * New editor controls from the parity pass: chord/arpeggiator modes and ruler
 * section markers. These are document writes, so the specs read the project back
 * instead of trusting the transient DOM alone.
 */

test("MIDI chord and arpeggiator modes write the expected notes", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1689, height: 1277 });
  await createStudioProject(page, { title: "MIDI modes" });

  await page.getByRole("button", { name: /Add new track/ }).click();
  await page.getByRole("menuitem", { name: /MIDI/ }).click();

  const panel = page.getByRole("region", { name: "MIDI editor" });
  const grid = panel.locator(".se-midi-grid");
  await grid.click({ position: { x: 90, y: 140 } });
  await expect(panel.locator(".se-midi-note")).toHaveCount(1);

  await panel.getByLabel("Chord mode").selectOption("major");
  await grid.click({ position: { x: 200, y: 140 } });
  await expect(panel.locator(".se-midi-note")).toHaveCount(4);

  await panel.getByLabel("Chord mode").selectOption("off");
  await panel.getByLabel("Arpeggiator").selectOption("up");
  await grid.click({ position: { x: 300, y: 140 } });
  await expect(panel.locator(".se-midi-note")).toHaveCount(5);

  // The arpeggio spreads the notes left-to-right; the chord stacks them.
  const lefts = await panel.locator(".se-midi-note").evaluateAll((nodes) =>
    nodes.map((node) => Math.round((node as HTMLElement).getBoundingClientRect().left))
  );
  expect(new Set(lefts).size).toBeGreaterThan(1);
});

test("track Automation draws a volume point that persists", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1689, height: 1277 });
  await createStudioProject(page, { title: "Track automation" });

  await page.locator(".se-clip").first().click();
  await page.locator(".se-foot").getByRole("button", { name: "Automation" }).click();
  const panel = page.getByRole("region", { name: "Track automation" });
  const volumeLane = panel.getByRole("group", { name: "Volume automation lane" });
  await expect(volumeLane).toBeVisible();
  await volumeLane.click({ position: { x: 180, y: 30 } });
  await expect(panel.locator(".se-automation-point")).toHaveCount(1);

  await panel.getByRole("button", { name: "Pan" }).click();
  const panLane = panel.getByRole("group", { name: "Pan automation lane" });
  await panLane.click({ position: { x: 320, y: 40 } });
  await expect(panel.locator(".se-automation-point")).toHaveCount(1);

  await page.reload();
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  await page.locator(".se-clip").first().click();
  await page.locator(".se-foot").getByRole("button", { name: "Automation" }).click();
  const reloaded = page.getByRole("region", { name: "Track automation" });
  await expect(reloaded.locator(".se-automation-point")).toHaveCount(1);
  await reloaded.getByRole("button", { name: "Pan" }).click();
  await expect(reloaded.locator(".se-automation-point")).toHaveCount(1);
});

test("Create Section stamps a ruler marker that survives a reload", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1689, height: 1277 });
  await createStudioProject(page, { title: "Section marker" });

  const clip = page.locator(".se-clip").first();
  await clip.click({ button: "right" });
  await page.getByRole("menuitem", { name: /Create Section/ }).click();

  const marker = page.locator(".se-section-marker");
  await expect(marker).toHaveCount(1);
  const label = await marker.first().getAttribute("aria-label");
  expect(label).toMatch(/Section .+ at /);

  await page.reload();
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".se-section-marker")).toHaveCount(1);
});
