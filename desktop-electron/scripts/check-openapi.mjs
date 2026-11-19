import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const source = path.join(root, "openapi.json");
const target = path.join(root, "src/lib/api-schema.d.ts");
const temp = path.join(root, "src/lib/api-schema.d.ts.tmp");

if (!fs.existsSync(source)) {
  console.error("openapi.json is missing. Generate it from platform_api first.");
  process.exit(1);
}

const cli = path.join(root, "node_modules/openapi-typescript/bin/cli.js");
execFileSync(process.execPath, [cli, source, "-o", temp], { stdio: "inherit" });

const current = fs.existsSync(target) ? fs.readFileSync(target, "utf8") : "";
const next = fs.readFileSync(temp, "utf8");
fs.rmSync(temp, { force: true });

if (current !== next) {
  console.error("API schema drift: regenerate with `npm run api:types`.");
  process.exit(1);
}

console.log("API schema is up to date.");
