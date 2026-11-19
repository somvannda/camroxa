import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "dist-electron", "vizzy-dist", "vizzy", "node_modules", "release"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      globals: { ...globals.browser },
    },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
    },
  },
  {
    files: [
      "electron/**/*.ts",
      "vite.config.ts",
      "vitest.config.ts",
      "tailwind.config.ts",
      "scripts/**/*.mjs",
      "tests/**/*.mjs",
    ],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
);
