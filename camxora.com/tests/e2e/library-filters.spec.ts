import { expect, test } from "@playwright/test";

import { signIn } from "./studio-fixture";

/**
 * Library filters.
 *
 * The reference exposes a wide filter set; our corpus only backs some of it. This spec
 * pins the honest split: data-backed filters are live, the rest stay visible and say
 * why they cannot work yet, and a selection can be cleared.
 */

test("library filters are only enabled where the corpus supports them", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.goto("/library");
  await expect(page.getByRole("tablist", { name: "Library sections" })).toBeVisible({
    timeout: 30_000,
  });

  await page.getByRole("button", { name: /^Filters/ }).click();
  const menu = page.getByRole("menu");

  // Backed by `instrumental` on the generation.
  await expect(menu.getByRole("menuitemcheckbox", { name: "Vocals" })).toBeEnabled();
  await expect(menu.getByRole("menuitemcheckbox", { name: "Instrumental" })).toBeEnabled();
  await expect(menu.getByRole("menuitemcheckbox", { name: "Full song" })).toBeEnabled();
  await expect(menu.getByRole("menuitemcheckbox", { name: "Ready to play" })).toBeEnabled();

  // Not modelled: visible, disabled, and carrying the reason.
  const publicFilter = menu.getByRole("menuitemcheckbox", { name: "Public" });
  await expect(publicFilter).toBeDisabled();
  await expect(publicFilter).toHaveAttribute("title", /private/i);

  // Selecting one updates the count and offers a way back.
  await menu.getByRole("menuitemcheckbox", { name: "Vocals" }).click();
  await expect(page.getByRole("button", { name: "Filters (1)" })).toBeVisible();
  await page.getByRole("button", { name: "Filters (1)" }).click();
  await page.getByRole("menuitem", { name: "Clear filters" }).click();
  await expect(page.getByRole("button", { name: "Filters (0)" })).toBeVisible();
});
