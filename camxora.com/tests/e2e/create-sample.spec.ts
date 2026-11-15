import { expect, test } from "@playwright/test";

import { signIn } from "./studio-fixture";

/**
 * Song row → Sample this song.
 *
 * The menu item used to be disabled. It now opens Create with the source clip
 * attached as an audio reference; submitting sends sample_task_id/variant, and
 * the server resolves the owned audio URL.
 */

test("sampling a song attaches a reference to the next generation", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.route("**/api/v3/web-music/generations/gen-123", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "gen-123",
        title: "Night Drive",
        style: "synthwave, neon",
        status: "completed",
        clips: [],
      }),
    })
  );
  const captured: { body: Record<string, unknown> | null } = { body: null };
  await page.route("**/api/v3/web-music/generate", async (route) => {
    captured.body = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        task_id: "sample-task-1",
        status: "QUEUED",
        title: "New Sample Song",
        style: "synthwave, neon",
        model: "V6_MINI",
        quota: { limit: 20, used: 1, remaining: 19, is_pro: false },
      }),
    });
  });
  await page.route("**/api/v3/web-music/generations?limit=*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], total: 0, limit: 40, offset: 0 }),
    })
  );
  await page.route("**/api/v3/web-music/generations/sample-task-1", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "sample-task-1",
        title: "New Sample Song",
        style: "synthwave, neon",
        status: "pending",
        clips: [],
      }),
    })
  );

  await page.goto("/create?sample=gen-123&variant=alt");

  const chip = page.getByRole("button", { name: /Remove sample Night Drive/ });
  await expect(chip).toBeVisible({ timeout: 30_000 });
  await expect(page.locator("#create-style")).toHaveValue("synthwave, neon");
  await page.getByPlaceholder("Song title").fill("New Sample Song");
  await page.locator("#create-lyrics").fill("[Verse]\nA new line");

  await page.locator(".s-create-btn").click();
  await expect.poll(() => captured.body?.sample_task_id, { timeout: 15_000 }).toBe("gen-123");
  expect(captured.body?.sample_variant).toBe("alt");
  await expect(chip).toHaveCount(0);
});
