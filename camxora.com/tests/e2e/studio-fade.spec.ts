import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

import { createStudioProject } from "./studio-fixture";

/**
 * Clip fade (S25): a diagonal handle at the top-left sets a fade-in; Shift+F toggles a
 * short default. The fade must be audible in the exported file, not just stored.
 */

async function wavWindowRms(download: import("@playwright/test").Download, from: number, to: number) {
  const path = await download.path();
  if (!path) throw new Error("download has no path");
  const bytes = await readFile(path);
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
}

test("the fade handle and Shift+F set a fade that is audible in the export", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Fade ${tag}`,
    clips: [
      { id: "clip", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  const lane = () =>
    page.evaluate(async (id) => {
      const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
      const project = (await response.json()) as {
        data?: { lanes?: Array<{ fadeIn?: number }> };
      };
      return project.data?.lanes?.[0]?.fadeIn ?? 0;
    }, projectId);

  const exportMix = async () => {
    await page.getByLabel("Export menu").click();
    const download = page.waitForEvent("download");
    await page.getByRole("menuitem", { name: "Full mix (WAV)" }).click();
    return download;
  };

  const plain = await wavWindowRms(await exportMix(), 0.2, 0.6);

  // Select the clip and drag the fade handle one bar (2 s, clamped to the clip length).
  await page.locator(".se-clip").first().click();
  const handle = page.locator(".se-fade-handle");
  await expect(handle).toHaveCount(1);
  const box = await handle.boundingBox();
  if (!box) throw new Error("fade handle has no box");
  await page.mouse.move(box.x + 4, box.y + 4);
  await page.mouse.down();
  await page.mouse.move(box.x + 4 + 96, box.y + 4, { steps: 8 });
  await page.mouse.up();

  await expect.poll(lane, { timeout: 15_000 }).toBe(2);

  const faded = await wavWindowRms(await exportMix(), 0.2, 0.6);
  // The first 0.4 s now sits inside a 2 s ramp, so it must be clearly quieter.
  expect(faded).toBeLessThan(plain * 0.75);

  // Shift+F toggles the fade off, then on again with a short default.
  await page.locator(".se-clip").first().click();
  await page.keyboard.press("Shift+F");
  await expect.poll(lane, { timeout: 15_000 }).toBe(0);
  await page.locator(".se-clip").first().click();
  await page.keyboard.press("Shift+F");
  await expect.poll(lane, { timeout: 15_000 }).toBe(0.5);
});

test("fades are refused on a MIDI arrangement", async ({ page }) => {
  test.setTimeout(120_000);
  const projectId = await createStudioProject(page, {
    title: `Midi fade ${Math.random().toString(36).slice(2, 6)}`,
    clips: [
      {
        id: "midi-fade",
        title: "Keys",
        start: 0,
        duration: 4,
        midi: { notes: [{ id: "n1", pitch: 60, start: 0, length: 1, velocity: 100 }] },
      },
    ],
  });

  await page.locator(".se-clip").first().click();
  await page.keyboard.press("Shift+F");
  await expect(page.getByRole("status")).toContainText(
    "Fades only apply to audio arrangements"
  );

  // Nothing was written to the document.
  const fade = await page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    const project = (await response.json()) as {
      data?: { lanes?: Array<{ id: string; fadeIn?: number }> };
    };
    return project.data?.lanes?.[0]?.fadeIn ?? null;
  }, projectId);
  expect(fade).toBeNull();
});
