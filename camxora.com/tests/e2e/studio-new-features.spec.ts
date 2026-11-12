import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * New editor controls from the parity pass: chord/arpeggiator modes and ruler
 * section markers. These are document writes, so the specs read the project back
 * instead of trusting the transient DOM alone.
 */

test("MIDI chord and arpeggiator modes write the expected notes", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1689, height: 1277 });
  await createStudioProject(page, { title: "MIDI modes" });

  await page.getByRole("button", { name: /Add new track/ }).click();
  await page.getByRole("menuitem", { name: /MIDI/ }).click();

  const panel = page.getByRole("region", { name: "MIDI editor" });
  const grid = panel.locator(".se-midi-grid");
  await grid.click({ position: { x: 90, y: 140 } });
  await expect(panel.locator(".se-midi-note")).toHaveCount(1);

  await panel.getByLabel("Chord mode").selectOption("major");
  await grid.click({ position: { x: 200, y: 140 } });
  await expect(panel.locator(".se-midi-note")).toHaveCount(4);

  await panel.getByLabel("Chord mode").selectOption("off");
  await panel.getByLabel("Arpeggiator").selectOption("up");
  await grid.click({ position: { x: 300, y: 140 } });
  await expect(panel.locator(".se-midi-note")).toHaveCount(5);

  // The arpeggio spreads the notes left-to-right; the chord stacks them.
  const lefts = await panel.locator(".se-midi-note").evaluateAll((nodes) =>
    nodes.map((node) => Math.round((node as HTMLElement).getBoundingClientRect().left))
  );
  expect(new Set(lefts).size).toBeGreaterThan(1);
});

test("track Automation draws a volume point that persists", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1689, height: 1277 });
  await createStudioProject(page, { title: "Track automation" });

  await page.locator(".se-clip").first().click();
  await page.locator(".se-foot").getByRole("button", { name: "Automation" }).click();
  const panel = page.getByRole("region", { name: "Track automation" });
  const volumeLane = panel.getByRole("group", { name: "Volume automation lane" });
  await expect(volumeLane).toBeVisible();
  await volumeLane.click({ position: { x: 180, y: 30 } });
  await expect(panel.locator(".se-automation-point")).toHaveCount(1);

  await panel.getByRole("button", { name: "Pan" }).click();
  const panLane = panel.getByRole("group", { name: "Pan automation lane" });
  await panLane.click({ position: { x: 320, y: 40 } });
  await expect(panel.locator(".se-automation-point")).toHaveCount(1);

  await page.reload();
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  await page.locator(".se-clip").first().click();
  await page.locator(".se-foot").getByRole("button", { name: "Automation" }).click();
  const reloaded = page.getByRole("region", { name: "Track automation" });
  await expect(reloaded.locator(".se-automation-point")).toHaveCount(1);
  await reloaded.getByRole("button", { name: "Pan" }).click();
  await expect(reloaded.locator(".se-automation-point")).toHaveCount(1);
});

test("clip settings copy and paste through the clip menu", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1689, height: 1277 });
  const projectId = await createStudioProject(page, {
    title: "Clip settings copy",
    clips: [
      {
        id: "clip-a",
        title: "A",
        start: 0,
        duration: 4,
        audioUrl: "/seed/demo-loop.wav",
        audio: { gainDb: 6, pitch: 2 },
      },
      {
        id: "clip-b",
        title: "B",
        start: 8,
        duration: 4,
        audioUrl: "/seed/demo-loop.wav",
        audio: { gainDb: 0, pitch: 0 },
      },
    ],
  });

  await page.locator(".se-clip").filter({ hasText: "A" }).first().click({ button: "right" });
  await page.getByRole("menuitem", { name: /Copy settings/ }).click();
  await page.locator(".se-clip").filter({ hasText: "B" }).first().click({ button: "right" });
  await page.getByRole("menuitem", { name: /Paste settings/ }).click();

  const saved = await page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    return response.json();
  }, projectId);
  const clipB = saved.data.lanes.find((clip: { id: string }) => clip.id === "clip-b");
  expect(clipB.audio).toMatchObject({ gainDb: 6, pitch: 2 });
});

test("track groups create, assign and mute", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1689, height: 1277 });
  const projectId = await createStudioProject(page, { title: "Track groups" });

  const tracksPanel = page.locator(".se-tracks");
  await tracksPanel.getByRole("button", { name: "Track groups" }).click();
  const groupsPopover = page.locator(".se-groups-popover");
  await groupsPopover.getByRole("button", { name: "New" }).click();
  await groupsPopover.getByLabel(/Rename Group/).first().fill("Band");
  await tracksPanel.getByRole("button", { name: "Track groups" }).click();

  await page.getByLabel("Options for Track 1").click();
  await page.getByLabel("Group for Track 1").selectOption({ label: "Band" });
  await tracksPanel.getByRole("button", { name: "Track groups" }).click();
  await groupsPopover.getByRole("button", { name: "Mute Band" }).click();
  await page.waitForTimeout(1200);

  const saved = await page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    return response.json();
  }, projectId);
  expect(saved.data.groups).toHaveLength(1);
  expect(saved.data.groups[0]).toMatchObject({ name: "Band", muted: true });
  expect(saved.data.tracks[0].groupId).toBe(saved.data.groups[0].id);
});

test("Create Section stamps a ruler marker that survives a reload", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1689, height: 1277 });
  await createStudioProject(page, { title: "Section marker" });

  const clip = page.locator(".se-clip").first();
  await clip.click({ button: "right" });
  await page.getByRole("menuitem", { name: /Create Section/ }).click();

  const marker = page.locator(".se-section-marker");
  await expect(marker).toHaveCount(1);
  const label = await marker.first().getAttribute("aria-label");
  expect(label).toMatch(/Section .+ at /);

  await page.reload();
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".se-section-marker")).toHaveCount(1);
});
