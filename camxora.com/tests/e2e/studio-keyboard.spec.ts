import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Keyboard bindings (spec §11): Space transport, Home/End, and the add-track
 * accelerators A / U. M is deliberately unbound — there are no MIDI tracks.
 */

test("keyboard drives transport and the add-track accelerators", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `Keys ${tag}` });

  // Space toggles playback (the transport button relabels itself).
  const play = page.getByLabel("Play", { exact: true });
  await expect(play).toBeVisible();
  await page.keyboard.press("Space");
  await expect(page.getByLabel("Pause", { exact: true })).toBeVisible();
  await page.keyboard.press("Space");
  await expect(page.getByLabel("Play", { exact: true })).toBeVisible();

  // Home parks the playhead at zero after it has moved.
  await page.locator(".se-lanes").click({ position: { x: 300, y: 40 } });
  const clock = page.getByLabel("Time", { exact: true });
  await expect(clock).not.toHaveText("00:00.000");
  await page.keyboard.press("Home");
  await expect(clock).toHaveText("00:00.000");

  // A adds an audio track (the menu's first item, wired to the same action).
  await expect(page.locator(".se-track")).toHaveCount(1);
  await page.keyboard.press("a");
  await expect(page.locator(".se-track")).toHaveCount(2);

  // U opens the library straight on its Uploads list (level 2).
  await page.keyboard.press("u");
  const library = page.getByRole("complementary", { name: "Library" });
  await expect(library).toBeVisible();
  await expect(library.getByLabel("Back to library")).toBeVisible();
  await expect(library.getByText("Uploads", { exact: true })).toBeVisible();

  // M does nothing: no third track appears.
  await page.keyboard.press("m");
  await expect(page.locator(".se-track")).toHaveCount(2);
});

test("the add-track menu keeps the captured items and letters", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `Menu ${tag}` });

  await page.getByRole("button", { name: /Add new track/ }).click();
  const menu = page.getByRole("menu", { name: "Add a track" });
  await expect(menu).toBeVisible();
  const items = menu.getByRole("menuitem");
  await expect(items).toHaveCount(3);
  await expect(items.nth(0)).toHaveText("Audio A");
  await expect(items.nth(1)).toHaveText("MIDI M");
  await expect(items.nth(2)).toHaveText("Upload U");
  await expect(items.nth(1)).toBeEnabled();

  await items.nth(0).click();
  await expect(page.locator(".se-track")).toHaveCount(2);
  await expect(menu).toHaveCount(0);
});
