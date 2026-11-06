import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Drag hints and track colour (W3): the snap guideline appears only while dragging, and
 * the colour menu writes the chosen colour to the document.
 */

test("the snap guideline shows while dragging and disappears on drop", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, {
    title: `Hints ${tag}`,
    clips: [{ id: "clip", title: "Clip", start: 0, duration: 2 }],
  });

  const clip = page.locator(".se-clip").first();
  const box = await clip.boundingBox();
  if (!box) throw new Error("clip has no box");

  await page.mouse.move(box.x + 40, box.y + 40);
  await page.mouse.down();
  await page.mouse.move(box.x + 40 + 40, box.y + 40, { steps: 4 });
  await expect(page.locator(".se-snap-line")).toHaveCount(1);
  await page.mouse.up();
  await expect(page.locator(".se-snap-line")).toHaveCount(0);
});

test("the track menu writes a chosen colour", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, { title: `Colour ${tag}` });

  await page.getByRole("button", { name: "Options for Track 1", exact: true }).click();
  await page.getByRole("menuitem", { name: "Collapse controls" }).waitFor();
  const swatch = page.getByRole("button", { name: "Use #a78bfa" });
  await expect(swatch).toBeVisible();
  await swatch.click();

  await expect
    .poll(
      () =>
        page.evaluate(async (id) => {
          const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
          const project = (await response.json()) as { data?: { tracks?: Array<{ color?: string }> } };
          return project.data?.tracks?.[0]?.color;
        }, projectId),
      { timeout: 15_000 }
    )
    .toBe("#a78bfa");

  // The row echoes it immediately.
  await expect(page.locator(".se-track-color").first()).toHaveCSS(
    "background-color",
    "rgb(167, 139, 250)"
  );
});
