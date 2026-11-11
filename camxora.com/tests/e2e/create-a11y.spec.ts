import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { signIn } from "./studio-fixture";

/**
 * Accessibility for the Create surface, which carries the most controls on the site:
 * prompt fields, mode tabs, the advanced panel and the model pickers.
 */

const AXE_PATH = path.join(process.cwd(), "node_modules", "axe-core", "axe.min.js");

async function audit(page: Page) {
  await page.evaluate(async () => {
    const finite = document
      .getAnimations()
      .filter((animation) => {
        const timing = animation.effect?.getComputedTiming?.();
        return timing ? timing.iterations !== Infinity : true;
      });
    await Promise.race([
      Promise.all(finite.map((animation) => animation.finished.catch(() => undefined))),
      new Promise((resolve) => setTimeout(resolve, 800)),
    ]);
  });
  await page.addScriptTag({ path: AXE_PATH });
  return page.evaluate(async () => {
    const axe = (
      window as unknown as {
        axe: {
          run: (ctx: Document) => Promise<{
            violations: Array<{ id: string; impact: string | null; nodes: unknown[] }>;
          }>;
        };
      }
    ).axe;
    const result = await axe.run(document);
    return result.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      nodes: (violation.nodes as Array<{ target: unknown; failureSummary?: string }>).map(
        (node) => ({ target: node.target, summary: node.failureSummary })
      ),
    }));
  });
}

test("the create page has no axe violations", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.goto("/create");
  await expect(page.getByRole("main")).toBeVisible({ timeout: 30_000 });
  // Wait for the workspace to finish booting rather than the skeleton.
  await expect(page.getByRole("heading", { level: 1, name: "Create music" })).toBeVisible({
    timeout: 30_000,
  });

  expect(await audit(page)).toEqual([]);
});

test("the marketing pages have no axe violations", async ({ page }) => {
  test.setTimeout(180_000);
  for (const route of ["/", "/pricing", "/discover"]) {
    await page.goto(route);
    await expect(page.getByRole("main")).toBeVisible({ timeout: 30_000 });
    expect(await audit(page), route).toEqual([]);
  }
});
