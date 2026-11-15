import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

const REFERENCE_VIEWPORT = { width: 1689, height: 1277 };

const JOB_PENDING = {
  job_id: "job-1",
  status: "pending",
  phase: "running",
  progress: [{ message: "Rendering test audio to verify the sound", stage: "probe_audio" }],
  plugin_id: null,
  plugin_version_id: null,
  display_name: null,
  descriptor: null,
  last_error: null,
};

const JOB_READY = {
  job_id: "job-1",
  status: "ready",
  phase: null,
  progress: [{ message: "Rendering test audio to verify the sound", stage: "probe_audio" }],
  plugin_id: "10c35bed-09ff-4bfe-86a8-f386bc281934",
  plugin_version_id: "53004c03-2451-47d2-957a-3acac99a626a",
  display_name: "Warm Tape",
  descriptor: {
    displayName: "Warm Tape",
    description: "A restrained stereo tape saturator that adds smooth warmth.",
    kind: "effect",
    parameters: [
      { name: "Drive", label: "Drive", default: 0.26, range: { min: 0, max: 1 }, unit: "percent" },
      { name: "Low Cut", label: "Low Cut", default: 140, range: { min: 20, max: 500 }, unit: "hz" },
    ],
  },
  last_error: null,
};

test("create-new-plugin authors through Suno and saves a draggable plugin", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);

  // The authoring agent lives behind the mirror; mock the two proxied calls so
  // the test exercises the real designer UI without spending credits.
  let polls = 0;
  await page.route("**/api/v3/web-music/studio/projects/*/plugins/author**", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ ...JOB_PENDING, progress: [] }),
      });
      return;
    }
    polls += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(polls === 1 ? JOB_PENDING : JOB_READY),
    });
  });

  await createStudioProject(page, { title: "Designer" });
  await page.getByRole("button", { name: "Track 1", exact: true }).click();

  await page.locator(".sp-add-inline").click();
  const catalog = page.getByRole("dialog", { name: "Add a track plugin" });
  await expect(catalog.getByText("My plugins")).toBeVisible();
  await catalog.getByRole("button", { name: /Create new plugin/ }).click();
  await expect(catalog).toHaveCount(0);

  // S45 entry: the Magic Bar takes design mode with the current object attached.
  const bar = page.locator(".se-prompt");
  await expect(bar).toHaveClass(/is-design/);
  const input = page.getByLabel("Describe a part to generate");
  await expect(input).toHaveValue(/Make me a new plugin\. Here's what I have in mind:/);
  await expect(bar.locator(".se-prompt-context.is-plugin")).toContainText("Track 1");
  const send = page.getByRole("button", { name: "Design this plugin" });
  await expect(send).toBeEnabled();
  await expect(send).toHaveClass(/is-active/);

  await input.fill("A warm tape saturation plugin with gentle drive and a low cut");
  await send.click();

  // The designer restates the request, asks, and says the agent spends credits.
  const assistant = page.getByRole("complementary", { name: "Studio assistant" });
  await expect(assistant.getByText(/plugin agent/)).toBeVisible();
  await expect(assistant.getByText(/saved to your plugin library/)).toBeVisible();
  await expect(assistant.getByRole("button", { name: "Build it" })).toBeVisible();
  await expect(assistant.getByRole("button", { name: "Change something…" })).toBeVisible();
  await expect(page.locator(".sp-slot")).toHaveCount(0);

  await assistant.getByRole("button", { name: "Build it" }).click();
  // While the agent works, its progress is shown verbatim.
  await expect(assistant.getByText(/Rendering test audio to verify the sound/)).toBeVisible();
  await expect(assistant.getByText(/Warm Tape is ready with/)).toBeVisible({ timeout: 30_000 });

  // The result is a card, never an inserted plugin.
  const card = page.getByLabel("Warm Tape, designed plugin");
  await expect(card).toBeVisible();
  await expect(card).toContainText("Audio effect · Drag onto a track");
  await expect(card).toHaveAttribute("draggable", "true");
  await expect(page.locator(".sp-slot")).toHaveCount(0);
  expect(polls).toBeGreaterThan(0);

  await card.getByRole("button", { name: "Add to track" }).click();
  const slot = page.locator(".sp-slot").first();
  await expect(slot).toContainText("Warm Tape");
  // Percent controls keep Suno's 0–1 value; the knob shows 0.26, not 26.
  await expect(slot.getByRole("slider", { name: "Drive" })).toHaveValue("0.26");
  await expect(slot.getByRole("slider", { name: "Low Cut" })).toHaveValue("140");

  // MY PLUGINS now lists the authored plugin next to Create new plugin.
  await page.locator(".sp-add").click();
  const again = page.getByRole("dialog", { name: "Add a track plugin" });
  await expect(again.getByRole("button", { name: /^Warm Tape/ })).toBeVisible();
  await again.getByRole("button", { name: "Close" }).click();
});
