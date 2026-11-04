import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

/**
 * Vitest only needs to resolve the `@/` alias the app uses; the tests cover pure
 * modules (snap, meter, draft, seed, WAV encoding) so no DOM environment is required.
 */
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
  },
});
