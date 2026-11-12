import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Studio home actions (W1): rename, duplicate, archive/restore and delete.
 *
 * Also guards a stacking-context bug found here: the card applies a transform on hover,
 * which trapped its popover under later cards, so a click on "Archive" landed on the
 * card below and navigated into it. The card now lifts while its menu is open.
 */

test("home search narrows the grid", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const alpha = `Alpha ${tag}`;
  const beta = `Beta ${tag}`;
  await createStudioProject(page, { title: alpha });
  await createStudioProject(page, { title: beta });
  await page.goto("/studio");

  await expect(page.locator(".studio-home-grid .studio-card", { hasText: beta })).toBeVisible({ timeout: 30_000 });

  await page.getByLabel("Search projects").fill(alpha);
  await expect(page.locator(".studio-home-grid .studio-card", { hasText: alpha })).toBeVisible();
  await expect(page.locator(".studio-home-grid .studio-card", { hasText: beta })).toHaveCount(0);

  await page.getByLabel("Search projects").fill("zzz-no-such-project");
  await expect(page.locator(".studio-home-grid .studio-card", { hasText: alpha })).toHaveCount(0);
  await expect(page.locator(".studio-home-grid .studio-card", { hasText: beta })).toHaveCount(0);

  await page.getByLabel("Search projects").fill("");
  await expect(page.locator(".studio-home-grid .studio-card", { hasText: beta })).toBeVisible();
});

test("home renames, duplicates, archives and deletes a project", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const title = `Home ${tag}`;
  await createStudioProject(page, { title });
  await page.goto("/studio");

  const matching = (text: string) => page.locator(".studio-card", { hasText: text }).count();
  await expect(page.locator(".studio-home-grid .studio-card").first()).toBeVisible({ timeout: 30_000 });

  // Rename through the card menu.
  await page.getByRole("button", { name: `Actions for ${title}` }).first().click();
  await page.getByRole("menuitem", { name: "Rename" }).click();
  const renamed = `${title} renamed`;
  await page.getByLabel("Project title").fill(renamed);
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("button", { name: `Actions for ${renamed}` }).first()).toBeVisible({
    timeout: 15_000,
  });
  expect(await matching(renamed)).toBe(1);

  // The menu must actually be hittable, not covered by a card below it.
  await page.getByRole("button", { name: `Actions for ${renamed}` }).first().click();
  const archiveBox = await page.getByRole("menuitem", { name: "Archive" }).boundingBox();
  if (!archiveBox) throw new Error("archive menu item has no box");
  const hit = await page.evaluate(
    ({ x, y }) =>
      document.elementFromPoint(x, y)?.closest('[role="menuitem"]')?.textContent?.trim() ?? null,
    { x: archiveBox.x + 30, y: archiveBox.y + 15 }
  );
  expect(hit).toBe("Archive");

  // Duplicate (menu is still open on the same card).
  await page.getByRole("menuitem", { name: "Duplicate" }).click();
  await expect.poll(() => matching(renamed), { timeout: 15_000 }).toBe(2);

  // Archive the original only.
  await page.getByRole("button", { name: `Actions for ${renamed}`, exact: true }).first().click();
  await page.getByRole("menuitem", { name: "Archive" }).click();
  await expect.poll(() => matching(renamed), { timeout: 15_000 }).toBe(1);
  expect(page.url()).toContain("/studio");

  // Archived brings it back; both cards are listed again.
  await page.getByLabel("Archived").check();
  await expect.poll(() => matching(renamed), { timeout: 15_000 }).toBe(2);

  // Delete needs confirmation, then the card is gone for good.
  await page.getByRole("button", { name: `Actions for ${renamed} (copy)` }).first().click();
  await page.getByRole("menuitem", { name: "Delete" }).click();
  const dialog = page.getByRole("dialog", { name: `Delete “${renamed} (copy)”?` });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Delete" }).click();
  await expect.poll(() => matching(renamed), { timeout: 15_000 }).toBe(1);

  const deleted = await page.evaluate(async (copyTitle) => {
    const response = await fetch("/api/v3/web-music/studio/projects?limit=50");
    const body = (await response.json()) as { items?: Array<{ title: string }> };
    return (body.items ?? []).some((project) => project.title === copyTitle);
  }, `${renamed} (copy)`);
  expect(deleted).toBe(false);
});
