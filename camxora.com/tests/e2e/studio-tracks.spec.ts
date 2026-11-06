import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Track operations (W3, spec §65): duplicate clones the track *and* its clips, rename
 * persists, Hide & Mute is one action, and delete removes the track with its clips.
 */

test("a track can be duplicated, renamed, hidden and deleted", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, { title: `Tracks ${tag}` });

  const server = () =>
    page.evaluate(async (id) => {
      const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
      const project = (await response.json()) as {
        data?: { lanes?: unknown[]; tracks?: Array<{ name?: string; hidden?: boolean }> };
      };
      return {
        lanes: project.data?.lanes?.length ?? 0,
        tracks: project.data?.tracks?.length ?? 0,
        names: (project.data?.tracks ?? []).map((track) => track.name),
        hidden: (project.data?.tracks ?? []).filter((track) => track.hidden).length,
      };
    }, projectId);

  const menuFor = (name: string) =>
    page.getByRole("button", { name: `Options for ${name}`, exact: true });

  // Duplicate: the copy owns its own clips, not a shared reference.
  await menuFor("Track 1").click();
  await page.getByRole("menuitem", { name: "Duplicate" }).click();
  await expect(page.locator(".se-track")).toHaveCount(2);
  await expect(page.locator(".se-clip")).toHaveCount(2);
  await expect.poll(async () => (await server()).lanes, { timeout: 15_000 }).toBe(2);

  // Rename the copy.
  await menuFor("Track 1 copy").click();
  await page.getByRole("menuitem", { name: "Rename track" }).click();
  const input = page.locator(".se-track-rename");
  await input.fill("Drums");
  await input.press("Enter");
  await expect(page.getByRole("button", { name: "Drums", exact: true })).toBeVisible();
  await expect.poll(async () => (await server()).names, { timeout: 15_000 }).toContain("Drums");

  // Hide & Mute is one action: the row disappears and the hidden pill appears.
  await menuFor("Drums").click();
  await page.getByRole("menuitem", { name: "Hide & Mute Track" }).click();
  await expect(page.locator(".se-track")).toHaveCount(1);
  await expect(page.getByLabel("1 hidden track")).toBeVisible();
  await expect.poll(async () => (await server()).hidden, { timeout: 15_000 }).toBe(1);

  // Show all hidden brings it back.
  await page.getByLabel("1 hidden track").click();
  await page.getByRole("button", { name: "Show all" }).click();
  await expect(page.locator(".se-track")).toHaveCount(2);

  // Delete the copy: its clip goes with it.
  await menuFor("Drums").click();
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await expect(page.locator(".se-track")).toHaveCount(1);
  await expect(page.locator(".se-clip")).toHaveCount(1);
  const final = await (async () => {
    await expect.poll(async () => (await server()).tracks, { timeout: 15_000 }).toBe(1);
    return server();
  })();
  expect(final.lanes).toBe(1);
  expect(final.names).toEqual(["Track 1"]);
});

test("track level and pan sliders persist, and collapse hides them", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const projectId = await createStudioProject(page, { title: `Sliders ${tag}` });

  const track = () =>
    page.evaluate(async (id) => {
      const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
      const project = (await response.json()) as {
        data?: { tracks?: Array<{ volume?: number; pan?: number; collapsed?: boolean }> };
      };
      const first = project.data?.tracks?.[0];
      return { volume: first?.volume, pan: first?.pan, collapsed: first?.collapsed };
    }, projectId);

  const volume = page.getByRole("slider", { name: "Volume Track 1" });
  const pan = page.getByRole("slider", { name: "Pan Track 1" });
  await expect(volume).toBeVisible();
  await expect(volume).toHaveValue("80");

  await volume.fill("50");
  await volume.press("Tab");
  await expect.poll(async () => (await track()).volume, { timeout: 15_000 }).toBe(50);

  await pan.fill("-40");
  await pan.press("Tab");
  await expect.poll(async () => (await track()).pan, { timeout: 15_000 }).toBe(-40);

  // Collapse controls hides the sliders and persists the state.
  await page.getByRole("button", { name: "Options for Track 1", exact: true }).click();
  await page.getByRole("menuitem", { name: "Collapse controls" }).click();
  await expect(volume).toHaveCount(0);
  await expect.poll(async () => (await track()).collapsed, { timeout: 15_000 }).toBe(true);

  await page.getByRole("button", { name: "Options for Track 1", exact: true }).click();
  await page.getByRole("menuitem", { name: "Expand controls" }).click();
  await expect(page.getByRole("slider", { name: "Volume Track 1" })).toBeVisible();
  await expect.poll(async () => (await track()).collapsed, { timeout: 15_000 }).toBe(false);
});
