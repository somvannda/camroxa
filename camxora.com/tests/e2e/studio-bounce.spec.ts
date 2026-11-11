import { readFile } from "node:fs/promises";

import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Track bounce (N-06).
 *
 * The reference reports "Exporting on track #" and renders a mixdown; ours bounces one
 * track through its own effect chain and hands back a WAV, ignoring the other tracks'
 * solo state so a soloed-out track is never silent.
 */

test("the track menu bounces that track to a RIFF mixdown", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, {
    title: `Bounce ${tag}`,
    clips: [
      { id: "loop", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  await page.getByLabel("Options for Track 1").click();
  const download = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: "Bounce track" }).click();

  const wav = await download;
  expect(wav.suggestedFilename()).toContain("(bounce).wav");

  const path = await wav.path();
  if (!path) throw new Error("bounce download has no path");
  const bytes = await readFile(path);
  expect(bytes.subarray(0, 4).toString("latin1")).toBe("RIFF");
  expect(bytes.subarray(8, 12).toString("latin1")).toBe("WAVE");
  // 4 s stereo 44.1 kHz 16-bit plus the 44-byte header.
  const expected = 44 + 4 * 44100 * 2 * 2;
  expect(Math.abs(bytes.length - expected)).toBeLessThan(2000);

  await expect(page.getByRole("status")).toContainText("Bounce on Track 1 started!");
});

test("a track with no clips cannot be bounced", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `Empty bounce ${tag}` });

  // Clear the fixture clip, leaving the track in place with nothing to render.
  await page.locator(".se-clip").first().click();
  await page.keyboard.press("Backspace");
  await expect(page.locator(".se-clip")).toHaveCount(0);

  await page.getByLabel("Options for Track 1").click();
  await expect(page.getByRole("menuitem", { name: "Bounce track" })).toBeDisabled();
});
