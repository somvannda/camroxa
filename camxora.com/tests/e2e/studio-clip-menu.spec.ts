import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Clip context menu (S26/§47): right-click selects the clip and opens a menu built from
 * its state; Split cuts at the playhead and the halves stay musically in place.
 */

test("the clip menu splits, renames and recolours a clip", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Clip menu ${tag}`,
    clips: [
      { id: "clip", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  const lanes = () =>
    page.evaluate(async (id) => {
      const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
      const project = (await response.json()) as {
        data?: { lanes?: Array<{ id: string; title?: string; color?: string; start?: number; duration?: number }> };
      };
      return project.data?.lanes ?? [];
    }, projectId);

  const clip = page.locator(".se-clip").first();
  const box = await clip.boundingBox();
  if (!box) throw new Error("clip has no box");

  // Right-click opens the menu and selects the clip.
  await page.mouse.click(box.x + 30, box.y + 40, { button: "right" });
  const menu = page.getByRole("menu", { name: "Clip options" });
  await expect(menu).toBeVisible();
  await expect(clip).toHaveAttribute("aria-pressed", "true");
  const items = await menu.getByRole("menuitem").allInnerTexts();
  expect(items[0]).toContain("Copy");
  expect(items.join(" ")).toContain("Split");
  expect(items.join(" ")).toContain("Clip Color");
  expect(items.join(" ")).toContain("Get Stems");
  expect(items.join(" ")).toContain("Download WAV");
  await expect(menu.getByRole("menuitem", { name: "Clip Info" })).toBeEnabled();

  // Split needs the playhead inside the clip: put it at 2 s (one bar).
  await page.locator(".se-ruler-bars").click({ position: { x: 96, y: 12 } });
  await expect(page.getByLabel("Time", { exact: true })).toHaveText("00:02.000");

  // Re-open the menu on the clip and split.
  await page.mouse.click(box.x + 30, box.y + 40, { button: "right" });
  await menu.getByRole("menuitem", { name: /Split/ }).click();
  await expect(page.locator(".se-clip")).toHaveCount(2);
  const split = await lanes();
  expect(split).toHaveLength(2);
  expect(split[0].duration).toBe(2);
  expect(split[1].start).toBe(2);
  expect(split[1].duration).toBe(2);

  // Rename the second half through the menu.
  const second = page.locator(".se-clip").nth(1);
  const secondBox = await second.boundingBox();
  if (!secondBox) throw new Error("second clip has no box");
  await page.mouse.click(secondBox.x + 20, secondBox.y + 40, { button: "right" });
  await menu.getByRole("menuitem", { name: "Rename" }).click();
  const dialog = page.getByRole("dialog", { name: "Rename clip" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Clip name").fill("Drop");
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect
    .poll(async () => (await lanes()).some((lane) => lane.title === "Drop"), { timeout: 15_000 })
    .toBe(true);
  await expect(page.getByText("Drop")).toBeVisible();

  // Clip Color writes a per-clip colour override.
  await page.mouse.click(secondBox.x + 20, secondBox.y + 40, { button: "right" });
  await menu.getByRole("menuitem", { name: /Clip Color/ }).click();
  await menu.getByLabel("Clip colour #f472b6").click();
  await expect
    .poll(async () => (await lanes()).some((lane) => lane.color === "#f472b6"), { timeout: 15_000 })
    .toBe(true);
  await expect(page.locator(".se-clip").nth(1)).toHaveCSS("background-color", "rgb(244, 114, 182)");
});

test("Ctrl+E splits the selected clip at the playhead", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, {
    title: `Split key ${tag}`,
    clips: [{ id: "clip", title: "Loop", start: 0, duration: 4 }],
  });

  await page.locator(".se-clip").first().click();
  await page.locator(".se-ruler-bars").click({ position: { x: 96, y: 12 } });
  await page.locator(".se-clip").first().click();
  await page.keyboard.press("Control+e");
  await expect(page.locator(".se-clip")).toHaveCount(2);
});
