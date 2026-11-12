import { expect, test } from "@playwright/test";

import { signIn } from "./studio-fixture";

/**
 * The previous editor stays reachable at `/studio/editor/classic`. This smoke test
 * exists because that page alone broke `next build` (no Suspense around its
 * `useSearchParams`), so loading it in the browser guards the same boundary.
 */

test("the classic editor route still loads", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.goto("/studio/editor/classic");
  await expect(page.locator(".studio-editor-head")).toBeVisible();
  await expect(page.getByRole("button", { name: /play/i }).first()).toBeVisible();
});
