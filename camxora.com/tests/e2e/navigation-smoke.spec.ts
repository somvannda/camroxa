import { expect, test, type Page } from "@playwright/test";

import { signIn } from "./studio-fixture";

/**
 * Navigation sweep: every page the product ships must answer with a real page and no
 * JavaScript errors, signed out and signed in. This is the cheap net that catches a
 * broken import, a crashed client component or a route that lost its chrome, without
 * asserting any particular UI.
 */

const PUBLIC_ROUTES = [
  "/",
  "/about",
  "/features",
  "/pricing",
  "/discover",
  "/charts",
  "/community",
  "/blog",
  "/changelog",
  "/contact",
  "/legal",
  "/support",
  "/services",
  "/developers",
  "/google-api",
  "/download",
  "/artist-program",
  "/playlists/khmer-hits",
  "/search?q=love",
];

/** Auth screens are the documented chrome exception: no SiteChrome, so no main. */
const AUTH_ROUTES = ["/login", "/signup", "/forgot-password", "/reset-password"];

const MEMBER_ROUTES = [
  "/library",
  "/library/trash",
  "/account",
  "/create",
  "/notifications",
  "/studio",
  "/artist-dashboard",
  "/redeem",
  "/invite",
];

/** Resource-load noise from expired signed media URLs is not a page defect. */
function isNoise(text: string): boolean {
  return (
    text.includes("Failed to load resource") ||
    text.includes("net::ERR") ||
    text.includes("the server responded with a status of 403") ||
    text.includes("the server responded with a status of 404")
  );
}

async function visit(page: Page, route: string, landmark: "main" | "auth" = "main") {
  const errors: string[] = [];
  const onConsole = (message: { type: () => string; text: () => string }) => {
    if (message.type() === "error" && !isNoise(message.text())) errors.push(message.text());
  };
  const onPageError = (error: Error) => errors.push(error.message);

  page.on("console", onConsole);
  page.on("pageerror", onPageError);
  try {
    const response = await page.goto(route, { waitUntil: "domcontentloaded" });
    expect(response?.status(), `${route} status`).toBeLessThan(400);
    if (landmark === "main") {
      // The app shell owns the single main landmark; a page without one shipped bare.
      await expect(page.locator("main").first(), `${route} main`).toBeVisible({ timeout: 20_000 });
    } else {
      // Auth screens ship their own surface: a card with a form inside.
      await expect(page.locator("form").first(), `${route} form`).toBeVisible({ timeout: 20_000 });
    }
    await page.waitForTimeout(250);
    expect(errors, `${route} console errors`).toEqual([]);
  } finally {
    page.off("console", onConsole);
    page.off("pageerror", onPageError);
  }
}

test("public pages load with chrome and no script errors", async ({ page }) => {
  test.setTimeout(300_000);
  for (const route of PUBLIC_ROUTES) {
    await test.step(route, () => visit(page, route));
  }
  for (const route of AUTH_ROUTES) {
    await test.step(route, () => visit(page, route, "auth"));
  }
});

test("member pages load with chrome and no script errors", async ({ page }) => {
  test.setTimeout(300_000);
  await signIn(page);
  for (const route of MEMBER_ROUTES) {
    await test.step(route, () => visit(page, route));
  }
});
