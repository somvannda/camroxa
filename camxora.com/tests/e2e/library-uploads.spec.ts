import { expect, test } from "@playwright/test";

import { createStudioProject, signIn } from "./studio-fixture";

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
  // An upload without artwork must not reach the player as an empty src.
  expect(await page.evaluate(() => document.querySelectorAll("[src='']").length)).toBe(0);
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

test("an upload can be placed into a Studio project", async ({ page }) => {
  test.setTimeout(120_000);
  await page.route("**/api/v3/web-music/studio/uploads?**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [upload] }),
    })
  );

  const tag = Math.random().toString(36).slice(2, 8);
  const projectTitle = `Upload target ${tag}`;
  const projectId = await createStudioProject(page, { title: projectTitle });

  await page.goto("/library");
  await expect(page.getByRole("tablist", { name: "Library sections" })).toBeVisible({
    timeout: 30_000,
  });
  await page.getByRole("tab", { name: "Uploads" }).click();
  await page.getByRole("button", { name: "Add to project" }).click();

  const dialog = page.getByRole("dialog", { name: "Add upload to a project" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: projectTitle }).click();

  await expect(page.getByRole("status")).toContainText("Added demo-loop.wav");

  // The document now carries the upload after the fixture clip.
  await expect
    .poll(
      async () =>
        page.evaluate(async (id) => {
          const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
          const project = (await response.json()) as {
            data?: { lanes?: Array<{ audioUrl?: string | null; start?: number; title?: string }> };
          };
          return project.data?.lanes?.find(
            (lane) => lane.audioUrl === "/seed/demo-loop.wav"
          ) ?? null;
        }, projectId),
      { timeout: 15_000, intervals: [250] }
    )
    .toMatchObject({ start: 4, title: "demo-loop" });
});
