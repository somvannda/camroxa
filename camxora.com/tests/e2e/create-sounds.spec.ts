import { expect, test } from "@playwright/test";

import { signIn } from "./studio-fixture";

/**
 * Create → Sounds.
 *
 * The tab used to be a "coming soon" panel. It now queues a real sound effect
 * through the same generation pipeline as songs; the provider call is mocked so
 * the test spends nothing.
 */

test("the Sounds tab creates a sound through the generation API", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.goto("/create");
  await expect(page.getByRole("tab", { name: "Sounds" })).toBeVisible({ timeout: 30_000 });

  const captured: { body: Record<string, unknown> | null } = { body: null };
  await page.route("**/api/v3/web-music/sounds", async (route) => {
    captured.body = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        task_id: "sound-1",
        status: "QUEUED",
        title: "Warm tape hiss",
        style: "a warm tape hiss with a soft tail",
        model: "V6_MINI",
        model_label: "V6 Mini",
        quota: { limit: 20, used: 1, remaining: 19, is_pro: false, requires_upgrade: false },
      }),
    });
  });
  await page.route("**/api/v3/web-music/generations/sound-1", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "sound-1",
        title: "Warm tape hiss",
        style: "a warm tape hiss with a soft tail",
        status: "pending",
        clips: [],
      }),
    })
  );

  await page.getByRole("tab", { name: "Sounds" }).click();
  await expect(page.getByText(/Sounds is coming soon/)).toHaveCount(0);
  const input = page.getByLabel("Sound description");
  await expect(input).toBeVisible();
  await input.fill("a warm tape hiss with a soft tail");
  await page.getByRole("button", { name: /Create sound/ }).click();

  await expect
    .poll(() => captured.body?.prompt, { timeout: 15_000 })
    .toBe("a warm tape hiss with a soft tail");
  await expect(input).toHaveValue("");
});
