import { expect, test } from "@playwright/test";

import { signIn } from "./studio-fixture";

/**
 * Library ▸ Uploads.
 *
 * Imported audio lives in Studio's storage; this tab lists it so it is not Studio-only.
 * The sandbox API has no bucket (B-006/B-007), so the listing is mocked here; the empty
 * state is covered separately.
 */

const upload = {
  id: "upload-1",
  filename: "demo-loop.wav",
  content_type: "audio/wav",
  size_bytes: 176444,
  duration_seconds: 4,
  url: "/seed/demo-loop.wav",
  created_at: new Date().toISOString(),
};

test("the uploads tab lists imported audio and plays it", async ({ page }) => {
  test.setTimeout(120_000);
  await page.route("**/api/v3/web-music/studio/uploads?**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [upload] }),
    })
  );

  await signIn(page);
  await page.goto("/library");
  await expect(page.getByRole("tablist", { name: "Library sections" })).toBeVisible({
    timeout: 30_000,
  });

  await page.getByRole("tab", { name: "Uploads" }).click();
  const card = page.getByRole("button", { name: /demo-loop\.wav/ });
  await expect(card).toBeVisible();
  await expect(card).toContainText("Play");

  // Playing hands the upload to the shared player.
  await card.click();
  await expect(page.getByText("demo-loop", { exact: true }).first()).toBeVisible();
});

test("the uploads tab explains an empty library", async ({ page }) => {
  test.setTimeout(120_000);
  await page.route("**/api/v3/web-music/studio/uploads?**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [] }),
    })
  );

  await signIn(page);
  await page.goto("/library");
  await expect(page.getByRole("tablist", { name: "Library sections" })).toBeVisible({
    timeout: 30_000,
  });

  await page.getByRole("tab", { name: "Uploads" }).click();
  await expect(page.getByText("No uploads yet")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open Studio" })).toBeVisible();
});
