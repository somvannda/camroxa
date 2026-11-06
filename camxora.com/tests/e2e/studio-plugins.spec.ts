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

  // Record every AudioParam assignment with a timestamp: the EQ's band gain is set to
  // 18 by the live update path, and a rebuild would create a new filter node.
  await page.addInitScript(() => {
    (window as unknown as { __paramSets: Array<{ value: number; at: number }> }).__paramSets = [];
    (window as unknown as { __biquads: number }).__biquads = 0;
    const fil = BaseAudioContext.prototype.createBiquadFilter;
    BaseAudioContext.prototype.createBiquadFilter = function patched(this: BaseAudioContext) {
      (window as unknown as { __biquads: number }).__biquads += 1;
      return fil.call(this);
    };
    const descriptor = Object.getOwnPropertyDescriptor(AudioParam.prototype, "value");
    if (!descriptor || !descriptor.get || !descriptor.set) return;
    Object.defineProperty(AudioParam.prototype, "value", {
      configurable: true,
      get: descriptor.get,
      set(value: number) {
        (window as unknown as { __paramSets: Array<{ value: number; at: number }> }).__paramSets.push(
          { value, at: performance.now() }
        );
        descriptor.set!.call(this, value);
      },
    });
  });

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

  await page.getByLabel("Play", { exact: true }).click();
  const playAt = await page.evaluate(() => performance.now());
  // The graph is built asynchronously (decode), so wait for the EQ node before taking
  // the baseline. A rebuild after this point would be a second node.
  await expect
    .poll(() => page.evaluate(() => (window as unknown as { __biquads: number }).__biquads), {
      timeout: 15_000,
      intervals: [100],
    })
    .toBeGreaterThan(0);
  const biquadsAtPlay = await page.evaluate(
    () => (window as unknown as { __biquads: number }).__biquads
  );

  await gain.fill("18");

  // The running graph received the new value…
  await expect
    .poll(
      () =>
        page.evaluate(
          (since) =>
            (window as unknown as { __paramSets: Array<{ value: number; at: number }> }).__paramSets.some(
              (entry) => entry.value === 18 && entry.at >= since
            ),
          playAt
        ),
      { timeout: 10_000, intervals: [100] }
    )
    .toBe(true);

  // …without rebuilding the chain (no new filter node after playback started).
  const biquadsNow = await page.evaluate(
    () => (window as unknown as { __biquads: number }).__biquads
  );
  expect(biquadsNow).toBe(biquadsAtPlay);

  await page.getByLabel("Pause", { exact: true }).click();
});
