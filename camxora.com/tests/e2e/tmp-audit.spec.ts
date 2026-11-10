import { expect, test } from "@playwright/test";

import { EMAIL, PASSWORD, createStudioProject } from "./studio-fixture";

const V = { width: 1689, height: 1277 };

async function createEmptyProject(page: import("@playwright/test").Page, title: string) {
  await page.goto("/studio");
  const id = await page.evaluate(
    async ({ email, password, name }) => {
      const login = await fetch("/api/v3/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      if (login.status !== 200) throw new Error(`login failed: ${login.status}`);
      const created = await fetch("/api/v3/web-music/studio/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: name,
          bpm: 120,
          time_signature: "4/4",
          data: {
            lanes: [],
            tracks: [
              {
                id: "audit-track",
                name: "Audio Track",
                color: "#38bdf8",
                index: 0,
                volume: 80,
                pan: 0,
                muted: false,
                solo: false,
                hidden: false,
                groupId: null,
                chain: [],
                clipIds: [],
              },
            ],
          },
        }),
      });
      if (!created.ok) throw new Error(`create failed: ${created.status}`);
      const project = (await created.json()) as { id: string };
      return project.id;
    },
    { email: EMAIL, password: PASSWORD, name: title }
  );
  await page.goto(`/studio/editor?project=${id}`);
  await expect(page.locator(".se-head")).toBeVisible({ timeout: 30_000 });
  return id;
}

test("audit shots", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize(V);

  await createEmptyProject(page, "Audit empty");
  await page.waitForTimeout(800);
  await page.screenshot({ path: "test-results/audit-empty.png" });

  await page.getByRole("button", { name: "Library", exact: true }).click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: "test-results/audit-library-root.png" });

  const library = page.getByRole("complementary", { name: "Library" });
  await library.getByRole("button", { name: "All Songs" }).click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: "test-results/audit-library-songs.png" });
  await library.getByLabel("Back to library").click();
  await page.getByRole("button", { name: "Library", exact: true }).click();

  await createStudioProject(page, { title: "Audit plugins" });
  await page.getByRole("button", { name: "Track 1", exact: true }).click();
  await page.locator(".sp-add-inline").click();
  await page.getByRole("dialog", { name: "Add a track plugin" }).getByRole("button", { name: /^Compressor/ }).first().click();
  await page.locator(".sp-add").click();
  await page.getByRole("dialog", { name: "Add a track plugin" }).getByRole("button", { name: /^EQ/ }).first().click();
  await page.screenshot({ path: "test-results/audit-plugins.png" });
});
