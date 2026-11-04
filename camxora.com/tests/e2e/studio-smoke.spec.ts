import { expect, test } from "@playwright/test";

/**
 * Studio smoke (roadmap W5.4): create a project, move a clip, undo it, open export.
 *
 * The spec builds its own fixture through the API from inside the page, so it does not
 * depend on leftover projects or on a UI login. It needs a dev server on BASE_URL with
 * the sandbox API running; the account is the local sandbox user
 * (scripts/seed_sandbox_user.py) and must never point at production.
 */

const EMAIL = process.env.STUDIO_SMOKE_EMAIL ?? "somvannda@gmail.com";
const PASSWORD = process.env.STUDIO_SMOKE_PASSWORD ?? "StudioLocal!2026";

test("studio smoke: move, undo, export", async ({ page }) => {
  test.setTimeout(120_000);

  await page.goto("/studio");

  // 1. sign in + create a project with one track and one clip, all through the API.
  const projectId = await page.evaluate(
    async ({ email, password }) => {
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
          title: "Smoke project",
          bpm: 120,
          time_signature: "4/4",
          data: {
            lanes: [
              { id: "smoke-clip", title: "Smoke clip", start: 0, duration: 4, volume: 1, pan: 0 },
            ],
            tracks: [
              {
                id: "smoke-track",
                name: "Track 1",
                color: "#38bdf8",
                index: 0,
                volume: 80,
                pan: 0,
                muted: false,
                solo: false,
                hidden: false,
                groupId: null,
                chain: [],
                clipIds: ["smoke-clip"],
              },
            ],
          },
        }),
      });
      if (!created.ok) throw new Error(`create failed: ${created.status}`);
      const project = await created.json();
      return project.id as string;
    },
    { email: EMAIL, password: PASSWORD }
  );

  // 2. open the fixture project and wait for the arrangement.
  await page.goto(`/studio/editor?project=${projectId}`);
  const clip = page.locator(".se-clip").first();
  await expect(clip).toBeVisible({ timeout: 30_000 });

  // 3. drag it exactly one bar (96px at the default zoom).
  const left = () => clip.evaluate((el) => (el as HTMLElement).style.left);
  const before = await left();
  const box = await clip.boundingBox();
  if (!box) throw new Error("clip has no box");

  await page.mouse.move(box.x + 12, box.y + 10);
  await page.mouse.down();
  await page.mouse.move(box.x + 12 + 96, box.y + 10, { steps: 8 });
  await page.mouse.up();

  await expect.poll(left, { timeout: 10_000 }).not.toBe(before);

  // 4. the save chip settles, then undo restores the original position.
  await expect(page.getByText("Saved")).toBeVisible({ timeout: 15_000 });
  await page.keyboard.press("Control+z");
  await expect.poll(left, { timeout: 10_000 }).toBe(before);

  // 5. the export menu opens with its scopes.
  await page.getByLabel("Export menu").click();
  await expect(page.getByRole("menuitem", { name: /Full mix/ })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: /Selected time range/ })).toBeVisible();
});
