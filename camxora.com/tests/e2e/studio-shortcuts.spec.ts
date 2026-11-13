import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Shortcut overlay bindings (spec §36/C-07) that have real actions behind them:
 * loop, metronome, add track, select all, cut, mute/solo, hide/show, rename, library.
 */

test("the captured shortcuts drive their actions", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, {
    title: `Keys ${tag}`,
    clips: [
      { id: "one", title: "One", start: 0, duration: 2 },
      { id: "two", title: "Two", start: 4, duration: 2 },
    ],
  });

  const clips = page.locator(".se-clip");
  const loop = page.locator(".se-head").getByRole("button", { name: "Loop", exact: true });
  const metronome = page.getByRole("button", { name: /^Metronome/ });
  const library = page.getByRole("complementary", { name: "Library" });

  // CTRL L toggles the loop.
  await page.keyboard.press("Control+l");
  await expect(loop).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("Control+l");
  await expect(loop).toHaveAttribute("aria-pressed", "false");

  // SHIFT C toggles the metronome.
  await page.keyboard.press("Shift+C");
  await expect(metronome).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("Shift+C");
  await expect(metronome).toHaveAttribute("aria-pressed", "false");

  // CTRL A selects every clip.
  await page.keyboard.press("Control+a");
  await expect(page.locator(".se-clip.selected")).toHaveCount(2);

  // CTRL X cuts them; CTRL V brings them back.
  await page.keyboard.press("Control+x");
  await expect(clips).toHaveCount(0);
  await page.keyboard.press("Control+v");
  await expect(clips).toHaveCount(2);

  // SHIFT T adds a track; SHIFT H hides it; SHIFT ALT H restores it.
  await page.keyboard.press("Shift+T");
  await expect(page.locator(".se-track")).toHaveCount(2);
  await page.getByRole("button", { name: "Track 2", exact: true }).click();
  await page.keyboard.press("Shift+H");
  await expect(page.locator(".se-track")).toHaveCount(1);
  await expect(page.getByLabel("1 hidden track")).toBeVisible();
  await page.keyboard.press("Shift+Alt+H");
  await expect(page.locator(".se-track")).toHaveCount(2);

  // F2 renames the focused track.
  await page.getByRole("button", { name: "Track 2", exact: true }).click();
  await page.keyboard.press("F2");
  const input = page.locator(".se-track-rename");
  await expect(input).toBeVisible();
  await input.fill("Lead");
  await input.press("Enter");
  await expect(page.getByRole("button", { name: "Lead", exact: true })).toBeVisible();

  // SHIFT M / SHIFT S on the focused track. Hide & Mute left the track muted, so
  // assert the toggle flips rather than assuming the starting state.
  const mute = page.getByRole("button", { name: "Mute Lead" });
  const solo = page.getByRole("button", { name: "Solo Lead" });
  const wasMuted = (await mute.getAttribute("aria-pressed")) === "true";
  await page.keyboard.press("Shift+M");
  await expect(mute).toHaveAttribute("aria-pressed", wasMuted ? "false" : "true");
  await page.keyboard.press("Shift+M");
  await expect(mute).toHaveAttribute("aria-pressed", wasMuted ? "true" : "false");

  const wasSoloed = (await solo.getAttribute("aria-pressed")) === "true";
  await page.keyboard.press("Shift+S");
  await expect(solo).toHaveAttribute("aria-pressed", wasSoloed ? "false" : "true");
  await page.keyboard.press("Shift+S");
  await expect(solo).toHaveAttribute("aria-pressed", wasSoloed ? "true" : "false");

  // 0 mutes the arrangement output, not the tracks.
  const mainMute = page.getByRole("button", { name: "Mute main" });
  await page.keyboard.press("0");
  await expect(mainMute).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("0");
  await expect(mainMute).toHaveAttribute("aria-pressed", "false");

  // ALT SPACE rolls the transport from the selection start (or the playhead).
  await page.keyboard.press("Alt+Space");
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible();
  await page.keyboard.press("Space");
  await expect(page.getByRole("button", { name: "Play", exact: true })).toBeVisible();

  // SHIFT A toggles the automation band for the focused track.
  await page.keyboard.press("Shift+A");
  await expect(page.getByRole("region", { name: "Track automation" })).toBeVisible();
  await page.keyboard.press("Shift+A");
  await expect(page.getByRole("region", { name: "Track automation" })).toHaveCount(0);

  // CTRL ↑ / ↓ reorders the focused track.
  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  await page.keyboard.press("Control+ArrowDown");
  await expect(page.locator(".se-track-name")).toHaveText(["Lead", "Track 1"]);

  // 1 and 3 toggle the assistant and take-lanes panels.
  await page.keyboard.press("1");
  await expect(page.getByRole("complementary", { name: "Studio assistant" })).toBeVisible();
  await page.keyboard.press("1");
  await expect(page.getByRole("complementary", { name: "Studio assistant" })).toHaveCount(0);
  await page.keyboard.press("3");
  await expect(page.getByRole("region", { name: "Take lanes" })).toBeVisible();
  await page.keyboard.press("3");
  await expect(page.getByRole("region", { name: "Take lanes" })).toHaveCount(0);

  // SHIFT TAB swaps the two bottom bands.
  const takeLanes = page.getByRole("region", { name: "Take lanes" });
  const automation = page.getByRole("region", { name: "Track automation" });
  await page.keyboard.press("3");
  await expect(takeLanes).toBeVisible();
  await page.keyboard.press("Shift+Tab");
  await expect(takeLanes).toHaveCount(0);
  await expect(automation).toBeVisible();
  await page.keyboard.press("Shift+Tab");
  await expect(automation).toHaveCount(0);
  await expect(takeLanes).toBeVisible();
  await page.keyboard.press("3");
  await expect(takeLanes).toHaveCount(0);

  // 4 toggles the library drawer.
  await page.keyboard.press("4");
  await expect(library).toBeVisible();
  await page.keyboard.press("4");
  await expect(library).toHaveCount(0);
});

test("Ctrl S saves immediately through the write queue", async ({ page }) => {
  test.setTimeout(120_000);
  const projectId = await createStudioProject(page, {
    title: `Save now ${Math.random().toString(36).slice(2, 8)}`,
  });

  await expect(page.locator(".se-save")).toHaveText("Saved", { timeout: 20_000 });
  const patch = page.waitForRequest(
    (request) =>
      request.method() === "PATCH" &&
      request.url().includes(`/studio/projects/${projectId}`),
    { timeout: 15_000 }
  );
  await page.keyboard.press("Control+s");
  await patch;
  await expect(page.locator(".se-save")).toHaveText("Saved", { timeout: 20_000 });
});
