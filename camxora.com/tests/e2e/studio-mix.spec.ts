import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Live track mix (G21): mute and solo used to be applied only when sources were
 * scheduled, so pressing M or S mid-playback changed the button and nothing else.
 */

test("mute silences a playing track and unmute brings it back", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, {
    title: `Mix ${tag}`,
    clips: [
      { id: "audible", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  const meter = page.getByLabel("Master peak");
  const peak = async () => (await meter.innerText()).trim();

  await page.getByLabel("Play", { exact: true }).click();
  // A real reading, not the idle dash.
  await expect.poll(peak, { timeout: 15_000, intervals: [200] }).toMatch(/dB pk/);
  const sounding = await peak();
  expect(sounding).not.toContain("-inf");

  await page.getByRole("button", { name: "Mute Track 1" }).click();
  await expect.poll(peak, { timeout: 10_000, intervals: [150] }).toContain("-inf");

  await page.getByRole("button", { name: "Mute Track 1" }).click();
  await expect
    .poll(peak, { timeout: 10_000, intervals: [150] })
    .not.toContain("-inf");

  await page.getByLabel("Pause", { exact: true }).click();
});

test("solo silences other tracks while it is on", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, {
    title: `Solo ${tag}`,
    clips: [
      { id: "a", title: "A", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  // A second track with the same loop so solo has something to silence.
  await page.keyboard.press("a");
  await expect(page.locator(".se-track")).toHaveCount(2);

  const meter = page.getByLabel("Master peak");
  await page.getByLabel("Play", { exact: true }).click();
  await expect.poll(async () => (await meter.innerText()).trim(), { timeout: 15_000 }).toMatch(/dB pk/);

  // Solo the empty second track: the audible one must fall silent.
  await page.getByRole("button", { name: "Solo Track 2" }).click();
  await expect
    .poll(async () => (await meter.innerText()).trim(), { timeout: 10_000, intervals: [150] })
    .toContain("-inf");

  // Unsolo: sound returns.
  await page.getByRole("button", { name: "Solo Track 2" }).click();
  await expect
    .poll(async () => (await meter.innerText()).trim(), { timeout: 10_000, intervals: [150] })
    .not.toContain("-inf");

  await page.getByLabel("Pause", { exact: true }).click();
});
