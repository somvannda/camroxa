import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * S29 take lanes: the footer control opens the band, a clip with no regenerations
 * shows the captured empty copy, and committing a generation over an existing audio
 * clip stacks takes (newest on top, active take switchable).
 */

test("take lanes show the empty copy and stack regenerated takes", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1689, height: 1277 });
  await createStudioProject(page, {
    title: "Takes",
    clips: [{ id: "base-clip", title: "Base Loop", start: 0, duration: 4, audioUrl: "/seed/demo-loop.wav" }],
  });

  // Empty state first: no clip regenerated yet.
  await page.locator(".se-clip").first().click();
  await page.getByRole("button", { name: "Take lanes", exact: true }).click();
  const band = page.getByRole("region", { name: "Take lanes" });
  await expect(band).toBeVisible();
  await expect(band.getByText("Create a clip to see alternate takes here")).toBeVisible();
  await page.getByRole("button", { name: "Take lanes", exact: true }).click();
  await expect(band).toHaveCount(0);

  // Generate and commit a take over the clip at 0.
  await page.route("**/api/v3/web-music/generate", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ task_id: "take-gen", status: "queued", title: "Loop", style: "pop" }),
    })
  );
  await page.route("**/api/v3/web-music/generations/take-gen", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "take-gen",
        title: "Loop",
        style: "pop",
        status: "complete",
        clips: [
          {
            variant: "v1",
            title: "Loop take 2",
            audio_url: "/seed/demo-loop.wav?take=2",
            download_url: "/seed/demo-loop.wav?take=2",
            duration_seconds: 4,
          },
        ],
      }),
    })
  );
  await page.getByLabel("Describe a part to generate").fill("A new drum loop over the clip");
  await page.getByRole("button", { name: "Generate this part" }).click();
  const assistant = page.getByRole("complementary", { name: "Studio assistant" });
  await expect(assistant.getByText(/Created Loop/)).toBeVisible({ timeout: 20_000 });
  await assistant.locator(".se-assistant-take").first().getByRole("button", { name: "Commit" }).click();

  // The regeneration stacked onto the clip instead of adding another clip.
  await expect(page.locator(".se-clip")).toHaveCount(1);
  const laneBand = page.getByRole("region", { name: "Take lanes" });
  await expect(laneBand).toBeVisible();
  const takeTwo = laneBand.getByRole("button", { name: "Use take 2" });
  const takeOne = laneBand.getByRole("button", { name: "Use take 1" });
  await expect(takeTwo).toHaveAttribute("aria-pressed", "true");
  await expect(takeOne).toHaveAttribute("aria-pressed", "false");
  await expect(takeTwo).toContainText("Loop take 2");

  await takeOne.click();
  await expect(takeOne).toHaveAttribute("aria-pressed", "true");
  await expect(takeTwo).toHaveAttribute("aria-pressed", "false");
});
