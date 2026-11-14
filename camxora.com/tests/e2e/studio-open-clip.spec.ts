import { expect, test } from "@playwright/test";

import { signIn } from "./studio-fixture";

/**
 * "Open in Studio" / Replace Section / Crop from a song row.
 *
 * The menu used to open the editor with no project (or stay disabled). It now
 * deep-links `?clip=<generation>`, and the editor materialises that version as a
 * one-track project. The generation and project calls are mocked so this stays a
 * pure UI test with no provider traffic.
 */

const SONG = {
  id: "gen-123",
  title: "Night Drive",
  style: "synthwave",
  status: "completed",
  clips: [
    {
      variant: "alt",
      label: "Version 2",
      title: "Night Drive (alt)",
      audio_url: "https://cdn.example/night-drive-alt.mp3",
      duration_seconds: 131,
      ready: true,
    },
  ],
};

test("a song deep link opens as a one-track Studio project", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);

  const captured: { body: Record<string, unknown> | null } = { body: null };
  await page.route("**/api/v3/web-music/generations/gen-123", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SONG) })
  );
  await page.route("**/api/v3/web-music/studio/projects/for-song/gen-123", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: null }),
    })
  );
  await page.route("**/api/v3/web-music/studio/projects", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fallback();
      return;
    }
    captured.body = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ id: "project-from-song", ...captured.body }),
    });
  });
  await page.route("**/api/v3/web-music/studio/projects/project-from-song", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "project-from-song", ...(captured.body ?? {}) }),
    })
  );

  await page.goto("/studio/editor?clip=gen-123&variant=alt&intent=crop");

  await expect(page.getByText("Drag the clip handles to crop this song.")).toBeVisible({
    timeout: 30_000,
  });
  expect(captured.body).not.toBeNull();
  const data = (captured.body?.data ?? {}) as Record<string, unknown>;
  const lanes = (data.lanes ?? []) as Array<Record<string, unknown>>;
  expect(lanes[0]).toMatchObject({
    audioUrl: "https://cdn.example/night-drive-alt.mp3",
    songId: "gen-123",
    songVariant: "alt",
  });
  await expect(page).toHaveURL(/project=project-from-song/);
});

test("opening the same song again loads the existing project", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);

  let created = false;
  await page.route("**/api/v3/web-music/studio/projects/for-song/gen-123", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "existing-project" }),
    })
  );
  await page.route("**/api/v3/web-music/studio/projects/existing-project", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "existing-project",
        title: "Night Drive",
        major_version: 2,
        bpm: 120,
        time_signature: "4/4",
        data: { tracks: [], lanes: [] },
      }),
    })
  );
  await page.route("**/api/v3/web-music/studio/projects", async (route) => {
    if (route.request().method() === "POST") {
      created = true;
      await route.fulfill({ status: 201, contentType: "application/json", body: "{}" });
      return;
    }
    await route.fallback();
  });

  await page.goto("/studio/editor?clip=gen-123&variant=ok");

  await expect(page).toHaveURL(/project=existing-project/, { timeout: 30_000 });
  expect(created).toBe(false);
});
