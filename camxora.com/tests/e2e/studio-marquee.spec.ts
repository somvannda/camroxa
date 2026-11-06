import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Marquee selection and multi-drag (W3, spec §26/G6): a rubber band selects the clips it
 * touches, and dragging one selected clip moves the whole group by the same amount.
 */

test("marquee selects clips and dragging one moves the selection", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, {
    title: `Marquee ${tag}`,
    clips: [
      { id: "clip-a", title: "A", start: 0, duration: 2 },
      { id: "clip-b", title: "B", start: 4, duration: 2 },
    ],
  });

  const clips = page.locator(".se-clip");
  await expect(clips).toHaveCount(2);

  const lanes = page.locator(".se-lanes");
  const box = await lanes.boundingBox();
  if (!box) throw new Error("lanes have no box");

  // Start on empty lane space to the right of both clips, then band leftwards.
  await page.mouse.move(box.x + 400, box.y + 20);
  await page.mouse.down();
  await page.mouse.move(box.x + 6, box.y + 70, { steps: 10 });
  await page.mouse.up();

  await expect(page.locator(".se-clip.selected")).toHaveCount(2);

  const leftOf = (index: number) =>
    clips.nth(index).evaluate((element) => (element as HTMLElement).style.left);
  const before = [await leftOf(0), await leftOf(1)];

  // Drag the first selected clip one bar to the right: the second must follow.
  const firstBox = await clips.first().boundingBox();
  if (!firstBox) throw new Error("clip has no box");
  await page.mouse.move(firstBox.x + 12, firstBox.y + 10);
  await page.mouse.down();
  await page.mouse.move(firstBox.x + 12 + 96, firstBox.y + 10, { steps: 8 });
  await page.mouse.up();

  await expect.poll(() => leftOf(0), { timeout: 10_000 }).not.toBe(before[0]);
  await expect.poll(() => leftOf(1), { timeout: 10_000 }).not.toBe(before[1]);

  const delta = (a: string, b: string) => Number.parseFloat(a) - Number.parseFloat(b);
  const movedA = delta(await leftOf(0), before[0]);
  const movedB = delta(await leftOf(1), before[1]);
  expect(Math.abs(movedA - 96)).toBeLessThan(2);
  expect(Math.abs(movedB - movedA)).toBeLessThan(0.5);
});
