/**
 * Build a Windows installer for one environment.
 *
 *   node scripts/package-release.mjs --env production
 *   node scripts/package-release.mjs --env sandbox
 *
 * The packaged app has no environment variables to read at launch, so the
 * platform endpoints and the environment label are baked into the main bundle
 * with esbuild `define` (the plain `npm run build` keeps the production
 * defaults). Sandbox and production installers are written to separate output
 * folders and use distinct artifact names.
 */
import { spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");

const args = process.argv.slice(2);
const envIndex = args.indexOf("--env");
const environment = (envIndex >= 0 ? args[envIndex + 1] : "production").trim().toLowerCase();
if (environment !== "production" && environment !== "sandbox") {
  console.error("Use --env production or --env sandbox.");
  process.exit(2);
}

const endpoints =
  environment === "sandbox"
    ? {
        api: "https://api.sandbox.camxora.com/api/v1",
        portal: "https://app.sandbox.camxora.com",
      }
    : {
        api: "https://api.camxora.com/api/v1",
        portal: "https://app.camxora.com",
      };

const pkg = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
const version = String(pkg.version || "0.0.0");
const outputDir = `release-${environment}`;
const artifactName =
  environment === "sandbox"
    ? `Camxora-\${version}-sandbox-setup.\${ext}`
    : `Camxora-\${version}-setup.\${ext}`;

function run(command, commandArgs, options = {}) {
  const result = spawnSync(command, commandArgs, {
    cwd: root,
    stdio: "inherit",
    shell: options.shell ?? process.platform === "win32",
    ...options,
  });
  if (result.status !== 0) {
    console.error(`\n${command} ${commandArgs.join(" ")} failed (${result.status ?? "signal"}).`);
    process.exit(result.status ?? 1);
  }
}

function esbuild(entry, outfile, extra = []) {
  // No shell here: `process.execPath` contains spaces ("C:\Program Files\...").
  run(
    process.execPath,
    [
      path.join(root, "node_modules", "esbuild", "bin", "esbuild"),
      entry,
      "--bundle",
      "--platform=node",
      "--format=cjs",
      `--outfile=${outfile}`,
      "--external:electron",
      "--external:electron-updater",
      "--sourcemap",
      ...extra,
    ],
    { shell: false },
  );
}

const define = [
  `--define:process.env.CAMXORA_API_BASE_URL=${JSON.stringify(endpoints.api)}`,
  `--define:process.env.CAMXORA_PORTAL_BASE_URL=${JSON.stringify(endpoints.portal)}`,
  `--define:process.env.CAMXORA_BUILD_ENV=${JSON.stringify(environment)}`,
];

console.log(`\n=== Camxora ${version} (${environment}) ===`);
console.log(`API    ${endpoints.api}`);
console.log(`Portal ${endpoints.portal}`);
console.log(`Output ${outputDir}/${artifactName.replace("${version}", version).replace("${ext}", "exe")}\n`);

run("npm", ["run", "typecheck"]);
run("npm", ["run", "build:renderer"]);
esbuild("electron/main.ts", "dist-electron/main.cjs", define);
esbuild("electron/preload.ts", "dist-electron/preload.cjs", define);
esbuild("electron/vizzy-preload.ts", "dist-electron/vizzy-preload.cjs", define);

run("npm", ["run", "vizzy:build"]);
run("npm", ["run", "vizzy:library:check"]);

run("npx", [
  "electron-builder",
  "--win",
  "nsis",
  `--config.directories.output=${outputDir}`,
  `--config.win.artifactName=${artifactName}`,
]);

const installer = path.join(root, outputDir, `Camxora-${version}${environment === "sandbox" ? "-sandbox" : ""}-setup.exe`);
if (!fs.existsSync(installer)) {
  console.error(`Installer was not produced: ${installer}`);
  process.exit(1);
}
const digest = crypto.createHash("sha256").update(fs.readFileSync(installer)).digest("hex");
console.log(`\nInstaller ${installer}`);
console.log(`Size      ${(fs.statSync(installer).size / 1048576).toFixed(1)} MB`);
console.log(`SHA-256   ${digest}`);
