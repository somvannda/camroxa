import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Clip trim grips (S25): the selected clip shows a vertical grip at each end. Dragging
 * the right one changes the duration; the left one moves the start and the content
 * offset together, so the audio under the clip does not shift.
 */

test("trimming from the right changes duration and from the left moves the offset", async ({
  page,
}) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, {
    title: `Trim ${tag}`,
    clips: [
      { id: "clip", title: "Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" },
    ],
  });

  const lane = () =>
    page.evaluate(async (id) => {
      const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
      const project = (await response.json()) as {
        data?: { lanes?: Array<{ start?: number; duration?: number; offset?: number }> };
      };
      const first = project.data?.lanes?.[0];
      return { start: first?.start, duration: first?.duration, offset: first?.offset ?? 0 };
    }, projectId);

  const clip = page.locator(".se-clip").first();
  await clip.click();
  await expect(page.locator(".se-trim-end")).toHaveCount(1);

  // Right grip: +1 bar (96 px = 2 s at 120 BPM) → duration 6.
  const end = page.locator(".se-trim-end");
  const endBox = await end.boundingBox();
  if (!endBox) throw new Error("end grip has no box");
  await page.mouse.move(endBox.x + 3, endBox.y + 20);
  await page.mouse.down();
  await page.mouse.move(endBox.x + 3 + 96, endBox.y + 20, { steps: 8 });
  await page.mouse.up();

  await expect.poll(async () => (await lane()).duration, { timeout: 15_000 }).toBe(6);
  expect((await lane()).start).toBe(0);

  // Left grip: +1 bar moves start to 2 s, duration to 4, offset to 2.
  const start = page.locator(".se-trim-start");
  const startBox = await start.boundingBox();
  if (!startBox) throw new Error("start grip has no box");
  await page.mouse.move(startBox.x + 3, startBox.y + 20);
  await page.mouse.down();
  await page.mouse.move(startBox.x + 3 + 96, startBox.y + 20, { steps: 8 });
  await page.mouse.up();

  await expect.poll(async () => (await lane()).start, { timeout: 15_000 }).toBe(2);
  const trimmed = await lane();
  expect(trimmed.duration).toBe(4);
  expect(trimmed.offset).toBe(2);

  // Reload draws the trimmed clip at the new position and width.
  await page.reload();
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  const geometry = await page.locator(".se-clip").first().evaluate((element) => {
    const style = (element as HTMLElement).style;
    return { left: style.left, width: style.width };
  });
  // 2 s in = one bar = 96 px; 4 s = two bars = 192 px.
  expect(Number.parseFloat(geometry.left)).toBeCloseTo(96, 0);
  expect(Number.parseFloat(geometry.width)).toBeCloseTo(192, 0);
});
