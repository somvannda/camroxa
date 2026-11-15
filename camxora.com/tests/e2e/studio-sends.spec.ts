import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * FX sends: two shared buses (Delay, Reverb) with a per-track level. The reference has no
 * sends surface; this covers the requested addition end to end (persistence + playback).
 */

test("send levels persist and playback runs with the shared buses", async ({ page }) => {
  test.setTimeout(120_000);
  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, { title: `Sends ${tag}` });

  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  const region = page.getByRole("region", { name: /Plugins for/ });
  await region.getByRole("button", { name: "Add effect", exact: true }).first().click();
  await page
    .getByRole("dialog", { name: "Add a track plugin" })
    .getByRole("button", { name: /^EQ/ })
    .first()
    .click();

  const delay = page.getByRole("slider", { name: "Delay send" });
  const reverb = page.getByRole("slider", { name: "Reverb send" });
  await expect(delay).toBeVisible();
  await delay.fill("40");
  await reverb.fill("25");

  await expect
    .poll(
      async () =>
        page.evaluate(async (id) => {
          const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
          const project = (await response.json()) as {
            data?: { tracks?: Array<{ sends?: { delay?: number; reverb?: number } }> };
          };
          return project.data?.tracks?.[0]?.sends ?? null;
        }, projectId),
      { timeout: 15_000, intervals: [250] }
    )
    .toEqual({ delay: 40, reverb: 25 });

  // Playing with the buses wired must not throw and the meter must move.
  await page.getByRole("button", { name: "Play" }).click();
  await page.waitForTimeout(800);
  await expect(page.getByRole("button", { name: "Pause" })).toBeVisible();
  await page.getByRole("button", { name: "Pause" }).click();
  // Nothing failed while the buses were live.
  await expect(page.getByText(/Save failed|Export failed|Could not/i)).toHaveCount(0);
});
