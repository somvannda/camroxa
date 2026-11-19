/**
 * P7 — the real Rea/Vizzy editor inside the Camxora shell.
 *
 * Boots the packaged Electron main, navigates to /vizzy, waits for the hosted
 * `WebContentsView`, then proves:
 *   - the editor chrome and stage canvas rendered,
 *   - the document is cross-origin isolated and WebGL2 is live,
 *   - the view cannot reach the shell bridge,
 *   - Save → Open → Save is a semantic round-trip,
 *   - no session email or token reaches the editor or the project file.
 *
 * Requires `npm run build` and `npm run vizzy:build` first.
 */
import fs from "node:fs";
import path from "node:path";
import { _electron as electron } from "playwright";

const root = process.cwd();
const artifacts = path.join(root, "artifacts", "vizzy");
const userData = path.join(artifacts, "user-data");
fs.mkdirSync(artifacts, { recursive: true });
fs.rmSync(userData, { recursive: true, force: true });

const projectExtension = ".camxora-vizzy.json";

function log(value) {
  console.log(JSON.stringify(value));
}

function fail(message) {
  throw new Error(message);
}

/**
 * Rea's snapshot captures a few per-frame analyser outputs on node props
 * (`currentData`, `cumulativeData`, `cumMult`). They are runtime values, not
 * authored state, and they change whenever the playhead moves — including when a
 * project is reopened. Semantic equality therefore compares everything except
 * these three counters. See docs/electron-desktop/vizzy/INTEGRATION-STATUS.md.
 */
const VOLATILE_RUNTIME_PROPS = new Set(["currentData", "cumulativeData", "cumMult"]);

function normalise(node) {
  if (Array.isArray(node)) return node.map(normalise);
  if (node && typeof node === "object") {
    const output = {};
    for (const key of Object.keys(node)) {
      if (VOLATILE_RUNTIME_PROPS.has(key)) continue;
      output[key] = normalise(node[key]);
    }
    return output;
  }
  return node;
}

function semantic(value) {
  const snapshot = normalise(JSON.parse(typeof value === "string" ? value : JSON.stringify(value)));
  delete snapshot.savedAt;
  const sort = (input) => {
    if (Array.isArray(input)) return input.map(sort);
    if (input && typeof input === "object") {
      const output = {};
      for (const key of Object.keys(input).sort()) output[key] = sort(input[key]);
      return output;
    }
    return input;
  };
  return JSON.stringify(sort(snapshot));
}

/** First differing JSON path, for a readable failure. */
function firstDifference(left, right, at = "$") {
  const a = normalise(JSON.parse(typeof left === "string" ? left : JSON.stringify(left)));
  const b = normalise(JSON.parse(typeof right === "string" ? right : JSON.stringify(right)));
  delete a.savedAt;
  delete b.savedAt;
  const walk = (x, y, pointer) => {
    if (typeof x !== typeof y) return `${pointer}: ${typeof x} vs ${typeof y}`;
    if (x === null || y === null || typeof x !== "object") {
      return x === y ? null : `${pointer}: ${JSON.stringify(x)} vs ${JSON.stringify(y)}`;
    }
    if (Array.isArray(x) !== Array.isArray(y)) return `${pointer}: array/object mismatch`;
    if (Array.isArray(x)) {
      if (x.length !== y.length) return `${pointer}: length ${x.length} vs ${y.length}`;
      for (let index = 0; index < x.length; index += 1) {
        const found = walk(x[index], y[index], `${pointer}[${index}]`);
        if (found) return found;
      }
      return null;
    }
    const keys = new Set([...Object.keys(x), ...Object.keys(y)]);
    for (const key of keys) {
      if (!(key in x)) return `${pointer}.${key}: missing on the left`;
      if (!(key in y)) return `${pointer}.${key}: missing on the right`;
      const found = walk(x[key], y[key], `${pointer}.${key}`);
      if (found) return found;
    }
    return null;
  };
  return walk(a, b, at);
}

const app = await electron.launch({
  args: ["dist-electron/main.cjs"],
  cwd: root,
  env: {
    ...process.env,
    CAMXORA_DEV_AUTH: "1",
    CAMXORA_E2E: "1",
    CAMXORA_USER_DATA_DIR: userData,
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

/** Poll an async page function until it returns truthy. */
async function poll(window, fn, label, timeoutMs = 60_000, intervalMs = 400) {
  const deadline = Date.now() + timeoutMs;
  let last;
  while (Date.now() < deadline) {
    last = await window.evaluate(fn);
    if (last) return last;
    await window.waitForTimeout(intervalMs);
  }
  fail(`Timed out waiting for ${label} (last: ${JSON.stringify(last)})`);
}

try {
  const window = await app.firstWindow();
  await window.waitForLoadState("domcontentloaded");
  await window.getByRole("link", { name: "Vizzy" }).click();
  await window.getByRole("button", { name: "Save", exact: true }).waitFor({ timeout: 15_000 });

  // The view reports attached + ready once the adapter has booted the editor.
  const state = await poll(
    window,
    async () => {
      const result = await window.camxora.vizzy.state();
      return result?.ok && result.data.attached && result.data.ready ? result.data : null;
    },
    "the hosted editor to report ready",
  );
  if (!state.attached) fail("vizzy:state does not report an attached view");

  const snapshot = await inView(`(() => {
    const test = window.__vizzyTest;
    return test ? {
      ready: test.ready,
      projectName: test.projectName,
      dirty: test.dirty,
      nodeCount: test.nodeCount,
      crossOriginIsolated: test.crossOriginIsolated,
      fftTier: test.fftTier,
    } : null;
  })()`);
  if (!snapshot) fail("window.__vizzyTest is missing inside the hosted editor");

  const dom = await inView(`(() => {
    const stage = document.querySelector("#stage");
    let stageContext = null;
    try {
      stageContext = stage ? stage.getContext("webgl2") : null;
    } catch {
      stageContext = null;
    }
    const canvas = document.createElement("canvas");
    return {
      url: location.href,
      title: document.title,
      hasTopbar: Boolean(document.querySelector("#topbar")),
      hasRail: Boolean(document.querySelector("#rail")),
      hasInspector: Boolean(document.querySelector("#inspector")),
      hasTimeline: Boolean(document.querySelector("#timeline")),
      menus: Array.from(document.querySelectorAll("#menus .menu")).map((node) => node.textContent),
      stage: stage ? { width: stage.width, height: stage.height } : null,
      stageWebgl2: Boolean(stageContext),
      newCanvasWebgl2: Boolean(canvas.getContext("webgl2")),
      isolated: window.crossOriginIsolated === true,
      hasVizzyBridge: typeof window.camxoraVizzy === "object",
      hasShellBridge: typeof window.camxora !== "undefined",
      text: document.body.innerText.slice(0, 400),
    };
  })()`);
  if (!dom) fail("Could not read the hosted editor document");

  const probe = await window.evaluate(async () => window.camxora.vizzy.probe());
  if (!probe.ok) fail(`vizzy:probe failed: ${probe.error.message}`);

  const sessionResult = await window.evaluate(async () => window.camxora.auth.restore());
  const email = sessionResult.ok ? (sessionResult.data.session?.email ?? null) : null;

  // --- Save → Open → Save round-trip -------------------------------------
  const first = await window.evaluate(async () => window.camxora.vizzy.save());
  if (!first.ok) fail(`vizzy:save failed: ${first.error.message}`);
  if (!first.data.path.endsWith(projectExtension)) {
    fail(`Unexpected project path: ${first.data.path}`);
  }
  const firstJson = fs.readFileSync(first.data.path, "utf8");
  fs.writeFileSync(path.join(artifacts, "saved-project.json"), firstJson);

  const opened = await window.evaluate(
    async (filePath) => window.camxora.vizzy.openPath(filePath),
    first.data.path,
  );
  if (!opened.ok) fail(`vizzy:open-path failed: ${opened.error.message}`);

  const second = await window.evaluate(async () => window.camxora.vizzy.save());
  if (!second.ok) fail(`second vizzy:save failed: ${second.error.message}`);
  const secondJson = fs.readFileSync(second.data.path, "utf8");
  const roundTripEqual = semantic(firstJson) === semantic(secondJson);
  const roundTripDiff = roundTripEqual ? null : firstDifference(firstJson, secondJson);
  if (!roundTripEqual) {
    fs.writeFileSync(path.join(artifacts, "saved-project-second.json"), secondJson);
  }

  const afterOpen = await inView(`window.__vizzyTest ? {
    projectName: window.__vizzyTest.projectName,
    dirty: window.__vizzyTest.dirty,
    nodeCount: window.__vizzyTest.nodeCount,
    ready: window.__vizzyTest.ready,
  } : null`);

  // --- The editor's own Ctrl+S goes through the native store -------------
  const savedMtime = fs.statSync(first.data.path).mtimeMs;
  await window.waitForTimeout(1_200);
  await app.evaluate(async ({ webContents }) => {
    const target = webContents
      .getAllWebContents()
      .find((contents) => contents.getURL().startsWith("camxora-vizzy://"));
    if (!target) return;
    target.focus();
    target.sendInputEvent({ type: "keyDown", keyCode: "s", modifiers: ["control"] });
    target.sendInputEvent({ type: "keyUp", keyCode: "s", modifiers: ["control"] });
  });
  const keyboardSaveDeadline = Date.now() + 10_000;
  let keyboardSave = false;
  while (Date.now() < keyboardSaveDeadline) {
    if (fs.statSync(first.data.path).mtimeMs > savedMtime) {
      keyboardSave = true;
      break;
    }
    await window.waitForTimeout(250);
  }
  if (!keyboardSave) fail("Ctrl+S inside the editor did not reach the native project store");

  // --- Screenshots -------------------------------------------------------
  await window.screenshot({ path: path.join(artifacts, "shell.png") });
  const editorShot = await app.evaluate(async ({ webContents }) => {
    const target = webContents
      .getAllWebContents()
      .find((contents) => contents.getURL().startsWith("camxora-vizzy://"));
    if (!target) return null;
    const image = await target.capturePage();
    return image.isEmpty() ? null : image.toDataURL();
  });
  if (editorShot) {
    fs.writeFileSync(
      path.join(artifacts, "editor.png"),
      Buffer.from(editorShot.split(",")[1], "base64"),
    );
  }

  const summary = {
    state,
    snapshot,
    probe: probe.data,
    dom: {
      url: dom.url,
      title: dom.title,
      hasTopbar: dom.hasTopbar,
      hasRail: dom.hasRail,
      hasInspector: dom.hasInspector,
      hasTimeline: dom.hasTimeline,
      menus: dom.menus,
      stage: dom.stage,
      stageWebgl2: dom.stageWebgl2,
      newCanvasWebgl2: dom.newCanvasWebgl2,
      isolated: dom.isolated,
      hasVizzyBridge: dom.hasVizzyBridge,
      hasShellBridge: dom.hasShellBridge,
    },
    afterOpen,
    roundTrip: {
      path: first.data.path,
      bytes: first.data.bytes,
      equal: roundTripEqual,
      diff: roundTripDiff,
      nodeCount: opened.data.nodeCount,
    },
    editorScreenshot: Boolean(editorShot),
    artifacts,
  };
  log(summary);

  // --- Assertions --------------------------------------------------------
  if (!dom.hasTopbar || !dom.hasRail || !dom.hasInspector || !dom.hasTimeline) {
    fail("The editor chrome did not render");
  }
  if (!dom.stage || dom.stage.width < 64 || dom.stage.height < 64) {
    fail(`The stage canvas is not sized: ${JSON.stringify(dom.stage)}`);
  }
  if (!dom.stageWebgl2 || !dom.newCanvasWebgl2) fail("WebGL2 is not available in the hosted editor");
  if (!dom.isolated || snapshot.crossOriginIsolated !== true) {
    fail("The hosted editor is not cross-origin isolated");
  }
  if (!dom.hasVizzyBridge) fail("The dedicated Vizzy preload did not inject window.camxoraVizzy");
  if (dom.hasShellBridge) fail("The hosted editor can reach the shell bridge (window.camxora)");
  if (!snapshot.ready) fail("window.__vizzyTest reports not ready");
  if (snapshot.nodeCount < 3) fail(`Expected the seeded project nodes, got ${snapshot.nodeCount}`);
  if (snapshot.fftTier === "unknown") fail("The editor did not report an FFT tier");
  if (state.fftTier !== snapshot.fftTier) {
    fail(`Shell strip FFT tier ${state.fftTier} != editor ${snapshot.fftTier}`);
  }
  if (!probe.data.webgl2) fail("vizzy:probe reports no WebGL2");
  if (!roundTripEqual) fail(`Save → Open → Save is not semantically identical: ${roundTripDiff}`);
  if (opened.data.nodeCount !== snapshot.nodeCount) {
    fail(`Open reported ${opened.data.nodeCount} nodes, editor has ${snapshot.nodeCount}`);
  }
  if (!firstJson.includes('"format": "studio-project"')) {
    fail("The saved project is not a studio-project snapshot");
  }
  if (email && (firstJson.includes(email) || dom.text.includes(email))) {
    fail("The session email leaked into the editor or the project file");
  }
  if (/accessToken|refreshToken/.test(firstJson)) {
    fail("The project file contains session token fields");
  }
  if (!editorShot) fail("Could not capture the hosted editor");

  // --- Route leave detaches the view and stops the process ---------------
  await window.getByRole("link", { name: "Dashboard" }).click();
  await poll(
    window,
    async () => {
      const result = await window.camxora.vizzy.state();
      return result?.ok && result.data.attached === false ? result.data : null;
    },
    "the view to detach on route leave",
    15_000,
  );
  const survivor = await app.evaluate(async ({ webContents }) =>
    webContents.getAllWebContents().some((contents) => contents.getURL().startsWith("camxora-vizzy://")),
  );
  if (survivor) fail("The Vizzy view survived the route change");

  // --- Back to Vizzy, then crash isolation and auto-reload ---------------
  await window.getByRole("link", { name: "Vizzy" }).click();
  await poll(
    window,
    async () => {
      const result = await window.camxora.vizzy.state();
      return result?.ok && result.data.ready ? result.data : null;
    },
    "the editor to boot again",
  );

  const crashed = await app.evaluate(async ({ webContents }) => {
    const target = webContents
      .getAllWebContents()
      .find((contents) => contents.getURL().startsWith("camxora-vizzy://"));
    if (!target) return false;
    target.forcefullyCrashRenderer();
    return true;
  });
  if (!crashed) fail("Could not find the editor process to crash");

  await poll(
    window,
    async () => {
      const result = await window.camxora.vizzy.state();
      return result?.ok && result.data.crashed ? result.data : null;
    },
    "the crash to be reported",
    20_000,
    200,
  );
  const shellAlive = await window.evaluate("({ title: document.title, url: location.href })");
  if (!shellAlive?.title) fail("The shell did not survive the editor crash");

  const recovered = await poll(
    window,
    async () => {
      const result = await window.camxora.vizzy.state();
      return result?.ok && result.data.ready && !result.data.crashed ? result.data : null;
    },
    "the editor to reload after the crash",
    45_000,
    500,
  );
  log({ crashIsolation: true, shellAlive, recovered });
} finally {
  await app.close();
}
