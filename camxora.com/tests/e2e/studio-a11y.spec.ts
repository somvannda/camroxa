import { expect, test } from "@playwright/test";
import path from "node:path";

/**
 * Accessibility as a test (W5.5), not a one-off audit.
 *
 * Injects the axe-core bundle into the real pages and asserts zero violations on both
 * Studio routes. The audit that produced the G14 fixes was manual; this keeps it true.
 */

const AXE_PATH = path.join(process.cwd(), "node_modules", "axe-core", "axe.min.js");

const EMAIL = process.env.STUDIO_SMOKE_EMAIL ?? "somvannda@gmail.com";
const PASSWORD = process.env.STUDIO_SMOKE_PASSWORD ?? "StudioLocal!2026";

async function audit(page: import("@playwright/test").Page) {
  await page.addScriptTag({ path: AXE_PATH });
  return page.evaluate(async () => {
    const axe = (window as unknown as { axe: { run: (ctx: Document) => Promise<{ violations: Array<{ id: string; impact: string | null; nodes: unknown[] }> }> } }).axe;
    const result = await axe.run(document);
    return result.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      nodes: violation.nodes.length,
    }));
  });
}

test("studio home has no axe violations", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/studio");
  await page.evaluate(
    async ({ email, password }) => {
      await fetch("/api/v3/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
    },
    { email: EMAIL, password: PASSWORD }
  );
  await page.reload();
  await expect(page.locator("main.studio-home")).toBeVisible({ timeout: 30_000 });

  expect(await audit(page)).toEqual([]);
});

test("studio editor has no axe violations", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/studio");

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
          title: "A11y probe",
          bpm: 120,
          time_signature: "4/4",
          data: {
            lanes: [{ id: "a11y-clip", title: "Clip", start: 0, duration: 4, volume: 1, pan: 0 }],
            tracks: [
              {
                id: "a11y-track",
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
                clipIds: ["a11y-clip"],
              },
            ],
          },
        }),
      });
      const project = await created.json();
      return project.id as string;
    },
    { email: EMAIL, password: PASSWORD }
  );

  await page.goto(`/studio/editor?project=${projectId}`);
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });

  expect(await audit(page)).toEqual([]);
});
