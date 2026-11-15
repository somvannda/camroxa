import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * S04 "Recently Deleted": deletion is soft, the tab lists deleted projects, and Restore
 * puts the document back in Projects (spec §56, behaviour note 3).
 */

test("a deleted project lands in Recently Deleted and can be restored", async ({ page }) => {
  test.setTimeout(120_000);
  const tag = Math.random().toString(36).slice(2, 8);
  const title = `Soft delete ${tag}`;
  const projectId = await createStudioProject(page, { title });

  // Delete from the Studio home card menu (the only delete entry point).
  await page.goto("/studio");
  await page.getByRole("button", { name: `Actions for ${title}` }).click();
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await expect(page.getByRole("heading", { name: new RegExp(`Delete .${title}`) })).toBeVisible();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(page.getByRole("button", { name: `Actions for ${title}` })).toHaveCount(0);

  // The document is hidden from every normal list and lookup.
  const hidden = await page.evaluate(async (id) => {
    const detail = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    const list = await fetch("/api/v3/web-music/studio/projects?limit=100");
    const body = (await list.json()) as { items?: Array<{ id: string }> };
    return {
      detail: detail.status,
      listed: Boolean(body.items?.some((item) => item.id === id)),
    };
  }, projectId);
  expect(hidden).toEqual({ detail: 404, listed: false });

  // A scratch project gives us the editor's project menu.
  await createStudioProject(page, { title: `Scratch ${tag}` });
  await page.getByRole("button", { name: /Scratch/ }).click();
  await page.getByRole("menuitem", { name: /My Projects|Open Project/i }).first().click();
  const modal = page.getByRole("dialog", { name: "Open project" });
  await expect(modal).toBeVisible();

  await modal.getByRole("tab", { name: "Recently Deleted" }).click();
  const restore = modal.getByRole("button", { name: `Restore ${title}` });
  await expect(restore).toBeVisible();
  await restore.click();

  // Restore returns to the Projects tab with the project listed and readable again.
  await expect(modal.getByRole("button", { name: `Open ${title}` })).toBeVisible();
  const visible = await page.evaluate(async (id) => {
    const detail = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    return detail.status;
  }, projectId);
  expect(visible).toBe(200);
});
