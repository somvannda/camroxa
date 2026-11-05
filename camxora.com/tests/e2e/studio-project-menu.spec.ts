import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

/**
 * Project menu (reference §18.1/G13): the captured items exist, rename persists, and
 * the three items this build cannot honour are disabled rather than missing.
 */

test("project menu renames the project and the name survives a reload", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const original = `Menu ${tag}`;
  const renamed = `Renamed ${tag}`;

  const projectId = await createStudioProject(page, { title: original });
  const chip = page.locator(".se-project .se-chip");
  await expect(chip).toHaveText(original);

  await chip.click();
  const menu = page.getByRole("menu", { name: "Project options" });
  await expect(menu).toBeVisible();

  // The order matches the capture; the two we cannot honour are disabled.
  await expect(menu.getByRole("menuitem")).toHaveCount(9);
  await expect(menu.getByRole("menuitem").nth(5)).toBeEnabled(); // Share Project
  await expect(menu.getByRole("menuitem").nth(6)).toBeDisabled(); // v1 copy
  await expect(menu.getByRole("menuitem").nth(7)).toBeDisabled(); // Settings

  await menu.getByRole("menuitem", { name: "Rename" }).click();
  const dialog = page.getByRole("dialog", { name: "Rename project" });
  await expect(dialog).toBeVisible();
  const input = dialog.getByLabel("Project title");
  await expect(input).toHaveValue(original);
  await input.fill(renamed);
  await dialog.getByRole("button", { name: "Save" }).click();

  await expect(dialog).toHaveCount(0);
  await expect(chip).toHaveText(renamed);

  // Persisted, not just local state.
  const stored = await page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    return ((await response.json()) as { title?: string }).title ?? null;
  }, projectId);
  expect(stored).toBe(renamed);

  await page.reload();
  await expect(page.locator(".se-project .se-chip")).toHaveText(renamed);
});

test("share creates a view link that resolves without the editor", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `Share ${tag}` });

  await page.locator(".se-project .se-chip").click();
  await page.getByRole("menuitem", { name: "Share Project" }).click();

  const dialog = page.getByRole("dialog", { name: "Share project" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(/view this project and make their own editable copy/)).toBeVisible();

  const link = dialog.getByLabel("Share link");
  await expect(link).toHaveValue(/\/studio\/shared\/.+$/);

  // The link is view + fork: the public share endpoint must answer for its token.
  const href = await link.inputValue();
  const token = href.split("/studio/shared/")[1];
  const shared = await page.request.get(`/api/v3/web-music/studio/shares/${token}`);
  expect(shared.status()).toBe(200);
  const body = (await shared.json()) as { title?: string };
  expect(body.title).toBe(`Share ${tag}`);

  await dialog.getByRole("button", { name: "Done" }).click();
  await expect(dialog).toHaveCount(0);
});
