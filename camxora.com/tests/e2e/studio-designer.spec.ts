import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

const REFERENCE_VIEWPORT = { width: 1689, height: 1277 };

test("create-new-plugin opens the designer and saves a draggable plugin", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize(REFERENCE_VIEWPORT);
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

  // The designer asks before building and says where the plugin will live.
  const assistant = page.getByRole("complementary", { name: "Studio assistant" });
  await expect(assistant.getByText(/saved to your plugin library/)).toBeVisible();
  await expect(assistant.getByRole("button", { name: "Build it" })).toBeVisible();
  await expect(assistant.getByRole("button", { name: "Change something…" })).toBeVisible();
  await expect(page.locator(".sp-slot")).toHaveCount(0);

  await assistant.getByRole("button", { name: "Build it" }).click();
  await expect(assistant.getByText(/Warm Tape is ready with/)).toBeVisible();

  // The result is a card, never an inserted plugin.
  const card = page.getByLabel("Warm Tape, designed plugin");
  await expect(card).toBeVisible();
  await expect(card).toContainText("Audio effect · Drag onto a track");
  await expect(card).toHaveAttribute("draggable", "true");
  await expect(page.locator(".sp-slot")).toHaveCount(0);

  await card.getByRole("button", { name: "Add to track" }).click();
  const slot = page.locator(".sp-slot").first();
  await expect(slot).toContainText("Warm Tape");
  await expect(slot.getByRole("slider", { name: "Drive" })).toHaveValue("26");
  await expect(slot.getByRole("slider", { name: "Low Cut" })).toHaveValue("140");

  // MY PLUGINS now lists the designed plugin next to Create new plugin.
  await page.locator(".sp-add").click();
  const again = page.getByRole("dialog", { name: "Add a track plugin" });
  await expect(again.getByRole("button", { name: /^Warm Tape/ })).toBeVisible();
  await again.getByRole("button", { name: "Close" }).click();
});
