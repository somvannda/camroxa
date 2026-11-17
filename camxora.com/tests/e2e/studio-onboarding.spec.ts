import { expect, test, type Page } from "@playwright/test";

import { signIn } from "./studio-fixture";

/**
 * S03/S06: an empty project opens the captured "How do you want to start?" overlay.
 * We ship five real starting points in the captured order (Edit Your Song · Drum & Bass
 * Demo · Upload Audio · Create a song · Empty Project) plus the Browse pill. The demo is a
 * project we seed with our own loop; the tutorial is the dropped YouTube row
 * (CLONE_DEFINITION §5).
 */

async function emptyProject(page: Page, title: string): Promise<string> {
  return page.evaluate(async (name) => {
    const response = await fetch("/api/v3/web-music/studio/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: name,
        bpm: 120,
        time_signature: "4/4",
        data: { lanes: [], tracks: [] },
      }),
    });
    const body = (await response.json()) as { id: string };
    return body.id;
  }, title);
}

test("an empty project offers real starting points, a close and a browse link", async ({ page }) => {
  test.setTimeout(120_000);

  await signIn(page);
  const projectId = await emptyProject(page, "Onboarding");

  await page.goto(`/studio/editor?project=${projectId}`);
  const dialog = page.getByRole("dialog", { name: "How do you want to start?" });
  await expect(dialog).toBeVisible({ timeout: 30_000 });

  await expect(dialog.getByRole("button", { name: /Edit Your Song/ })).toBeVisible();
  await expect(dialog.getByRole("button", { name: /Drum & Bass Demo/ })).toBeVisible();
  await expect(dialog.getByRole("button", { name: /Upload Audio/ })).toBeVisible();
  await expect(dialog.getByRole("link", { name: /Create a song/ })).toBeVisible();
  await expect(dialog.getByRole("button", { name: /Empty Project/ })).toBeVisible();
  await expect(dialog.getByRole("link", { name: /Browse Studio projects/ })).toBeVisible();

  // Five tiles keep the captured fan; the tutorial stays the recorded absence.
  await expect(dialog.locator(".se-onboard-tile")).toHaveCount(5);

  // Edit Your Song opens the library drawer rather than doing nothing.
  await dialog.getByRole("button", { name: /Edit Your Song/ }).click();
  await expect(page.getByRole("complementary", { name: "Library" })).toBeVisible();
});

test("the Drum & Bass Demo tile opens a project seeded with our loop", async ({ page }) => {
  test.setTimeout(120_000);

  await signIn(page);
  const projectId = await emptyProject(page, "Onboarding demo");

  await page.goto(`/studio/editor?project=${projectId}`);
  const dialog = page.getByRole("dialog", { name: "How do you want to start?" });
  await expect(dialog).toBeVisible({ timeout: 30_000 });

  await dialog.getByRole("button", { name: /Drum & Bass Demo/ }).click();

  // The tile materialises a project, rewrites the URL and stays in the editor on it.
  await expect(page.locator(".se-chip")).toHaveText("Drum & Bass Demo", { timeout: 30_000 });
  const opened = await page.evaluate(() => new URL(window.location.href).searchParams.get("project"));
  expect(opened).toBeTruthy();
  expect(opened).not.toBe(projectId);

  // One track, one clip, and the clip carries our seed loop's waveform — playable now.
  const clip = page.locator(".se-clip");
  await expect(clip).toHaveCount(1);
  await expect(clip.locator(".se-clip-head")).toHaveText("Drum & Bass Demo");
  // The clip body is aria-hidden, so assert the canvas state rather than its role.
  await expect(clip.locator(".se-clip-body canvas")).toHaveAttribute("data-waveform", /ready|fallback/);
  await expect(page.locator(".se-track-name").first()).toContainText("Drum & Bass");
  await expect(page.locator(".se-lane")).toHaveCount(1);

  // The overlay closes once the seeded project has clips.
  await expect(page.getByRole("dialog", { name: "How do you want to start?" })).toHaveCount(0);
});

test("the overlay closes from its ✕ and does not come back for that project", async ({ page }) => {
  test.setTimeout(120_000);

  await signIn(page);
  const projectId = await emptyProject(page, "Onboarding close");

  await page.goto(`/studio/editor?project=${projectId}`);
  const dialog = page.getByRole("dialog", { name: "How do you want to start?" });
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  await dialog.getByRole("button", { name: "Close" }).click();
  await expect(dialog).toHaveCount(0);

  await page.reload();
  await expect(page.locator(".se-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("dialog", { name: "How do you want to start?" })).toHaveCount(0);
});
