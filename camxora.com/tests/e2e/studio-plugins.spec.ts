import { expect, test, type Download } from "@playwright/test";
import { readFile } from "node:fs/promises";

import { createStudioProject } from "./studio-fixture";

/**
 * Per-track plugin chains reach the audio engine (W4.1/§50).
 *
 * The chain used to be UI-only: it persisted, but neither playback nor export applied
 * it. This renders the same clip twice — dry, then with a +24 dB EQ — and compares the
 * decoded samples of the downloaded WAVs.
 */

/** RMS of a 16-bit PCM WAV's samples, ignoring the 44-byte header. */
async function wavRms(download: Download): Promise<number> {
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

test("an EQ on the track changes the exported mix", async ({ page }) => {
  test.setTimeout(120_000);

  // Count biquad filters from before the app boots: the built-in EQ is the only thing
  // in the playback graph that creates one (the default master limiter is a compressor).
  await page.addInitScript(() => {
    (window as unknown as { __biquads: number }).__biquads = 0;
    const proto = BaseAudioContext.prototype;
    const original = proto.createBiquadFilter;
    proto.createBiquadFilter = function patched(this: BaseAudioContext) {
      (window as unknown as { __biquads: number }).__biquads += 1;
      return original.call(this);
    };
  });

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Plugins ${tag}`,
    clips: [
      { id: "audible", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  // Dry export first.
  await page.getByLabel("Export menu").click();
  const dryDownload = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: "Full mix (WAV)" }).click();
  const dry = await wavRms(await dryDownload);
  expect(dry).toBeGreaterThan(0);

  // Add an EQ to the track and push its gain up.
  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  const dock = page.getByRole("region", { name: "Plugins for Track 1" });
  await expect(dock).toBeVisible();
  await dock.getByRole("button", { name: "Add effect", exact: true }).first().click();
  const catalog = page.getByRole("dialog", { name: "Add a track plugin" });
  await expect(catalog).toBeVisible();
  await catalog.getByRole("button", { name: /^EQ/ }).click();
  await expect(page.getByRole("article", { name: "EQ slot 1" })).toBeVisible();

  const gain = page.getByRole("slider", { name: "Gain" });
  await gain.fill("24");

  // The chain is stored on the project…
  await expect
    .poll(
      () =>
        page.evaluate(async (id) => {
          const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
          const project = (await response.json()) as {
            data?: { chains?: Record<string, unknown[]> };
          };
          return project.data?.chains?.["fixture-track"]?.length ?? 0;
        }, projectId),
      { timeout: 15_000 }
    )
    .toBe(1);

  // …and the wet export is audibly louder.
  await page.getByLabel("Export menu").click();
  const wetDownload = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: "Full mix (WAV)" }).click();
  const wet = await wavRms(await wetDownload);

  expect(wet / dry).toBeGreaterThan(1.2);

  // Playback builds the same chain: pressing play must create the EQ's filter node.
  const beforePlay = await page.evaluate(() => (window as unknown as { __biquads: number }).__biquads);
  await page.getByLabel("Play", { exact: true }).click();
  await expect
    .poll(() => page.evaluate(() => (window as unknown as { __biquads: number }).__biquads), {
      timeout: 10_000,
    })
    .toBeGreaterThan(beforePlay);
  await page.getByLabel("Pause", { exact: true }).click();
});

test("turning an EQ knob while playing changes the live level", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, {
    title: `Live EQ ${tag}`,
    clips: [
      { id: "audible", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  const dock = page.getByRole("region", { name: "Plugins for Track 1" });
  await dock.getByRole("button", { name: "Add effect", exact: true }).first().click();
  await page.getByRole("dialog", { name: "Add a track plugin" }).getByRole("button", { name: /^EQ/ }).click();
  const gain = page.getByRole("slider", { name: "Gain" });
  await gain.fill("0");

  const meter = page.getByLabel("Master peak");
  const peak = async () => {
    const text = (await meter.innerText()).trim();
    const value = Number.parseFloat(text);
    return Number.isFinite(value) ? value : -60;
  };

  await page.getByLabel("Play", { exact: true }).click();
  await expect.poll(peak, { timeout: 15_000, intervals: [200] }).toBeGreaterThan(-60);
  const before = await peak();

  // +18 dB on the only band: the running graph must follow without a restart.
  await gain.fill("18");
  await expect
    .poll(peak, { timeout: 10_000, intervals: [200] })
    .toBeGreaterThan(before + 3);

  await page.getByLabel("Pause", { exact: true }).click();
});
