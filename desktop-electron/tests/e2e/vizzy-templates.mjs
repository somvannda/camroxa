/* global document, HTMLImageElement, HTMLVideoElement */
/**
 * P7 — save the current preview as a video template, preview it, render it.
 *
 * Boots the packaged Electron main with dev auth, opens `/vizzy`, loads the
 * Trap Motion fixture, then:
 *   - opens "Save as video template" and asserts the detected bindings,
 *   - blocks a duplicate binding with a field error,
 *   - saves the template and asserts template.json / pipeline.json / thumbnail.png,
 *   - lists it in the Templates rail (thumbnail, kind, output size),
 *   - previews it and proves the editor project is semantically identical,
 *   - renders it with a generated 2 s WAV through the real UI path (the native
 *     picker is stubbed in the main process), asserting streamed progress,
 *   - ffprobes the MP4 (h264/aac, 1920×1080, ~2 s) and finds it in Renders.
 *
 * Requires `npm run build` and `npm run vizzy:build` first.
 */
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { _electron as electron } from "playwright";

const root = process.cwd();
const artifacts = path.join(root, "artifacts", "vizzy");
const tempRoot = path.join(root, "artifacts", "vizzy-templates");
const userData = path.join(tempRoot, "user-data");
const templatesDir = path.join(userData, "templates");
const rendersDir = path.join(userData, "renders");
fs.mkdirSync(artifacts, { recursive: true });
fs.rmSync(tempRoot, { recursive: true, force: true });
fs.mkdirSync(userData, { recursive: true });

const fixture = path.join(root, "tests", "fixtures", "vizzy", "trap-motion.camxora-vizzy.json");
const TEMPLATE_NAME = "Trap Motion Template";

function log(value) {
  console.log(JSON.stringify(value));
}

function fail(message) {
  throw new Error(message);
}

function step(name) {
  process.stdout.write(`[vizzy-templates] ${name}\n`);
}

const watchdog = setTimeout(() => {
  console.error("[vizzy-templates] timed out");
  process.exit(1);
}, 900_000);
watchdog.unref?.();

/** 2 s mono 16-bit WAV: a quiet sine tone the editor can decode. */
function writeWav(filePath, seconds = 2, rate = 44_100) {
  const samples = Math.round(seconds * rate);
  const data = Buffer.alloc(samples * 2);
  for (let index = 0; index < samples; index += 1) {
    const value = Math.round(
      Math.sin((2 * Math.PI * 220 * index) / rate) * 0.25 * 0x7fff,
    );
    data.writeInt16LE(value, index * 2);
  }
  const header = Buffer.alloc(44);
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + data.length, 4);
  header.write("WAVE", 8);
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(rate, 24);
  header.writeUInt32LE(rate * 2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write("data", 36);
  header.writeUInt32LE(data.length, 40);
  fs.writeFileSync(filePath, Buffer.concat([header, data]));
}

function ffprobe(filePath) {
  const binary = process.env.CAMXORA_FFPROBE_PATH ?? "ffprobe";
  const result = spawnSync(
    binary,
    ["-v", "error", "-print_format", "json", "-show_format", "-show_streams", filePath],
    { encoding: "utf8" },
  );
  if (result.error) fail(`ffprobe could not run (${result.error.message}); set CAMXORA_FFPROBE_PATH`);
  if (result.status !== 0) fail(`ffprobe failed: ${(result.stderr ?? "").trim()}`);
  const payload = JSON.parse(result.stdout);
  const video = payload.streams?.find((stream) => stream.codec_type === "video");
  const audio = payload.streams?.find((stream) => stream.codec_type === "audio");
  return {
    duration: Number(payload.format?.duration ?? 0),
    format: payload.format?.format_name ?? null,
    videoCodec: video?.codec_name ?? null,
    width: video?.width ?? null,
    height: video?.height ?? null,
    audioCodec: audio?.codec_name ?? null,
    frames: Number(video?.nb_frames ?? 0),
  };
}

const VOLATILE_RUNTIME_PROPS = new Set([
  "currentData",
  "cumulativeData",
  "cumMult",
  // Rea's particle node adds a null texture cache slot when a project loads.
  "particleTexture",
]);

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

/** First differing JSON path, so a mismatch is actionable. */
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
      return result?.ok && result.data.attached && result.data.ready ? result.data : null;
    },
    "the hosted editor to report ready",
  );

  const opened = await window.evaluate(
    async (filePath) => window.camxora.vizzy.openPath(filePath),
    fixture,
  );
  if (!opened.ok) fail(`vizzy:open-path failed: ${opened.error.message}`);
  const fixtureJson = fs.readFileSync(fixture, "utf8");
  step("fixture opened");

  // --- Save dialog: detection, duplicate guard, then save -----------------
  await window.getByTestId("vizzy-template-open").click();
  const dialog = window.getByTestId("vizzy-template-dialog");
  await dialog.waitFor({ timeout: 20_000 });
  const kindValue = await window.getByTestId("vizzy-template-kind").inputValue();
  if (kindValue !== "long") fail(`Expected kind "long", got ${kindValue}`);
  const outputText = await window.getByTestId("vizzy-template-output").innerText();
  if (!outputText.includes("1920") || !outputText.includes("1080") || !outputText.includes("30 fps")) {
    fail(`Unexpected output summary: ${outputText}`);
  }
  const audioText = await window.getByTestId("vizzy-template-audio").innerText();
  if (!/run track replaces project audio/i.test(audioText)) {
    fail(`Unexpected audio binding copy: ${audioText}`);
  }
  const backgroundSelect = window.getByTestId("vizzy-template-binding-background");
  const backgroundOptions = await backgroundSelect.locator("option").count();
  if (backgroundOptions < 2) fail("Background select has no detected node option");
  const paletteValue = await window.getByTestId("vizzy-template-binding-palette").inputValue();
  if (!paletteValue) fail("The palette binding was not detected");
  await window.getByTestId("vizzy-template-name").fill(TEMPLATE_NAME);
  await window.screenshot({ path: path.join(artifacts, "save-dialog.png") });

  // Duplicate: the same media node cannot be background and logo.
  const mediaNodeId = await backgroundSelect
    .locator("option")
    .nth(1)
    .getAttribute("value");
  if (!mediaNodeId) fail("Could not read the media node id");
  await backgroundSelect.selectOption(mediaNodeId);
  await window.getByTestId("vizzy-template-binding-logo").selectOption(mediaNodeId);
  await window.getByTestId("vizzy-template-error-logo").waitFor({ timeout: 5_000 });
  const duplicateMessage = await window.getByTestId("vizzy-template-error-logo").innerText();
  if (!/already bound/i.test(duplicateMessage)) {
    fail(`Expected a duplicate-binding error, got: ${duplicateMessage}`);
  }
  const saveDisabled = await window.getByTestId("vizzy-template-save").isDisabled();
  if (!saveDisabled) fail("Save must be blocked while a duplicate binding is selected");

  // Compatible selection: clear the logo, keep the background override.
  await window.getByTestId("vizzy-template-binding-logo").selectOption("");
  await window.getByTestId("vizzy-template-error-logo").waitFor({ state: "detached", timeout: 5_000 });
  await window.getByTestId("vizzy-template-save").click();
  await dialog.waitFor({ state: "detached", timeout: 30_000 });
  step("template saved");

  const templateDirs = fs.readdirSync(templatesDir).filter((name) => !name.startsWith("."));
  if (templateDirs.length !== 1) fail(`Expected one template, got ${JSON.stringify(templateDirs)}`);
  const templateId = templateDirs[0];
  const templateDir = path.join(templatesDir, templateId);
  for (const file of ["template.json", "pipeline.json", "thumbnail.png"]) {
    if (!fs.existsSync(path.join(templateDir, file))) fail(`Missing ${file} in ${templateDir}`);
  }
  const templateJson = fs.readFileSync(path.join(templateDir, "template.json"), "utf8");
  const pipeline = JSON.parse(fs.readFileSync(path.join(templateDir, "pipeline.json"), "utf8"));
  const thumbnail = fs.readFileSync(path.join(templateDir, "thumbnail.png"));
  if (!thumbnail.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) {
    fail("thumbnail.png is not a PNG");
  }
  if (thumbnail.byteLength < 1_000) fail(`thumbnail.png is suspiciously small: ${thumbnail.byteLength}`);
  if (semantic(templateJson) !== semantic(fixtureJson)) {
    fail("template.json is not semantically the project that was previewed");
  }
  if (pipeline.kind !== "long" || pipeline.output.width !== 1920 || pipeline.output.height !== 1080) {
    fail(`Unexpected pipeline output: ${JSON.stringify(pipeline.output)}`);
  }
  if (pipeline.bindings.background?.nodeId !== mediaNodeId) {
    fail(`Background override not saved: ${JSON.stringify(pipeline.bindings.background)}`);
  }
  if (!pipeline.bindings.palette?.nodeIds?.length) fail("Palette binding not saved");
  step("template files verified");

  // --- Templates rail -----------------------------------------------------
  // A successful save opens the Templates rail; it lists the new template.
  const panel = window.getByTestId("vizzy-templates-panel");
  await panel.waitFor({ timeout: 10_000 });
  const row = panel.getByTestId("vizzy-template-row").filter({ hasText: TEMPLATE_NAME });
  await row.waitFor({ timeout: 10_000 });
  const rowText = await row.innerText();
  if (!/long/i.test(rowText) || !rowText.includes("1920×1080")) {
    fail(`Template row is missing kind/size: ${rowText}`);
  }
  const thumb = row.getByTestId("vizzy-template-thumb");
  await thumb.waitFor({ timeout: 10_000 });
  const thumbInfo = await poll(
    async () =>
      window.evaluate(() => {
        const image = document.querySelector('[data-testid="vizzy-template-thumb"]');
        if (!(image instanceof HTMLImageElement)) return null;
        return image.complete && image.naturalWidth > 0
          ? { width: image.naturalWidth, height: image.naturalHeight, src: image.getAttribute("src") }
          : null;
      }),
    "the template thumbnail to load",
    15_000,
  );
  if (!thumbInfo.src?.startsWith("camxora-media://")) {
    fail(`Thumbnail did not use camxora-media://: ${thumbInfo.src}`);
  }
  await window.screenshot({ path: path.join(artifacts, "templates-panel.png") });
  step("templates rail verified");

  // --- Preview: the saved project is loaded semantically unchanged --------
  await row.getByTestId("vizzy-template-preview").click();
  const liveProject = await poll(
    async () => {
      const value = await inView(`window.__vizzyTest ? window.__vizzyTest.readProjectJson() : null`);
      return typeof value === "string" && value.length > 0 ? value : null;
    },
    "the previewed template to load in the editor",
    30_000,
  );
  if (semantic(liveProject) !== semantic(templateJson)) {
    fs.writeFileSync(path.join(tempRoot, "live-preview.json"), liveProject);
    fail(
      `Preview is not semantically identical to the saved template.json: ${firstDifference(
        templateJson,
        liveProject,
      )}`,
    );
  }
  const previewName = await inView("window.__vizzyTest ? window.__vizzyTest.projectName : null");
  const savedProjectName = JSON.parse(templateJson).project?.name;
  if (previewName !== savedProjectName) {
    fail(`Preview project name is ${previewName}, expected ${savedProjectName}`);
  }
  step("preview matches template.json");

  // --- Render: real UI path, stubbed native picker ------------------------
  await window.getByTestId("vizzy-templates-open").click();
  await panel.waitFor({ timeout: 10_000 });
  const renderRow = panel.getByTestId("vizzy-template-row").filter({ hasText: TEMPLATE_NAME });
  await renderRow.waitFor({ timeout: 10_000 });

  const wavPath = path.join(tempRoot, "run-tone.wav");
  writeWav(wavPath);
  const pickerStubbed = await app.evaluate(async ({ dialog }, audioPath) => {
    dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [audioPath] });
    return typeof dialog.showOpenDialog === "function";
  }, wavPath);
  if (!pickerStubbed) fail("Could not stub the native audio picker");

  await window.evaluate(() => {
    window.__vizzyRenderEvents = [];
    window.camxora.vizzy.onExportProgress((payload) => window.__vizzyRenderEvents.push(payload));
  });

  const renderStarted = Date.now();
  await renderRow.getByTestId("vizzy-template-render").click();
  await panel.getByTestId("vizzy-template-render-result").waitFor({ timeout: 600_000 });
  const renderMs = Date.now() - renderStarted;
  const renderResultText = await panel.getByTestId("vizzy-template-render-result").innerText();
  const events = await window.evaluate(() => window.__vizzyRenderEvents);
  const jobEvents = events.filter((event) => event.jobId && event.total > 0);
  const progressed = jobEvents.filter((event) => event.done > 0 && event.percent > 0);
  const monotonic = jobEvents.every(
    (event, index) => index === 0 || event.done >= jobEvents[index - 1].done,
  );
  step(`render finished in ${renderMs} ms`);

  const files = fs.readdirSync(rendersDir).filter((name) => name.endsWith(".mp4"));
  if (files.length !== 1) fail(`Expected one MP4, got ${JSON.stringify(files)}`);
  const renderName = files[0];
  if (!renderName.startsWith(`${templateId}-`)) {
    fail(`Render is not named after the template slug (${templateId}): ${renderName}`);
  }
  const renderPath = path.join(rendersDir, renderName);
  const bytes = fs.statSync(renderPath).size;
  if (bytes <= 0) fail("The render is empty");
  const probed = ffprobe(renderPath);
  if (probed.videoCodec !== "h264") fail(`Expected h264, got ${probed.videoCodec}`);
  if (probed.audioCodec !== "aac") fail(`Expected aac audio, got ${probed.audioCodec}`);
  if (probed.width !== 1920 || probed.height !== 1080) {
    fail(`Expected 1920×1080, got ${probed.width}×${probed.height}`);
  }
  if (!(probed.duration > 1.6 && probed.duration < 2.6)) {
    fail(`Expected ~2 s, ffprobe says ${probed.duration}`);
  }
  if (!(probed.frames >= 55 && probed.frames <= 66)) {
    fail(`Expected ~60 frames, ffprobe says ${probed.frames}`);
  }
  if (!renderResultText.includes(renderName)) {
    fail(`The Templates panel does not name the render: ${renderResultText}`);
  }
  if (jobEvents.length < 10) fail(`Expected streaming progress, got ${jobEvents.length}`);
  if (progressed.length < 3) fail(`Expected intermediate progress, got ${progressed.length}`);
  if (!monotonic) fail("Render progress went backwards");
  step("render probed");

  // --- Renders rail -------------------------------------------------------
  await window.getByTestId("vizzy-renders-open").click();
  await window.getByTestId("vizzy-renders-panel").waitFor({ timeout: 10_000 });
  const renderRow2 = window.getByTestId("vizzy-render-row").filter({ hasText: renderName });
  await renderRow2.waitFor({ timeout: 10_000 });
  await renderRow2.getByTestId("vizzy-render-play").click();
  const video = window.getByTestId("vizzy-render-video");
  await video.waitFor({ timeout: 10_000 });
  const videoSrc = await video.getAttribute("src");
  if (!videoSrc?.startsWith("camxora-media://")) {
    fail(`Inline playback did not use camxora-media://: ${videoSrc}`);
  }
  const playback = await poll(
    async () =>
      window.evaluate(() => {
        const element = document.querySelector('[data-testid="vizzy-render-video"]');
        return element instanceof HTMLVideoElement && element.readyState >= 1
          ? { readyState: element.readyState, duration: element.duration }
          : null;
      }),
    "the rendered video to load metadata",
    15_000,
  );
  await window.screenshot({ path: path.join(artifacts, "rendered-preview.png") });
  // The editor's own export dialog stays open after a successful run; close it
  // so the preview capture shows the rendered composition, not the dialog.
  await inView(`(() => {
    const button = Array.from(document.querySelectorAll(".modal button"))
      .find((node) => /^close$/i.test((node.textContent ?? "").trim()));
    if (button) button.click();
    return true;
  })()`);
  await window.waitForTimeout(500);
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
      path.join(artifacts, "rendered-editor.png"),
      Buffer.from(editorShot.split(",")[1], "base64"),
    );
  }
  step("renders rail verified");

  log({
    template: { id: templateId, dir: templateDir, pipeline, thumbnailBytes: thumbnail.byteLength },
    preview: { name: previewName, semanticEqual: true },
    render: {
      ms: renderMs,
      name: renderName,
      bytes,
      events: jobEvents.length,
      progressed: progressed.length,
      monotonic,
      resultText: renderResultText.replace(/\n+/g, " | "),
    },
    probe: probed,
    playback,
    artifacts,
  });
} finally {
  clearTimeout(watchdog);
  await app.close();
}
