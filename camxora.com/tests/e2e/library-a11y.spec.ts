import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { createStudioProject, signIn } from "./studio-fixture";

/**
 * Accessibility for the Library surfaces added with the filter/upload work: the tab
 * strip, the filter menu, the uploads cards and the add-to-project dialog. Same axe gate
 * as the Studio routes, so a new control cannot ship without a landmark, name or contrast
 * check.
 */

const AXE_PATH = path.join(process.cwd(), "node_modules", "axe-core", "axe.min.js");

async function audit(page: Page, options: { disable?: string[] } = {}) {
  // Let entrance animations finish: axe reads the painted colours, and the modal fades
  // in from transparent (a false contrast failure otherwise).
  await page.evaluate(async () => {
    const finite = document.getAnimations().filter((animation) => {
      const timing = animation.effect?.getComputedTiming?.();
      return timing ? timing.iterations !== Infinity : true;
    });
    await Promise.race([
      Promise.all(finite.map((animation) => animation.finished.catch(() => undefined))),
      new Promise((resolve) => setTimeout(resolve, 800)),
    ]);
  });
  await page.addScriptTag({ path: AXE_PATH });
  return page.evaluate(async (disabled) => {
    const axe = (
      window as unknown as {
        axe: {
          run: (
            ctx: Document,
            options?: { rules?: Record<string, { enabled: boolean }> }
          ) => Promise<{
            violations: Array<{ id: string; impact: string | null; nodes: unknown[] }>;
          }>;
        };
      }
    ).axe;
    const rules = Object.fromEntries(disabled.map((id) => [id, { enabled: false }]));
    const result = await axe.run(document, { rules });
    return result.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      nodes: (violation.nodes as Array<{ target: unknown; failureSummary?: string }>).map(
        (node) => ({ target: node.target, summary: node.failureSummary })
      ),
    }));
  }, options.disable ?? []);
}

/**
 * Audit one element instead of the whole document. Radix marks the rest of the page
 * `aria-hidden` while a menu is open, so a document-wide scan sees "no main landmark"
 * and "no h1" that are only masked, not missing; scoping to the menu checks the menu.
 */
async function auditWithin(page: Page, locator: ReturnType<Page["locator"]>) {
  const handle = await locator.elementHandle();
  if (!handle) throw new Error("audit target is missing");
  await page.addScriptTag({ path: AXE_PATH });
  return page.evaluate(async (element) => {
    const axe = (
      window as unknown as {
        axe: {
          run: (ctx: Element) => Promise<{
            violations: Array<{ id: string; impact: string | null; nodes: unknown[] }>;
          }>;
        };
      }
    ).axe;
    const result = await axe.run(element);
    return result.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      nodes: (violation.nodes as Array<{ target: unknown; failureSummary?: string }>).map(
        (node) => ({ target: node.target, summary: node.failureSummary })
      ),
    }));
  }, handle);
}

const upload = {
  id: "a11y-upload",
  filename: "demo-loop.wav",
  content_type: "audio/wav",
  size_bytes: 176444,
  duration_seconds: 4,
  url: "/seed/demo-loop.wav",
  created_at: new Date().toISOString(),
};

test("library, its filter menu and the uploads tab have no axe violations", async ({ page }) => {
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
  expect(await audit(page)).toEqual([]);

  await page.getByRole("button", { name: /^Filters/ }).click();
  const menu = page.getByRole("menu");
  await expect(menu).toBeVisible();
  // Radix marks the page aria-hidden while the menu is open, so the menu is audited as a
  // surface of its own (page-level landmarks are audited above, before opening it).
  expect(await auditWithin(page, menu)).toEqual([]);

  await page.keyboard.press("Escape");
  await page.getByRole("tab", { name: "Uploads" }).click();
  await expect(page.getByRole("button", { name: /demo-loop\.wav/ })).toBeVisible();
  expect(await audit(page)).toEqual([]);
});

test("the add-to-project dialog has no axe violations", async ({ page }) => {
  test.setTimeout(120_000);
  await page.route("**/api/v3/web-music/studio/uploads?**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [upload] }),
    })
  );

  const tag = Math.random().toString(36).slice(2, 8);
  await createStudioProject(page, { title: `A11y upload target ${tag}` });

  await page.goto("/library");
  await expect(page.getByRole("tablist", { name: "Library sections" })).toBeVisible({
    timeout: 30_000,
  });
  await page.getByRole("tab", { name: "Uploads" }).click();
  await page.getByRole("button", { name: "Add to project" }).click();

  const dialog = page.getByRole("dialog", { name: "Add upload to a project" });
  await expect(dialog).toBeVisible();
  expect(await audit(page)).toEqual([]);
});
