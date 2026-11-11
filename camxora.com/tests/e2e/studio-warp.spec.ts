import { expect, test, type Page } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Warp markers (S30).
 *
 * Double-clicking an audio clip opens the captured Clip Settings editor: a Stretch
 * switch, the three modes with their captured tooltips, and white pennant markers on
 * the waveform. Markers are stored on the clip (`warp`), so the assertions read the
 * document back from the API rather than the DOM.
 */

type SavedWarp = {
  on?: boolean;
  mode?: string;
  markers?: Array<{ time: number; source: number }>;
};

async function savedWarp(page: Page, projectId: string): Promise<SavedWarp | null> {
  return page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    if (!response.ok) return null;
    const project = (await response.json()) as {
      data?: { lanes?: Array<{ id: string; warp?: SavedWarp }> };
    };
    return project.data?.lanes?.find((lane) => lane.id === "audio")?.warp ?? null;
  }, projectId);
}

async function openEditor(page: Page): Promise<void> {
  await page.locator(".se-clip").first().dblclick();
  await expect(page.getByRole("region", { name: "Clip settings" })).toBeVisible();
}

/**
 * A 4 s click track at 8 kHz: a short 1.2 kHz tick every 500 ms. The seed loop is a
 * steady tone, so transient detection needs real attacks to place markers on.
 */
function clickTrackWav(seconds = 4, rate = 8000, interval = 0.5): Buffer {
  const frames = seconds * rate;
  const data = Buffer.alloc(frames * 2);
  for (let index = 0; index < frames; index += 1) {
    const time = index / rate;
    const phase = time % interval;
    const value =
      phase < 0.03 ? Math.sin(2 * Math.PI * 1200 * time) * Math.exp(-phase * 120) : 0;
    data.writeInt16LE(Math.round(Math.max(-1, Math.min(1, value)) * 32000), index * 2);
  }
  const header = Buffer.alloc(44);
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + data.length, 4);
  header.write("WAVE", 8);
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(rate, 24);
  header.writeUInt32LE(rate * 2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write("data", 36);
  header.writeUInt32LE(data.length, 40);
  return Buffer.concat([header, data]);
}

test("double-click opens Clip Settings and On Beat fills the clip", async ({ page }) => {
  test.setTimeout(120_000);
  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Warp ${tag}`,
    clips: [
      { id: "audio", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  await openEditor(page);
  const stretch = page.getByRole("switch", { name: "Stretch" });
  expect(await stretch.getAttribute("aria-checked")).toBe("false");

  await page.getByRole("radio", { name: "On Beat" }).click();
  await expect.poll(async () => (await savedWarp(page, projectId))?.mode).toBe("beat");
  await expect(page.locator(".se-warp-head")).toHaveCount(9);
  expect(await stretch.getAttribute("aria-checked")).toBe("true");

  const warp = await savedWarp(page, projectId);
  expect(warp?.markers?.map((marker) => marker.time)).toEqual([
    0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4,
  ]);
});

test("transients place marker heads that can be selected, dragged and quantized", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const tag = Math.random().toString(36).slice(2, 8);
  const wav = clickTrackWav();
  await page.route("**/seed/warp-clicks.wav", (route) =>
    route.fulfill({ status: 200, contentType: "audio/wav", body: wav })
  );
  const projectId = await createStudioProject(page, {
    title: `Transients ${tag}`,
    clips: [
      {
        id: "audio",
        title: "Clicks",
        start: 0,
        duration: 4,
        audioUrl: "/seed/warp-clicks.wav",
      },
    ],
  });

  await openEditor(page);
  await page.getByRole("radio", { name: "Transients" }).click();
  await expect.poll(async () => (await savedWarp(page, projectId))?.mode).toBe("transients");

  const heads = page.locator(".se-warp-head");
  await expect(heads.first()).toBeVisible();
  const count = await heads.count();
  // Eight ticks in four seconds: the transient pass must find most of them.
  expect(count).toBeGreaterThan(4);

  // Ctrl+A selects every marker (spec §36).
  await page.keyboard.press("Control+a");
  await expect(page.locator(".se-warp-head[aria-pressed='true']")).toHaveCount(count);

  // Drag the second head, then quantize the selection back onto the grid.
  const box = await heads.nth(1).boundingBox();
  if (!box) throw new Error("marker head has no box");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 9, box.y + box.height / 2, { steps: 4 });
  await page.mouse.up();
  await page.keyboard.press("Shift+Q");

  await expect
    .poll(async () => {
      const warp = await savedWarp(page, projectId);
      const times = warp?.markers?.map((marker) => marker.time) ?? [];
      if (times.length === 0) return false;
      return times.every((time) => Math.abs(time * 2 - Math.round(time * 2)) < 0.0001);
    }, { timeout: 15_000, intervals: [250] })
    .toBe(true);

  // Switching Stretch off hides the heads but keeps the markers.
  await page.getByRole("switch", { name: "Stretch" }).click();
  await expect(heads).toHaveCount(0);
  await expect.poll(async () => (await savedWarp(page, projectId))?.on).toBe(false);
  const warp = await savedWarp(page, projectId);
  expect(warp?.markers?.length).toBeGreaterThan(1);
});
