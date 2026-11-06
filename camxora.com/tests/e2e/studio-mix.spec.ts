import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

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

test("the mix export follows solo, like playback", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Bounce ${tag}`,
    clips: [
      { id: "first", title: "First", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  // Add a second track whose clip sits at 8 s, so the two are separable in the file.
  const patched = await page.evaluate(async (id) => {
    const read = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    const project = (await read.json()) as { data: { lanes: unknown[]; tracks: unknown[] } };
    const data = {
      ...project.data,
      lanes: [
        ...project.data.lanes,
        {
          id: "second",
          title: "Second",
          start: 8,
          duration: 4,
          volume: 1,
          pan: 0,
          audioUrl: "/seed/demo-loop.wav",
        },
      ],
      tracks: [
        ...project.data.tracks,
        {
          id: "second-track",
          name: "Track 2",
          color: "#a78bfa",
          index: 1,
          volume: 80,
          pan: 0,
          muted: false,
          solo: false,
          hidden: false,
          groupId: null,
          chain: [],
          clipIds: ["second"],
        },
      ],
    };
    const write = await fetch(`/api/v3/web-music/studio/projects/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data }),
    });
    return write.status;
  }, projectId);
  expect(patched).toBe(200);

  await page.reload();
  await expect(page.locator(".se-clip")).toHaveCount(2, { timeout: 30_000 });

  const exportMix = async () => {
    await page.getByLabel("Export menu").click();
    const download = page.waitForEvent("download");
    await page.getByRole("menuitem", { name: "Full mix (WAV)" }).click();
    const file = await download;
    const path = await file.path();
    if (!path) throw new Error("download has no path");
    return readFile(path);
  };

  /** RMS of a window in seconds, from a 44.1 kHz 16-bit stereo WAV. */
  const windowRms = (bytes: Buffer, from: number, to: number) => {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const rate = 44100;
    const first = 44 + Math.floor(from * rate) * 4;
    const last = Math.min(bytes.length, 44 + Math.floor(to * rate) * 4);
    let sum = 0;
    let count = 0;
    for (let offset = first; offset + 1 < last; offset += 2) {
      const sample = view.getInt16(offset, true) / 0x8000;
      sum += sample * sample;
      count += 1;
    }
    return count ? Math.sqrt(sum / count) : 0;
  };

  const full = await exportMix();
  expect(windowRms(full, 0.2, 3.5)).toBeGreaterThan(0.001);
  expect(windowRms(full, 8.2, 11.5)).toBeGreaterThan(0.001);

  // Solo the second track: the bounce now contains only the second clip.
  await page.getByRole("button", { name: "Solo Track 2" }).click();
  await expect(page.getByRole("button", { name: "Solo Track 2" })).toHaveAttribute(
    "aria-pressed",
    "true"
  );
  const soloed = await exportMix();
  expect(windowRms(soloed, 0.2, 3.5)).toBeLessThan(0.0005);
  expect(windowRms(soloed, 8.2, 11.5)).toBeGreaterThan(0.001);
});
