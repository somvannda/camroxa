import { expect, test } from "@playwright/test";

import { signIn } from "./studio-fixture";

/**
 * S03/S06: an empty project opens the captured "How do you want to start?" overlay.
 * We ship four real starting points plus the Browse pill; the demo tile needs a bundled
 * arrangement and the tutorial is the dropped YouTube row (CLONE_DEFINITION §5).
 */

test("an empty project offers real starting points, a close and a browse link", async ({ page }) => {
  test.setTimeout(120_000);

  await signIn(page);
  const projectId = await page.evaluate(async () => {
    const response = await fetch("/api/v3/web-music/studio/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: "Onboarding",
        bpm: 120,
        time_signature: "4/4",
        data: { lanes: [], tracks: [] },
      }),
    });
    const body = (await response.json()) as { id: string };
    return body.id;
  });

  await page.goto(`/studio/editor?project=${projectId}`);
  const dialog = page.getByRole("dialog", { name: "How do you want to start?" });
  await expect(dialog).toBeVisible({ timeout: 30_000 });

  await expect(dialog.getByRole("button", { name: /Edit Your Song/ })).toBeVisible();
  await expect(dialog.getByRole("button", { name: /Upload Audio/ })).toBeVisible();
  await expect(dialog.getByRole("button", { name: /Empty Project/ })).toBeVisible();
  await expect(dialog.getByRole("link", { name: /Browse Studio projects/ })).toBeVisible();

  // Edit Your Song opens the library drawer rather than doing nothing.
  await dialog.getByRole("button", { name: /Edit Your Song/ }).click();
  await expect(page.getByRole("complementary", { name: "Library" })).toBeVisible();
});

test("the overlay closes from its ✕ and does not come back for that project", async ({ page }) => {
  test.setTimeout(120_000);

  await signIn(page);
  const projectId = await page.evaluate(async () => {
    const response = await fetch("/api/v3/web-music/studio/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: "Onboarding close",
        bpm: 120,
        time_signature: "4/4",
        data: { lanes: [], tracks: [] },
      }),
    });
    const body = (await response.json()) as { id: string };
    return body.id;
  });

  await page.goto(`/studio/editor?project=${projectId}`);
  const dialog = page.getByRole("dialog", { name: "How do you want to start?" });
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  await dialog.getByRole("button", { name: "Close" }).click();
  await expect(dialog).toHaveCount(0);

  await page.reload();
  await expect(page.locator(".se-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("dialog", { name: "How do you want to start?" })).toHaveCount(0);
});
