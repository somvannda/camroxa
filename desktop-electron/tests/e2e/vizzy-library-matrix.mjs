import fs from "node:fs";
import path from "node:path";
import { _electron as electron } from "playwright";

const root = process.cwd();
const artifacts = path.join(root, "artifacts");
const userData = path.join(artifacts, "e2e-library-matrix");
fs.mkdirSync(artifacts, { recursive: true });
fs.rmSync(userData, { recursive: true, force: true });

const libraryRoot =
  process.env.CAMXORA_VIZZY_LIBRARY_DIR ||
  path.join(root, "vizzy-library");
const manifest = JSON.parse(
  fs.readFileSync(path.join(libraryRoot, "creations", "manifest.json"), "utf8"),
).creations;

const app = await electron.launch({
  args: ["dist-electron/main.cjs"],
  cwd: root,
  env: {
    ...process.env,
    CAMXORA_DEV_AUTH: "1",
    CAMXORA_USER_DATA_DIR: userData,
    CAMXORA_E2E: "1",
    CAMXORA_VIZZY_LIBRARY_DIR: libraryRoot,
  },
});

const results = [];
try {
  const window = await app.firstWindow();
  await window.waitForLoadState("domcontentloaded");
  await window.evaluate(() => {
    window.location.hash = "#/vizzy";
  });

  let ready = false;
  for (let attempt = 0; attempt < 30 && !ready; attempt += 1) {
    await window.waitForTimeout(500);
    ready = await app.evaluate(async ({ webContents }) =>
      Boolean(
        webContents
          .getAllWebContents()
          .find((contents) => contents.getURL().startsWith("camxora-vizzy://")),
      ),
    );
  }
  if (!ready) throw new Error("Editor did not attach");
  await window.waitForTimeout(2500);

  for (const entry of manifest) {
    const started = Date.now();
    const result = await app.evaluate(
      async ({ webContents }, payload) => {
        const target = webContents
          .getAllWebContents()
          .find((contents) => contents.getURL().startsWith("camxora-vizzy://"));
        if (!target) return { ok: false, error: "no view" };
        return target.executeJavaScript(
          `(async () => {
            try {
              const response = await fetch(${JSON.stringify(payload.file)}, { cache: "no-store" });
              if (!response.ok) return { ok: false, error: "HTTP " + response.status };
              const raw = await response.json();
              const report = await window.editorImportProject(raw);
              await new Promise((resolve) => setTimeout(resolve, 350));
              return {
                ok: true,
                name: report.name,
                nodes: report.nodes,
                layers: report.layers,
                skipped: report.skipped?.length ?? 0,
                notes: report.notes?.slice(0, 3) ?? [],
              };
            } catch (error) {
              return { ok: false, error: String(error && error.message ? error.message : error) };
            }
          })()`,
          true,
        );
      },
      entry,
    );
    results.push({ slug: entry.id, ms: Date.now() - started, ...result });
    const label = result.ok ? `ok ${result.nodes} nodes` : `FAIL ${result.error}`;
    console.log(`${entry.id}: ${label} (${Date.now() - started} ms)`);
  }

  const failures = results.filter((item) => !item.ok);
  console.log(
    JSON.stringify({
      total: results.length,
      passed: results.length - failures.length,
      failed: failures.length,
      slowest: [...results].sort((a, b) => b.ms - a.ms).slice(0, 5),
      failures,
    }),
  );
  fs.writeFileSync(
    path.join(artifacts, "vizzy", "library-matrix.json"),
    JSON.stringify(results, null, 2),
  );
} finally {
  await app.close();
}
