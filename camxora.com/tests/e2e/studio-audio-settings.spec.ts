import { readFile } from "node:fs/promises";

import { expect, test, type Page } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Clip Settings audio state (spec §81): Volume, Loop, Reverse, Pitch and Speed.
 *
 * The pure maths is unit-tested (`tests/studio-clip-audio.test.ts`); this proves the
 * panel persists what it shows and that a volume trim really reaches the exported mix.
 */

async function openClipSettings(page: Page) {
  await page.locator(".se-clip").first().dblclick();
  await expect(panel(page)).toBeVisible();
  return panel(page);
}

function panel(page: Page) {
  return page.getByRole("region", { name: "Clip settings" });
}

/** React-controlled range inputs need the native setter before dispatching. */
async function setRange(locator: ReturnType<typeof panel>, value: string): Promise<void> {
  await locator.getByLabel("Volume", { exact: true }).evaluate((element, next) => {
    const input = element as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    setter?.call(input, next);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }, value);
}

type SavedAudio = {
  gainDb?: number;
  loop?: boolean;
  reverse?: boolean;
  pitch?: number;
  speed?: number;
};

async function savedAudio(page: Page, projectId: string): Promise<SavedAudio | null> {
  return page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    if (!response.ok) return null;
    const project = (await response.json()) as {
      data?: { lanes?: Array<{ id: string; audio?: SavedAudio }> };
    };
    return project.data?.lanes?.find((lane) => lane.id === "loop")?.audio ?? null;
  }, projectId);
}

/** RMS of a 16-bit PCM WAV, ignoring the header. */
function wavRms(bytes: Buffer): number {
  let sum = 0;
  let count = 0;
  for (let offset = 44; offset + 1 < bytes.length; offset += 2) {
    const sample = bytes.readInt16LE(offset) / 32768;
    sum += sample * sample;
    count += 1;
  }
  return count === 0 ? 0 : Math.sqrt(sum / count);
}

test("the clip editor persists volume, loop, reverse, pitch and speed", async ({ page }) => {
  test.setTimeout(120_000);
  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Clip settings ${tag}`,
    clips: [
      { id: "loop", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  const editor = await openClipSettings(page);

  await setRange(editor, "-6");
  await editor.getByRole("button", { name: "Loop", exact: true }).click();
  await editor.getByRole("button", { name: "Reverse" }).click();
  await editor.getByRole("button", { name: "Raise pitch" }).click();
  await editor.getByRole("button", { name: "Raise pitch" }).click();
  await editor.getByRole("button", { name: "×2" }).click();

  await expect
    .poll(async () => await savedAudio(page, projectId), { timeout: 15_000, intervals: [250] })
    .toMatchObject({ gainDb: -6, loop: true, reverse: true, pitch: 2, speed: 200 });

  // The panel reads its own state back, not just the document.
  await expect(editor.getByText("-6.0 dB")).toBeVisible();
  await expect(editor.getByText("200%")).toBeVisible();
});

test("a volume trim reaches the exported mix", async ({ page }) => {
  test.setTimeout(120_000);
  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, {
    title: `Clip gain ${tag}`,
    clips: [
      { id: "loop", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  async function exportMix(): Promise<Buffer> {
    await page.getByLabel("Export menu").click();
    const download = page.waitForEvent("download");
    await page.getByRole("menuitem", { name: "Full Song" }).click();
    const file = await download;
    const path = await file.path();
    if (!path) throw new Error("export has no path");
    return readFile(path);
  }

  const dry = await exportMix();
  expect(wavRms(dry)).toBeGreaterThan(0.001);

  await openClipSettings(page);
  await setRange(panel(page), "-12");
  await panel(page).getByRole("button", { name: "Close clip editor" }).click();

  const quiet = await exportMix();
  expect(quiet.length).toBe(dry.length);
  const ratio = wavRms(quiet) / wavRms(dry);
  // −12 dB is a quarter of the amplitude.
  expect(ratio).toBeGreaterThan(0.2);
  expect(ratio).toBeLessThan(0.32);
});
