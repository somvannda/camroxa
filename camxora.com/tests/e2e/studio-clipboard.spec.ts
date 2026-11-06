import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Clipboard and delete (W3, spec §36/G6/G9): copy/paste/duplicate create independent
 * clips, delete removes the selection and keeps keyboard focus on a neighbour, and undo
 * puts the deleted clips back.
 */

test("copy, paste, duplicate, delete and undo keep the arrangement consistent", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, { title: `Clipboard ${tag}` });

  const clips = page.locator(".se-clip");
  const serverLanes = () =>
    page.evaluate(async (id) => {
      const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
      const project = (await response.json()) as { data?: { lanes?: unknown[] } };
      return project.data?.lanes?.length ?? 0;
    }, projectId);

  await clips.first().click();
  await expect(clips).toHaveCount(1);

  // Copy + paste creates a second, independent clip.
  await page.keyboard.press("Control+c");
  await page.keyboard.press("Control+v");
  await expect(clips).toHaveCount(2);

  // Duplicate the (still selected) pasted clip.
  await page.keyboard.press("Control+d");
  await expect(clips).toHaveCount(3);
  await expect.poll(serverLanes, { timeout: 15_000 }).toBe(3);

  // Delete removes the selected clip and moves focus to a remaining one.
  await page.keyboard.press("Delete");
  await expect(clips).toHaveCount(2);
  const focused = await page.evaluate(() => {
    const active = document.activeElement as HTMLElement | null;
    return { tag: active?.tagName ?? null, isClip: active?.classList.contains("se-clip") ?? false };
  });
  expect(focused.tag).toBe("BUTTON");
  expect(focused.isClip).toBe(true);
  await expect.poll(serverLanes, { timeout: 15_000 }).toBe(2);

  // Undo restores the deleted clip.
  await page.keyboard.press("Control+z");
  await expect(clips).toHaveCount(3);
  await expect.poll(serverLanes, { timeout: 15_000 }).toBe(3);

  // The pasted copies are independent: moving one does not move its source.
  const first = clips.first();
  const last = clips.last();
  const before = {
    first: await first.evaluate((el) => (el as HTMLElement).style.left),
    last: await last.evaluate((el) => (el as HTMLElement).style.left),
  };
  const box = await last.boundingBox();
  if (!box) throw new Error("clip has no box");
  await page.mouse.move(box.x + 12, box.y + 10);
  await page.mouse.down();
  await page.mouse.move(box.x + 12 + 96, box.y + 10, { steps: 6 });
  await page.mouse.up();

  await expect
    .poll(() => last.evaluate((el) => (el as HTMLElement).style.left), { timeout: 10_000 })
    .not.toBe(before.last);
  expect(await first.evaluate((el) => (el as HTMLElement).style.left)).toBe(before.first);
});
