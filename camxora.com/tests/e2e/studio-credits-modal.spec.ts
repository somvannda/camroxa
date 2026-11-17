import { expect, test, type Page } from "@playwright/test";

import { signIn } from "./studio-fixture";

/**
 * S61 — the captured out-of-credits modal.
 *
 * The pricing ladder and the generate refusal are mocked so the spec pins the
 * modal anatomy, not the sandbox balance. `/topups/packs/public` mirrors the
 * three packs `127_web_music_plans_v2.py` seeds ($5 / $10 / $30) — the capture's
 * $6 is not a CAMXORA price, and the modal must render whatever the API returns.
 */

const PACKS = {
  packs: [
    {
      id: "pack-small",
      slug: "small",
      name: "Small Pack",
      description: "",
      total_credits: 700,
      price_cents: 500,
      display_order: 1,
      songs_equivalent: 140,
    },
    {
      id: "pack-medium",
      slug: "medium",
      name: "Medium Pack",
      description: "",
      total_credits: 1840,
      price_cents: 1000,
      display_order: 2,
      songs_equivalent: 368,
    },
    {
      id: "pack-large",
      slug: "large",
      name: "Large Pack",
      description: "",
      total_credits: 7920,
      price_cents: 3000,
      display_order: 3,
      songs_equivalent: 1584,
    },
  ],
};

function quota(creditsRemaining: number) {
  return {
    limit: 100,
    used: 0,
    remaining: 100,
    is_pro: true,
    requires_upgrade: false,
    credits_remaining: creditsRemaining,
    credits_per_song: 10,
    has_subscription: true,
    can_download: true,
    daily_free_remaining: 0,
    daily_free_limit: 0,
    premium_unlocked: true,
    free_model: "v6",
    queue_limit: 20,
    queue_used: 0,
    previews: null,
  };
}

/** Sign in, mock pricing/quota/generate, then submit one song. */
async function openCreditsModal(page: Page, options: { creditsRemaining?: number } = {}) {
  const { creditsRemaining = 1000 } = options;
  await signIn(page);

  let generateCalls = 0;
  await page.route("**/api/v3/topups/packs/public", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(PACKS),
    })
  );
  await page.route("**/api/v3/web-music/quota", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(quota(creditsRemaining)),
    })
  );
  await page.route("**/api/v3/web-music/generate", (route) => {
    generateCalls += 1;
    return route.fulfill({
      status: 429,
      contentType: "application/json",
      body: JSON.stringify({
        error: { message: "Insufficient credits.", code: "INSUFFICIENT_CREDITS" },
      }),
    });
  });

  await page.goto("/create");
  await expect(page.getByRole("heading", { level: 1, name: "Create music" })).toBeVisible({
    timeout: 30_000,
  });

  await page.getByLabel("Song description").fill("one more calm piano loop");
  await page.locator(".s-create-btn").click();

  const dialog = page.getByRole("dialog", { name: "You're out of credits" });
  await expect(dialog).toBeVisible({ timeout: 20_000 });
  return { dialog, generateCalls: () => generateCalls };
}

test("a refused generate opens the captured out-of-credits modal", async ({ page }) => {
  test.setTimeout(120_000);
  const { dialog } = await openCreditsModal(page);

  await expect(dialog).toHaveAttribute("aria-modal", "true");
  await expect(dialog.getByRole("button", { name: "Close" })).toBeVisible();
  await expect(dialog.getByText("Monthly credits used")).toBeVisible();
  await expect(dialog.getByText("100%")).toBeVisible();
  await expect(dialog.getByText(/Get back to creating/)).toBeVisible();
  await expect(dialog.getByText("Auto-reload amount")).toBeVisible();
  await expect(dialog.getByTestId("credits-modal-amount")).toHaveText("$5");
  await expect(dialog.getByText("700 credits · about 140 songs")).toBeVisible();
  await expect(
    dialog.getByRole("switch", { name: "Turn on auto-reload" })
  ).toBeDisabled();
  await expect(dialog.getByRole("button", { name: "Buy credits" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Not now" })).toBeVisible();
});

test("the stepper walks the pricing ladder and stops at both ends", async ({ page }) => {
  test.setTimeout(120_000);
  const { dialog } = await openCreditsModal(page);

  const amount = dialog.getByTestId("credits-modal-amount");
  const down = dialog.getByRole("button", { name: "Decrease amount" });
  const up = dialog.getByRole("button", { name: "Increase amount" });

  await expect(amount).toHaveText("$5");
  await expect(down).toBeDisabled();

  await up.click();
  await expect(amount).toHaveText("$10");
  await up.click();
  await expect(amount).toHaveText("$30");
  await expect(up).toBeDisabled();

  await down.click();
  await expect(amount).toHaveText("$10");
});

test("Not now dismisses the modal and leaves the form usable", async ({ page }) => {
  test.setTimeout(120_000);
  const { dialog } = await openCreditsModal(page);

  await dialog.getByRole("button", { name: "Not now" }).click();
  await expect(dialog).toBeHidden();

  const prompt = page.getByLabel("Song description");
  await expect(prompt).toBeEditable();
  await prompt.fill("a calmer piano loop with a longer tail");
  await expect(page.locator(".s-create-btn")).toBeEnabled();
});

test("Escape closes the modal", async ({ page }) => {
  test.setTimeout(120_000);
  const { dialog } = await openCreditsModal(page);

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(page.locator(".s-create-btn")).toBeEnabled();
});

test("a short balance opens the modal before any generate is sent", async ({ page }) => {
  test.setTimeout(120_000);
  const { dialog, generateCalls } = await openCreditsModal(page, { creditsRemaining: 0 });

  await expect(dialog).toBeVisible();
  await expect(dialog.getByTestId("credits-modal-amount")).toHaveText("$5");
  expect(generateCalls()).toBe(0);
});
