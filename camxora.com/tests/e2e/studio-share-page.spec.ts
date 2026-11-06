import { expect, test } from "@playwright/test";

import { createStudioProject } from "./studio-fixture";

const ORIGIN = process.env.BASE_URL ?? "http://localhost:3103";

/** Create a view link through the API and return its token. */
async function createShare(page: import("@playwright/test").Page, projectId: string) {
  return page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}/shares`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expires_days: 7, permission: "view" }),
    });
    const body = (await response.json()) as { token?: string };
    return body.token ?? "";
  }, projectId);
}

test("a share link opens read-only without an account", async ({ page, browser }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const title = `Shared ${tag}`;
  const projectId = await createStudioProject(page, { title });
  const token = await createShare(page, projectId);
  expect(token.length).toBeGreaterThan(10);

  // A visitor with no cookies at all.
  const anon = await browser.newContext({ baseURL: ORIGIN });
  const anonPage = await anon.newPage();
  await anonPage.goto(`/studio/shared/${token}`);

  await expect(anonPage.getByRole("heading", { name: title })).toBeVisible({ timeout: 30_000 });
  await expect(anonPage.getByText("Read-only Studio share")).toBeVisible();
  await expect(anonPage.getByLabel("Read-only project timeline")).toBeVisible();
  await expect(anonPage.getByRole("link", { name: "Sign in to fork" })).toBeVisible();
  // Visitors cannot edit: there is no editor link on the page.
  await expect(anonPage.locator('a[href*="/studio/editor"]')).toHaveCount(0);

  await anon.close();
});

test("fork opens the new copy, not just the most recent project", async ({ page }) => {
  test.setTimeout(120_000);

  const tag = Math.random().toString(36).slice(2, 8);
  const title = `Fork ${tag}`;
  const projectId = await createStudioProject(page, { title });
  const token = await createShare(page, projectId);

  await page.goto(`/studio/shared/${token}`);
  await expect(page.getByRole("heading", { name: title })).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Fork to Studio" }).click();
  await page.waitForURL(/\/studio\/editor\?project=/, { timeout: 30_000 });

  const copyId = new URL(page.url()).searchParams.get("project");
  expect(copyId).toBeTruthy();
  expect(copyId).not.toBe(projectId);

  // The editor is showing the forked project.
  await expect(page.locator(".se-project .se-chip")).toContainText(title, { timeout: 30_000 });
});
