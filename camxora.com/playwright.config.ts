import { defineConfig, devices } from "@playwright/test";

/**
 * Smoke config for the Studio editor (W5.4).
 *
 * Runs against an already-running dev server by default, so it can be used locally
 * without a database bootstrap; CI overrides BASE_URL and starts the app itself.
 */
export default defineConfig({
  testDir: "tests/e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  // The specs share one dev server and one sandbox account and some decode audio; more
  // workers than this starves the machine and turns timing-based checks flaky.
  workers: 4,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3103",
    trace: "off",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
  },
});
