import { expect, test } from "@playwright/test";

import { signIn } from "./studio-fixture";

/**
 * Library "Audio +" menu.
 *
 * The menu used to open a panel that only said uploads/recording were not
 * enabled. It now opens the working flow in Create with the right intent, so the
 * dead end is gone.
 */

test("library audio actions open the working upload and record flows", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.goto("/library");
  await expect(page.getByRole("tablist", { name: "Library sections" })).toBeVisible({
    timeout: 30_000,
  });

  await page.getByRole("button", { name: "Audio actions" }).click();
  await page.getByRole("menuitem", { name: /^Upload/ }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("file picker opens in Create");

  await dialog.getByRole("link", { name: /Open the uploader/ }).click();
  await expect(page).toHaveURL(/\/create$/);
  const createDialog = page.getByRole("dialog");
  await expect(createDialog.getByText("Add audio")).toBeVisible({ timeout: 30_000 });
  await createDialog.getByRole("button", { name: "Close", exact: true }).last().click();
  await expect(createDialog).toHaveCount(0);
});
