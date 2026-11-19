/**
 * P7 — the 91-template library inside the hosted editor.
 *
 * Boots the packaged Electron main with `CAMXORA_VIZZY_LIBRARY_DIR` pointed at
 * the staged library, opens `/vizzy`, then:
 *   - opens the editor's own Creations browser from the Templates rail,
 *   - asserts the manifest and all 91 rows (with loaded thumbnails),
 *   - fetches the manifest and one thumbnail directly (HTTP 200),
 *   - loads one template and asserts the editor project changed.
 *
 * Requires `npm run build`, `npm run vizzy:build` and a staged library:
 *   $env:CAMXORA_VIZZY_LIBRARY_DIR=".../desktop-electron/vizzy-library"
 */
import fs from "node:fs";
import path from "node:path";
import { _electron as electron } from "playwright";

const root = process.cwd();
const artifacts = path.join(root, "artifacts", "vizzy");
const userData = path.join(root, "artifacts", "vizzy-library", "user-data");
fs.mkdirSync(artifacts, { recursive: true });
fs.rmSync(path.join(root, "artifacts", "vizzy-library"), { recursive: true, force: true });
fs.mkdirSync(userData, { recursive: true });

const libraryRoot = path.resolve(
  process.env.CAMXORA_VIZZY_LIBRARY_DIR ?? path.join(root, "vizzy-library"),
);
if (!fs.existsSync(path.join(libraryRoot, "manifest.json"))) {
  if (process.env.CI === "true" || process.env.CAMXORA_SKIP_VIZZY_LIBRARY === "1") {
    console.log(
      JSON.stringify({
        library: "skipped",
        reason: `No staged Vizzy library at ${libraryRoot}; run npm run vizzy:library for the full gate.`,
      }),
    );
    process.exit(0);
  }
  throw new Error(
    `The Vizzy library is not staged at ${libraryRoot}. Set CAMXORA_VIZZY_LIBRARY_DIR to a ` +
      "staged desktop-electron/vizzy-library folder (npm run vizzy:library).",
  );
}
const rootManifest = JSON.parse(fs.readFileSync(path.join(libraryRoot, "manifest.json"), "utf8"));
if (rootManifest.count !== 91) {
  throw new Error(`Expected the staged library to list 91 templates, got ${rootManifest.count}`);
}

const LOAD_SLUG = "nebula-staff";
const loadEntry = rootManifest.templates.find((entry) => entry.slug === LOAD_SLUG);
if (!loadEntry) throw new Error(`The library does not contain ${LOAD_SLUG}`);

function log(value) {
  console.log(JSON.stringify(value));
}

function fail(message) {
  throw new Error(message);
}

function step(name) {
  process.stdout.write(`[vizzy-library] ${name}\n`);
}

const watchdog = setTimeout(() => {
  console.error("[vizzy-library] timed out");
  process.exit(1);
}, 300_000);
watchdog.unref?.();

const app = await electron.launch({
  args: ["dist-electron/main.cjs"],
  cwd: root,
  env: {
    ...process.env,
    CAMXORA_DEV_AUTH: "1",
    CAMXORA_E2E: "1",
    CAMXORA_USER_DATA_DIR: userData,
    CAMXORA_VIZZY_LIBRARY_DIR: libraryRoot,
    CAMXORA_API_BASE_URL: process.env.CAMXORA_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1",
  },
});

/** Run a script inside the hosted editor's webContents. */
function inView(script) {
  return app.evaluate(async ({ webContents }, source) => {
    const target = webContents
      .getAllWebContents()
      .find((contents) => contents.getURL().startsWith("camxora-vizzy://"));
    if (!target) return null;
    return target.executeJavaScript(source, true);
  }, script);
}

async function poll(fn, label, timeoutMs = 60_000, intervalMs = 300) {
  const deadline = Date.now() + timeoutMs;
  let last;
  while (Date.now() < deadline) {
    last = await fn();
    if (last) return last;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  fail(`Timed out waiting for ${label} (last: ${JSON.stringify(last)})`);
}

try {
  const window = await app.firstWindow();
  await window.waitForLoadState("domcontentloaded");
  await window.getByRole("link", { name: "Vizzy" }).click();
  await window.getByRole("button", { name: "Save", exact: true }).waitFor({ timeout: 15_000 });
  await poll(
    async () => {
      const result = await window.evaluate(async () => window.camxora.vizzy.state());
      return result?.ok && result.data.ready ? result.data : null;
    },
    "the hosted editor to report ready",
  );
  const before = await inView(
    "window.__vizzyTest ? { name: window.__vizzyTest.projectName, nodes: window.__vizzyTest.nodeCount } : null",
  );

  // --- Open the editor's own Creations browser ---------------------------
  await window.getByTestId("vizzy-templates-open").click();
  await window.getByTestId("vizzy-templates-panel").waitFor({ timeout: 10_000 });
  await window.getByTestId("vizzy-library-open").click();

  const catalog = await poll(
    async () =>
      inView(`(() => {
        const rows = document.querySelectorAll(".creation-item .creation-row");
        const intro = document.querySelector(".modal .modal-note");
        return rows.length > 0
          ? { rows: rows.length, intro: intro ? intro.textContent : "", modal: Boolean(document.querySelector(".modal")) }
          : null;
      })()`),
    "the Creations browser to list the library",
    30_000,
  );
  if (catalog.rows !== 91) fail(`Expected 91 creations, got ${catalog.rows}`);
  if (!/\(91\)/.test(catalog.intro)) fail(`Unexpected catalogue intro: ${catalog.intro}`);

  const assets = await inView(`(async () => {
    const manifestResponse = await fetch("/creations/manifest.json", { cache: "no-store" });
    const manifest = manifestResponse.ok ? await manifestResponse.json() : null;
    const creations = Array.isArray(manifest?.creations) ? manifest.creations : [];
    const first = creations[0];
    const thumbResponse = first ? await fetch(first.thumbnail) : null;
    const bytes = thumbResponse ? (await thumbResponse.arrayBuffer()).byteLength : 0;
    const images = Array.from(document.querySelectorAll("img.creation-thumb"));
    const loaded = images.filter((image) => image.complete && image.naturalWidth > 0).length;
    return {
      manifestStatus: manifestResponse.status,
      count: creations.length,
      thumbStatus: thumbResponse ? thumbResponse.status : null,
      thumbBytes: bytes,
      images: images.length,
      loaded,
    };
  })()`);
  if (assets.manifestStatus !== 200) fail(`Manifest HTTP ${assets.manifestStatus}`);
  if (assets.count !== 91) fail(`Manifest lists ${assets.count} creations, expected 91`);
  if (assets.thumbStatus !== 200) fail(`Thumbnail HTTP ${assets.thumbStatus}`);
  if (assets.thumbBytes <= 0) fail("The thumbnail response was empty");
  if (assets.images !== 91) fail(`Expected 91 thumbnail <img> elements, got ${assets.images}`);
  if (assets.loaded < 1) fail("No library thumbnail loaded");
  step("catalogue and thumbnails verified");

  const libraryShot = await app.evaluate(async ({ webContents }) => {
    const target = webContents
      .getAllWebContents()
      .find((contents) => contents.getURL().startsWith("camxora-vizzy://"));
    if (!target) return null;
    const image = await target.capturePage();
    return image.isEmpty() ? null : image.toDataURL();
  });
  if (libraryShot) {
    fs.writeFileSync(
      path.join(artifacts, "library.png"),
      Buffer.from(libraryShot.split(",")[1], "base64"),
    );
  }
  await window.screenshot({ path: path.join(artifacts, "library-shell.png") });

  // --- Load one template -------------------------------------------------
  const rowFound = await inView(`(() => {
    const rows = Array.from(document.querySelectorAll(".creation-item .creation-row"));
    const target = rows.find((row) => (row.querySelector(".creation-name")?.textContent ?? "").trim() === ${JSON.stringify(loadEntry.name)})
      ?? rows[0];
    if (!target) return false;
    target.click();
    return true;
  })()`);
  if (!rowFound) fail("Could not click a library row");
  const confirmed = await poll(
    async () =>
      inView(`(() => {
        const button = Array.from(document.querySelectorAll(".modal .mini.accent"))
          .find((node) => /load template/i.test(node.textContent ?? ""));
        if (!button) return false;
        button.click();
        return true;
      })()`),
    "the load-template confirmation",
    15_000,
    250,
  );
  if (!confirmed) fail("The load confirmation did not appear");

  const loaded = await poll(
    async () =>
      inView(`window.__vizzyTest && window.__vizzyTest.projectName !== ${JSON.stringify(before?.name ?? "")}
        ? { name: window.__vizzyTest.projectName, nodes: window.__vizzyTest.nodeCount, ready: window.__vizzyTest.ready }
        : null`),
    "the library project to load into the editor",
    120_000,
    500,
  );
  if (!loaded.ready) fail("The editor is not ready after loading a library template");
  if (!(loaded.nodes > 0)) fail("The loaded library project has no nodes");
  step(`loaded ${loaded.name} (${loaded.nodes} items)`);

  const afterShot = await app.evaluate(async ({ webContents }) => {
    const target = webContents
      .getAllWebContents()
      .find((contents) => contents.getURL().startsWith("camxora-vizzy://"));
    if (!target) return null;
    const image = await target.capturePage();
    return image.isEmpty() ? null : image.toDataURL();
  });
  if (afterShot) {
    fs.writeFileSync(
      path.join(artifacts, "library-loaded.png"),
      Buffer.from(afterShot.split(",")[1], "base64"),
    );
  }

  log({
    libraryRoot,
    catalog,
    assets,
    load: { slug: LOAD_SLUG, before, after: loaded },
    artifacts,
  });
} finally {
  clearTimeout(watchdog);
  await app.close();
}
