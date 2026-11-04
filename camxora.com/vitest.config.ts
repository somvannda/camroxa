import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

/**
 * Two kinds of test live here:
 *   - pure modules (snap, meter, draft, seed, WAV encoding) run in `node`
 *   - component tests render with jsdom
 * The `@/` alias has to resolve for both.
 */
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    globals: false,
  },
});
