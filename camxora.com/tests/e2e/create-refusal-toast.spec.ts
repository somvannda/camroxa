import { expect, test } from "@playwright/test";

import { signIn } from "./studio-fixture";

/**
 * S60: a policy refusal on Create is the captured orange toast, not a line in the form
 * footer. The copy is the captured sentence.
 */
test("a copyrighted-lyrics refusal arrives as the captured orange toast", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);

  await page.route("**/api/v3/web-music/generate", (route) =>
    route.fulfill({
      status: 400,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "MODERATION_BLOCKED",
          message: "Your lyrics contain copyrighted material. Please change it and try again.",
        },
      }),
    })
  );

  await page.goto("/create");
  await expect(page.getByRole("heading", { level: 1, name: "Create music" })).toBeVisible({
    timeout: 30_000,
  });
  await page.getByLabel("Song description").fill("a calm piano loop with borrowed lyrics");
  await page.locator(".s-create-btn").click();

  const toast = page.locator(".s-refusal-toast");
  await expect(toast).toBeVisible({ timeout: 20_000 });
  await expect(toast).toContainText("Couldn't generate that.");
  await expect(toast).toContainText("copyrighted material");
  await toast.getByRole("button", { name: "Dismiss" }).click();
  await expect(toast).toHaveCount(0);
});
