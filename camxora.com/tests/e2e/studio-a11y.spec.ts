import { expect, test } from "@playwright/test";
import path from "node:path";

import { createStudioProject, signIn } from "./studio-fixture";

/**
 * Accessibility as a test (W5.5), not a one-off audit.
 *
 * Injects the axe-core bundle into the real pages and asserts zero violations on both
 * Studio routes. The audit that produced the G14 fixes was manual; this keeps it true.
 */

const AXE_PATH = path.join(process.cwd(), "node_modules", "axe-core", "axe.min.js");

async function audit(page: import("@playwright/test").Page) {
  await page.addScriptTag({ path: AXE_PATH });
  return page.evaluate(async () => {
    const axe = (window as unknown as { axe: { run: (ctx: Document) => Promise<{ violations: Array<{ id: string; impact: string | null; nodes: unknown[] }> }> } }).axe;
    const result = await axe.run(document);
    return result.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      // Targets make a failure actionable without re-running the audit by hand.
      nodes: (violation.nodes as Array<{ target: unknown; failureSummary?: string }>).map((node) => ({
        target: node.target,
        summary: node.failureSummary,
      })),
    }));
  });
}

test("studio home has no axe violations", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.reload();
  await expect(page.locator("main.studio-home")).toBeVisible({ timeout: 30_000 });

  expect(await audit(page)).toEqual([]);
});

test("studio editor has no axe violations", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: "A11y probe" });

  expect(await audit(page)).toEqual([]);

  // The Learn popover is a fifth surface; audit it while open.
  await page.getByRole("button", { name: "Learn", exact: true }).click();
  await expect(page.getByRole("menu", { name: "Learn" })).toBeVisible();
  expect(await audit(page)).toEqual([]);
});

test("library drawer has no axe violations", async ({ page }) => {
  test.setTimeout(120_000);
  await createStudioProject(page, { title: "A11y library probe" });
  await page.getByRole("button", { name: "Library", exact: true }).click();
  await expect(page.getByRole("complementary", { name: "Library" })).toBeVisible();

  expect(await audit(page)).toEqual([]);
});
