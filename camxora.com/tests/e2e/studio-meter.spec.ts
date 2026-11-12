import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Time signature (H-13): the meter is editable and the bar maths follow it.
 *
 * At 120 BPM: 4/4 bars are 2 s, 3/4 bars are 1.5 s. Clicking three bars in therefore
 * lands at 4.5 s in 3/4 (bar 4 beat 1) rather than 6 s.
 */

test("changing the meter rescales bars and persists", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, { title: `Meter ${tag}` });

  const signature = page.getByLabel("Time signature");
  await expect(signature).toHaveValue("4/4");

  // Default 4/4: three bars in = 6 s.
  await page.locator(".se-lanes").click({ position: { x: 288, y: 40 } });
  await expect(page.getByLabel("Time", { exact: true })).toHaveText("00:06.000");

  await signature.selectOption("3/4");
  await expect.poll(
    () =>
      page.evaluate(async (id) => {
        const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
        const project = (await response.json()) as { time_signature?: string };
        return project.time_signature;
      }, projectId),
    { timeout: 15_000 }
  ).toBe("3/4");

  // Three bars at 3/4 = 4.5 s, and the readout counts in threes.
  await page.locator(".se-lanes").click({ position: { x: 288, y: 40 } });
  await expect(page.getByLabel("Time", { exact: true })).toHaveText("00:04.500");
  await expect(page.getByLabel("Bar and beat", { exact: true })).toHaveText("004.1.1");

  // Reload keeps the meter.
  await page.reload();
  await expect(page.getByLabel("Time signature")).toHaveValue("3/4", { timeout: 30_000 });
});
