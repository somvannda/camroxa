import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

import { createStudioProject } from "./studio-fixture";

/**
 * Master section (reference F-01/F-02): a Main fader and a main mute, both live while
 * playing, persisted in the document, and reflected in the exported mix.
 */

async function wavRms(download: import("@playwright/test").Download): Promise<number> {
  const path = await download.path();
  if (!path) throw new Error("download has no path");
  const bytes = await readFile(path);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let sum = 0;
  let count = 0;
  for (let offset = 44; offset + 1 < bytes.length; offset += 2) {
    const sample = view.getInt16(offset, true) / 0x8000;
    sum += sample * sample;
    count += 1;
  }
  return count ? Math.sqrt(sum / count) : 0;
}

test("the main fader and mute affect playback and the export", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Master ${tag}`,
    clips: [
      { id: "audible", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  const fader = page.getByRole("slider", { name: "Master volume" });
  const mute = page.getByRole("button", { name: "Mute main" });
  await expect(fader).toHaveValue("85");
  await expect(mute).toHaveAttribute("aria-pressed", "false");

  // Live: pull the fader to zero and the playing track goes silent; restore it.
  const meter = page.getByLabel("Master peak");
  const peak = async () => (await meter.innerText()).trim();

  await page.getByLabel("Play", { exact: true }).click();
  await expect.poll(peak, { timeout: 15_000, intervals: [200] }).toMatch(/dB pk/);
  await expect.poll(peak, { timeout: 10_000 }).not.toContain("-inf");

  await fader.fill("0");
  await fader.press("Tab"); // commit
  await expect.poll(peak, { timeout: 10_000, intervals: [150] }).toContain("-inf");

  await fader.fill("85");
  await fader.press("Tab");
  await expect.poll(peak, { timeout: 10_000, intervals: [150] }).not.toContain("-inf");

  // Main mute also silences without moving the fader.
  await mute.click();
  await expect(mute).toHaveAttribute("aria-pressed", "true");
  await expect.poll(peak, { timeout: 10_000, intervals: [150] }).toContain("-inf");
  await mute.click();
  await expect.poll(peak, { timeout: 10_000, intervals: [150] }).not.toContain("-inf");
  await page.getByLabel("Pause", { exact: true }).click();

  // Persisted in the document (poll: the unmute write may still be in flight).
  await expect
    .poll(
      () =>
        page.evaluate(async (id) => {
          const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
          const project = (await response.json()) as {
            data?: { masterVolume?: number; masterMuted?: boolean };
          };
          return { volume: project.data?.masterVolume, muted: project.data?.masterMuted };
        }, projectId),
      { timeout: 15_000 }
    )
    .toEqual({ volume: 85, muted: false });

  // …and the export follows it: muted bounce is silence, then audio returns.
  const exportMix = async () => {
    await page.getByLabel("Export menu").click();
    const download = page.waitForEvent("download");
    await page.getByRole("menuitem", { name: "Full mix (WAV)" }).click();
    return wavRms(await download);
  };

  await mute.click();
  const silent = await exportMix();
  expect(silent).toBeLessThan(0.0005);

  await mute.click();
  const audible = await exportMix();
  expect(audible).toBeGreaterThan(0.001);

  // Reload keeps the fader where the user left it.
  await page.reload();
  await expect(page.getByRole("slider", { name: "Master volume" })).toHaveValue("85", {
    timeout: 30_000,
  });
});
