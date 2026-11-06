import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Zoom (W3): the presets change the bar pitch, and "Fit to content" derives a pitch that
 * brings the whole arrangement inside the viewport (it used to reset to a preset).
 *
 * Clips outside the visible window plus one screen of slack are culled (G19), so the
 * assertions use the first clip for pitch and the rendered set after a fit.
 */

test("zoom presets scale the timeline and fit brings all clips into view", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, {
    title: `Zoom ${tag}`,
    clips: [
      { id: "left", title: "Left", start: 0, duration: 2 },
      // 30 s in: outside the default double-screen culling window once zoomed in.
      { id: "right", title: "Right", start: 30, duration: 2 },
    ],
  });

  const firstWidth = () =>
    page
      .locator(".se-clip")
      .first()
      .evaluate((el) => Number.parseFloat((el as HTMLElement).style.width));

  const initial = await firstWidth();
  await page.getByLabel("Zoom in").click();
  await expect.poll(firstWidth, { timeout: 10_000 }).toBeGreaterThan(initial);
  const zoomed = await firstWidth();

  // Fit derives the pitch from the arrangement: every clip ends inside the viewport.
  await page.getByLabel("Fit to content").click();
  const fitted = await firstWidth();
  expect(fitted).toBeLessThan(zoomed);
  await expect(page.locator(".se-clip")).toHaveCount(2);

  const afterFit = await page.evaluate(() => {
    const el = document.querySelector(".se-timeline") as HTMLElement | null;
    if (!el) return null;
    const origin = el.getBoundingClientRect().left;
    const edges = [...document.querySelectorAll<HTMLElement>(".se-clip")].map(
      (clip) => clip.getBoundingClientRect().right - origin
    );
    return { count: edges.length, overflow: Math.max(0, ...edges) - el.clientWidth };
  });
  expect(afterFit?.count).toBe(2);
  expect(afterFit?.overflow ?? 1).toBeLessThanOrEqual(2);

  // Fit is not sticky: zooming in still works afterwards.
  await page.getByLabel("Zoom in").click();
  await expect.poll(firstWidth, { timeout: 10_000 }).toBeGreaterThan(fitted);
});
