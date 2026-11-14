import { expect, test } from "@playwright/test";

import { signIn } from "./studio-fixture";

/**
 * Song row → Use as Inspiration.
 *
 * The menu item used to be disabled. It now opens Create in advanced mode with
 * the source song's style filled in and empty lyrics.
 */

test("inspiration seeds the style in the advanced form", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.route("**/api/v3/web-music/generations/gen-123", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "gen-123",
        title: "Night Drive",
        style: "synthwave, neon, 118 BPM",
        status: "completed",
        clips: [],
      }),
    })
  );

  await page.goto("/create?inspire=gen-123");

  await expect(page.getByText(/Inspired by Night Drive/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("tab", { name: "Advanced" })).toHaveAttribute(
    "aria-selected",
    "true"
  );
  await expect(page.locator("#create-style")).toHaveValue("synthwave, neon, 118 BPM");
  await expect(page.locator("#create-lyrics")).toHaveValue("");
});
