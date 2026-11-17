#!/usr/bin/env node
/**
 * W3 capture script — the work list from docs/studio/reports/2026-11-17-capture-plan.md.
 *
 * Captures the 13 STATE screens (frames that show the wrong app state) and the 14
 * previously "cannot judge" screens at their reference viewports, writing PNGs into
 * docs/studio/compare/. Nothing here writes to the product API except the fixtures W3
 * already owns (a throwaway Studio project per screen, built through the documented
 * `/api/v3/web-music/studio/projects` endpoint).
 *
 * Usage (needs a dev server; this script never starts one):
 *   cd camxora.com
 *   npm ci && npx playwright install chromium      # once per worktree
 *   node scripts/capture-screens.mjs                # everything
 *   node scripts/capture-screens.mjs --only S28,S46 # a subset
 *   node scripts/capture-screens.mjs --only S43 --headed
 *   node scripts/capture-screens.mjs --list         # the work list, no browser
 *
 * Env:
 *   CAPTURE_BASE_URL      default http://localhost:3103
 *   STUDIO_SMOKE_EMAIL    default somvannda@gmail.com     (sandbox user)
 *   STUDIO_SMOKE_PASSWORD default StudioLocal!2026
 *
 * Failure policy: every structural expectation is hard. When a selector does not appear
 * the run prints `SELECTOR MISSING: <screen> — <selector> — <step>` plus the page URL,
 * writes docs/studio/reports/capture-failures/<screen>.png, and exits 1 with all
 * failures listed. Measured-only tags (library key/BPM, which are computed from audio and
 * may legitimately stay absent) are `soft` and are reported, not gated.
 *
 * This script never runs `npm run check:pixels`; re-run it after the captures exist.
 * See docs/studio/reports/2026-11-17-capture-plan.md for the PAIRING edits that go with it.
 */

import { existsSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = resolve(HERE, "..");
const REPO = resolve(APP, "..");
const COMPARE = join(REPO, "docs", "studio", "compare");
const FAILURES = join(REPO, "docs", "studio", "reports", "capture-failures");

const BASE = (process.env.CAPTURE_BASE_URL ?? "http://localhost:3103").replace(/\/$/, "");
const EMAIL = process.env.STUDIO_SMOKE_EMAIL ?? "somvannda@gmail.com";
const PASSWORD = process.env.STUDIO_SMOKE_PASSWORD ?? "StudioLocal!2026";

const args = process.argv.slice(2);
const flag = (name) => args.includes(`--${name}`);
const onlyArg = args.find((arg) => arg.startsWith("--only=")) ?? null;
const onlyIndex = args.indexOf("--only");
const only = new Set(
  (onlyArg ? onlyArg.split("=")[1] : onlyIndex >= 0 ? args[onlyIndex + 1] ?? "" : "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean)
);

// ------------------------------------------------------------------ helpers

class CaptureError extends Error {
  constructor(screen, step, message) {
    super(`SELECTOR MISSING: ${screen} — ${message} — ${step}`);
    this.screen = screen;
    this.step = step;
  }
}

const ROLE = (page, role, name, options = {}) => page.getByRole(role, { name, ...options });
const SEL = (page, selector) => page.locator(selector);

/** Hard expectation: wait for visible text/control; throw with the selector and step. */
async function must(screen, step, locator, describe, timeout = 30_000) {
  try {
    await locator.first().waitFor({ state: "visible", timeout });
  } catch {
    throw new CaptureError(screen, step, describe);
  }
}

/** Hard expectation: must not be present (used by the offline and idle states). */
async function mustNot(screen, step, locator, describe, timeout = 5_000) {
  try {
    await locator.first().waitFor({ state: "visible", timeout });
  } catch {
    return;
  }
  throw new CaptureError(screen, step, `${describe} (it is visible)`);
}

/** Soft expectation: report, never fail. */
async function soft(screen, step, locator, describe, timeout = 6_000) {
  try {
    await locator.first().waitFor({ state: "visible", timeout });
    return true;
  } catch {
    console.warn(`  · soft: ${screen} ${step} — ${describe} did not appear (reported, not gated)`);
    return false;
  }
}

/** Fresh browser context; Studio settings are pinned so previous runs cannot leak in. */
async function newContext(browser, viewport) {
  const context = await browser.newContext({
    baseURL: BASE,
    viewport,
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
    locale: "en-US",
    timezoneId: "UTC",
  });
  await context.addInitScript(() => {
    try {
      // What's This? on, but the first-run explainer already seen: the explainer card is
      // the additive the S15 report calls out, and it covers other captures.
      window.localStorage.setItem(
        "studio:settings",
        JSON.stringify({
          ghostDrag: true,
          whatsThis: true,
          inputDeviceId: null,
          countIn: false,
          windowMode: "toggle",
          autoStretch: true,
          advancedContent: false,
        })
      );
      window.localStorage.setItem("studio:help:seen", "1");
    } catch {
      /* storage disabled: defaults still enable What's This? */
    }
  });
  return context;
}

/** Park the page on this origin, then log in through the API (cookies land in the context). */
async function signIn(page) {
  await page.goto("/studio", { waitUntil: "domcontentloaded" });
  const result = await page.evaluate(
    async ({ email, password }) => {
      const response = await fetch("/api/v3/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      return { status: response.status, body: (await response.text()).slice(0, 300) };
    },
    { email: EMAIL, password: PASSWORD }
  );
  if (result.status !== 200) {
    throw new Error(`login failed: ${result.status} ${result.body}`);
  }
}

/**
 * Build a throwaway project through the documented API and open its editor.
 * `tracks[i].clips` are real lanes bucketed onto that track, so multi-track screens
 * (S43 sidechain routing) get the routing entries without any provider call.
 */
async function createProject(page, { title, tracks, open = true }) {
  await page.goto("/studio", { waitUntil: "domcontentloaded" });
  const projectId = await page.evaluate(
    async ({ title, tracks }) => {
      const lanes = [];
      const payloadTracks = tracks.map((track, index) => {
        const clipIds = (track.clips ?? []).map((clip) => clip.id);
        for (const clip of track.clips ?? []) {
          lanes.push({
            id: clip.id,
            title: clip.title ?? clip.id,
            start: clip.start ?? 0,
            duration: clip.duration ?? 4,
            volume: 1,
            pan: 0,
            ...(clip.audioUrl ? { audioUrl: clip.audioUrl } : {}),
            ...(clip.midi ? { midi: clip.midi } : {}),
          });
        }
        return {
          id: track.id ?? `track-${index + 1}`,
          name: track.name ?? `Track ${index + 1}`,
          color: track.color ?? ["#38bdf8", "#f472b6", "#f59e0b", "#34d399"][index % 4],
          index,
          volume: 80,
          pan: 0,
          muted: false,
          solo: false,
          hidden: false,
          groupId: null,
          chain: [],
          clipIds,
        };
      });
      const response = await fetch("/api/v3/web-music/studio/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          title,
          bpm: 120,
          time_signature: "4/4",
          data: { lanes, tracks: payloadTracks },
        }),
      });
      if (!response.ok) throw new Error(`create failed: ${response.status} ${(await response.text()).slice(0, 300)}`);
      const project = await response.json();
      return project.id;
    },
    { title, tracks }
  );
  if (open) await page.goto(`/studio/editor?project=${encodeURIComponent(projectId)}`);
  return projectId;
}

/** Route mocks. Every one of these is a provider call the screen would otherwise need. */
const mock = {
  quota: (page, quota) =>
    page.route("**/api/v3/web-music/quota", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          limit: 50,
          used: 50,
          remaining: 0,
          is_pro: false,
          credits_per_song: 10,
          credits_remaining: 999,
          has_subscription: false,
          can_download: true,
          ...quota,
        }),
      })
    ),

  generations: (page, items) =>
    page.route(/\/api\/v3\/web-music\/generations\?/, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items, total: items.length, limit: 20, offset: 0 }),
      })
    ),

  uploads: (page, items) =>
    page.route(/\/api\/v3\/web-music\/studio\/uploads\?/, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items }),
      })
    ),

  /** One queued generation that completes, so a take can be committed (S29). */
  takeGeneration: (page, { title = "Loop", takeTitle = "Loop take 2" } = {}) => {
    page.route("**/api/v3/web-music/generate", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ task_id: "take-gen", status: "queued", title, style: "pop" }),
      })
    );
    return page.route("**/api/v3/web-music/generations/take-gen", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "take-gen",
          title,
          style: "pop",
          status: "complete",
          clips: [
            {
              variant: "v1",
              title: takeTitle,
              audio_url: "/demo-loop.wav",
              download_url: "/demo-loop.wav",
              duration_seconds: 4,
            },
          ],
        }),
      })
    );
  },

  /** A refused generation, as the provider reports it (S60 / EXTRA-generation-refused). */
  refusal: (page, { code = "MODERATION_BLOCKED", message = "Blocked by the content policy.", status = 400 } = {}) =>
    page.route("**/api/v3/web-music/generate", (route) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify({ error: { code, message } }),
      })
    ),

  /** Hold the project GET so the loading state stays on screen (S57 / EXTRA-restoring). */
  slowProject: (page, projectId, delayMs = 8_000) =>
    page.route(`**/api/v3/web-music/studio/projects/${projectId}`, async (route) => {
      if (route.request().method() === "GET") {
        await new Promise((done) => setTimeout(done, delayMs));
      }
      return route.continue();
    }),

  /** Fail the project GET so the editor shows its load error (EXTRA-project-load-error). */
  brokenProject: (page, projectId) =>
    page.route(`**/api/v3/web-music/studio/projects/${projectId}`, (route) => {
      if (route.request().method() !== "GET") return route.continue();
      return route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ error: { code: "INTERNAL", message: "Project storage unavailable." } }),
      });
    }),
};

const library = (page) => ROLE(page, "complementary", "Library");

/** The Create form's Styles/Lyrics sections collapse; open the one carrying `fieldId`. */
async function ensureSection(page, fieldId, expandLabel) {
  if (await SEL(page, fieldId).first().isVisible().catch(() => false)) return;
  const expand = page.getByRole("button", { name: expandLabel });
  if (await expand.count()) await expand.first().click();
}

// ------------------------------------------------------------------ scenarios
//
// One function per screen. Each one leaves the page in the state the reference frame
// shows; expectations live in the table below so the "what must be visible" statement is
// next to the reference frame it is argued against.

const SCENARIOS = {
  /* S15 — "What's This?" hover card on the Tempo control. */
  async whatsThis(page, { screen }) {
    await createProject(page, {
      title: "Capture · What's This?",
      tracks: [{ id: "track-1", name: "Drums", clips: [{ id: "clip-1", title: "Loop" }] }],
    });
    await must(screen, "editor loaded", SEL(page, ".se-clip"), ".se-clip");
    const tempo = page.getByLabel("Tempo in BPM");
    await must(screen, "tempo control", tempo, 'input[aria-label="Tempo in BPM"]');
    await tempo.hover();
  },

  /* S25 — clip selected, master chain visible in the dock. */
  async clipSelected(page, { screen }) {
    await createProject(page, {
      title: "Capture · Clip selected",
      tracks: [
        {
          id: "track-1",
          name: "Drums",
          clips: [{ id: "clip-1", title: "Loop", audioUrl: "/demo-loop.wav" }],
        },
      ],
    });
    const clip = SEL(page, ".se-clip").first();
    await must(screen, "clip", clip, ".se-clip");
    await clip.click();
    await page.getByRole("button", { name: "Main", exact: true }).click();
  },

  /* S28 — clip menu with the Clip Color submenu expanded. */
  async clipColor(page, { screen }) {
    await createProject(page, {
      title: "Capture · Clip colour",
      tracks: [{ id: "track-1", name: "Drums", clips: [{ id: "clip-1", title: "Loop", audioUrl: "/demo-loop.wav" }] }],
    });
    const clip = SEL(page, ".se-clip").first();
    await must(screen, "clip", clip, ".se-clip");
    const box = await clip.boundingBox();
    if (!box) throw new CaptureError(screen, "right-click clip", ".se-clip has no bounding box");
    await page.mouse.click(box.x + 30, box.y + 40, { button: "right" });
    const menu = page.getByRole("menu", { name: "Clip options" });
    await must(screen, "clip menu", menu, 'role=menu[name="Clip options"]');
    await menu.getByRole("menuitem", { name: /Clip Color/ }).click();
  },

  /* S29 — two stacked takes, the newer one active (mocked generation, no provider). */
  async takeLanes(page, { screen }) {
    await mock.takeGeneration(page);
    await createProject(page, {
      title: "Capture · Take lanes",
      tracks: [
        {
          id: "track-1",
          name: "Drums",
          clips: [{ id: "base-clip", title: "Base Loop", audioUrl: "/demo-loop.wav" }],
        },
      ],
    });
    await must(screen, "clip", SEL(page, ".se-clip"), ".se-clip");
    await SEL(page, ".se-clip").first().click();
    await page.getByRole("button", { name: "Take lanes", exact: true }).click();
    await must(screen, "take band", page.getByRole("region", { name: "Take lanes" }), 'role=region[name="Take lanes"]');

    await page.getByLabel("Describe a part to generate").fill("A new drum loop over the clip");
    await page.getByRole("button", { name: "Generate this part" }).click();
    const assistant = page.getByRole("complementary", { name: "Studio assistant" });
    await must(screen, "generation result", assistant.getByText(/Created/), "assistant generation result");
    await assistant.locator(".se-assistant-take").first().getByRole("button", { name: "Commit" }).click();
    await must(screen, "second take", page.getByRole("button", { name: "Use take 2" }), 'role=button[name="Use take 2"]');
  },

  /* S34 — idle prompt bar: no menu, no attachment, no docked panel. */
  async promptIdle(page, { screen }) {
    await createProject(page, {
      title: "Capture · Prompt bar idle",
      tracks: [{ id: "track-1", name: "Drums", clips: [{ id: "clip-1", title: "Loop", audioUrl: "/demo-loop.wav" }] }],
    });
    await must(screen, "editor loaded", SEL(page, ".se-clip"), ".se-clip");
    await must(screen, "prompt bar", SEL(page, ".se-prompt"), ".se-prompt");
    await mustNot(screen, "no open menu", page.getByRole("menu"), "role=menu");
    await mustNot(screen, "no MIDI editor", page.getByRole("region", { name: "MIDI editor" }), 'role=region[name="MIDI editor"]');
  },

  /* S35 — a clip attached to the prompt bar (chip with the clip title). */
  async promptAttachment(page, { screen }) {
    await createProject(page, {
      title: "Capture · Prompt attachment",
      tracks: [
        {
          id: "track-1",
          name: "Drums",
          clips: [{ id: "clip-1", title: "Drum Kit Main", audioUrl: "/demo-loop.wav" }],
        },
      ],
    });
    await must(screen, "editor loaded", SEL(page, ".se-clip"), ".se-clip");
    await page.getByRole("button", { name: "Attach a track or clip" }).click();
    const attach = page.getByRole("menu", { name: "Attach to the prompt" });
    await must(screen, "attach menu", attach, 'role=menu[name="Attach to the prompt"]');
    await attach.getByRole("menuitem", { name: /Drum Kit Main/ }).click();
    await must(screen, "attachment chip", SEL(page, ".se-prompt-context"), ".se-prompt-context");
  },

  /* S40 — master chain with a single EQ slot. */
  async masterSingle(page, { screen }) {
    await createProject(page, {
      title: "Capture · Master chain one slot",
      tracks: [{ id: "track-1", name: "Drums", clips: [{ id: "clip-1", title: "Loop", audioUrl: "/demo-loop.wav" }] }],
    });
    await must(screen, "editor loaded", SEL(page, ".se-clip"), ".se-clip");
    await page.getByRole("button", { name: "Main", exact: true }).click();
    const master = page.getByRole("region", { name: "Master chain" });
    await must(screen, "master dock", master, 'role=region[name="Master chain"]');
    await master.getByRole("button", { name: "Add EQ" }).click();
  },

  /* S46 — Compressor preset menu open (stepper + Clear all settings / Save preset…). */
  async presetMenu(page, { screen }) {
    await createProject(page, {
      title: "Capture · Preset menu",
      tracks: [{ id: "track-1", name: "Drums", clips: [{ id: "clip-1", title: "Loop", audioUrl: "/demo-loop.wav" }] }],
    });
    await must(screen, "editor loaded", SEL(page, ".se-clip"), ".se-clip");
    await page.getByRole("button", { name: "Track 1", exact: true }).click();
    const dock = page.getByRole("region", { name: "Plugins for Track 1" });
    await must(screen, "plugin dock", dock, 'role=region[name="Plugins for Track 1"]');
    await dock.getByRole("button", { name: "Add effect", exact: true }).first().click();
    const catalog = page.getByRole("dialog", { name: "Add a track plugin" });
    await must(screen, "plugin catalog", catalog, 'role=dialog[name="Add a track plugin"]');
    await catalog.getByRole("button", { name: /^Compressor/ }).first().click();
    const slot = page.getByRole("article", { name: "Compressor slot 1" });
    await must(screen, "compressor slot", slot, 'role=article[name="Compressor slot 1"]');
    await slot.getByRole("button", { name: "Default" }).click();
    await must(screen, "preset menu", page.getByRole("menu", { name: "Compressor presets" }), 'role=menu[name="Compressor presets"]');
  },

  /* S43 — Compressor card with the sidechain routing list open (no reference frame yet). */
  async sidechain(page, { screen }) {
    await createProject(page, {
      title: "Capture · Compressor sidechain",
      tracks: [
        { id: "track-1", name: "Brass Section", clips: [{ id: "clip-1", title: "Loop", audioUrl: "/demo-loop.wav" }] },
        { id: "track-2", name: "Long Vocal" },
        { id: "track-3", name: "Bass Line" },
        { id: "track-4", name: "Bass Answer" },
      ],
    });
    await must(screen, "editor loaded", SEL(page, ".se-clip"), ".se-clip");
    await page.getByRole("button", { name: "Track 1", exact: true }).click();
    const dock = page.getByRole("region", { name: "Plugins for Track 1" });
    await must(screen, "plugin dock", dock, 'role=region[name="Plugins for Track 1"]');
    await dock.getByRole("button", { name: "Add effect", exact: true }).first().click();
    const catalog = page.getByRole("dialog", { name: "Add a track plugin" });
    await must(screen, "plugin catalog", catalog, 'role=dialog[name="Add a track plugin"]');
    await catalog.getByRole("button", { name: /^Compressor/ }).first().click();
    const slot = page.getByRole("article", { name: "Compressor slot 1" });
    await must(screen, "compressor slot", slot, 'role=article[name="Compressor slot 1"]');
    await slot.getByRole("button", { name: "Sidechain" }).click();
    await must(screen, "sidechain routing", page.getByRole("menu", { name: "Sidechain routing" }), 'role=menu[name="Sidechain routing"]');
  },

  /* S53 — Library ▸ All Songs with the model · key · BPM tag strip. */
  async librarySongs(page, { screen }) {
    const day = (offset) => new Date(Date.now() - offset * 86_400_000).toISOString();
    await mock.generations(page, [
      {
        id: "song-1",
        title: "Bassac Moon",
        style: "khmer pop, warm bass",
        model_label: "v6",
        status: "complete",
        created_at: day(0),
        clips: [{ variant: "ok", label: "cover", audio_url: "/demo-loop.wav", duration_seconds: 4 }],
      },
      {
        id: "song-2",
        title: "Neon Ferry",
        style: "synthwave, neon",
        model_label: "v6",
        status: "complete",
        created_at: day(1),
        clips: [{ variant: "ok", label: "extend", audio_url: "/demo-loop.wav", duration_seconds: 4 }],
      },
      {
        id: "song-3",
        title: "Rain Market",
        style: "lo-fi, field recording",
        model_label: "v5",
        status: "complete",
        created_at: day(3),
        clips: [{ variant: "ok", label: "cover", audio_url: "/demo-loop.wav", duration_seconds: 4 }],
      },
    ]);
    await createProject(page, {
      title: "Capture · Library songs",
      tracks: [{ id: "track-1", name: "Drums", clips: [{ id: "clip-1", title: "Loop" }] }],
    });
    await must(screen, "editor loaded", SEL(page, ".se-clip"), ".se-clip");
    await page.getByLabel("Toggle library").click();
    const panel = library(page);
    await must(screen, "library panel", panel, 'role=complementary[name="Library"]');
    await panel.getByRole("button", { name: /All Songs/ }).click();
    await must(screen, "song row", SEL(page, ".se-lib-song"), ".se-lib-song");
    // Key/BPM are measured from the audio, so they are reported rather than gated.
    await soft(screen, "tag strip", SEL(page, ".se-lib-tags"), ".se-lib-tags");
    await soft(screen, "bpm tag", page.getByText(/\d+ BPM/), "N BPM tag");
  },

  /* EXTRA-library-uploads — Uploads view resolved (rows, day groups). */
  async libraryUploads(page, { screen }) {
    const upload = (id, filename, minutes, daysAgo) => ({
      id,
      filename,
      content_type: "audio/wav",
      size_bytes: 176_444,
      duration_seconds: 214,
      url: "/demo-loop.wav",
      created_at: new Date(Date.now() - daysAgo * 86_400_000).toISOString(),
      minutes,
    });
    await mock.uploads(page, [
      upload("up-1", "field-recording-market.wav", 3.34, 0),
      upload("up-2", "room-tone-bassac.wav", 1.12, 1),
      upload("up-3", "vocal-idea-04.wav", 0.48, 4),
    ]);
    await createProject(page, {
      title: "Capture · Library uploads",
      tracks: [{ id: "track-1", name: "Drums", clips: [{ id: "clip-1", title: "Loop" }] }],
    });
    await must(screen, "editor loaded", SEL(page, ".se-clip"), ".se-clip");
    await page.getByLabel("Toggle library").click();
    const panel = library(page);
    await must(screen, "library panel", panel, 'role=complementary[name="Library"]');
    await panel.getByRole("button", { name: "Uploads", exact: true }).click();
    await must(screen, "upload row", SEL(page, ".se-lib-upload"), ".se-lib-upload");
    await must(screen, "day group", SEL(page, ".se-lib-day"), ".se-lib-day");
    await mustNot(screen, "list resolved", page.getByText("Loading uploads…"), '"Loading uploads…"');
  },

  /* EXTRA-library-song-detail — the read-only song rail. */
  async librarySongDetail(page, { screen }) {
    await mock.generations(page, [
      {
        id: "song-detail",
        title: "Bassac Moon",
        style: "khmer pop, warm bass",
        lyrics: "[Verse]\nRiver light on the ferry rail",
        model_label: "v6",
        status: "complete",
        created_at: new Date().toISOString(),
        clips: [
          {
            variant: "ok",
            label: "cover",
            audio_url: "/demo-loop.wav",
            duration_seconds: 4,
            image_url: "",
          },
        ],
      },
    ]);
    await createProject(page, {
      title: "Capture · Song detail",
      tracks: [{ id: "track-1", name: "Drums", clips: [{ id: "clip-1", title: "Loop" }] }],
    });
    await must(screen, "editor loaded", SEL(page, ".se-clip"), ".se-clip");
    await page.getByLabel("Toggle library").click();
    const panel = library(page);
    await must(screen, "library panel", panel, 'role=complementary[name="Library"]');
    await panel.getByRole("button", { name: /All Songs/ }).click();
    const row = SEL(page, ".se-lib-song").first();
    await must(screen, "song row", row, ".se-lib-song");
    await row.dblclick();
    await must(screen, "song detail rail", SEL(page, ".se-song-detail"), ".se-song-detail");
  },

  /* EXTRA-take-lanes-empty — the empty band, no help card over its right end. */
  async takeLanesEmpty(page, { screen }) {
    await createProject(page, {
      title: "Capture · Take lanes empty",
      tracks: [{ id: "track-1", name: "Drums", clips: [{ id: "clip-1", title: "Loop", audioUrl: "/demo-loop.wav" }] }],
    });
    await must(screen, "editor loaded", SEL(page, ".se-clip"), ".se-clip");
    await SEL(page, ".se-clip").first().click();
    await page.getByRole("button", { name: "Take lanes", exact: true }).click();
    await must(screen, "empty band", SEL(page, ".se-takes-empty"), ".se-takes-empty");
    await mustNot(screen, "no first-run card", SEL(page, ".se-help-first"), ".se-help-first");
  },

  /* S57 / EXTRA-restoring-last-project — the loading state, held by a slow GET. */
  async loadingState(page, { screen, row }) {
    const projectId = await createProject(page, {
      title: "Capture · Loading",
      tracks: [{ id: "track-1", name: "Drums", clips: [{ id: "clip-1", title: "Loop" }] }],
      open: false,
    });
    await mock.slowProject(page, projectId, 15_000);
    await page.goto(`/studio/editor?project=${encodeURIComponent(projectId)}`);
    await must(screen, "loading state", SEL(page, ".se-loading"), ".se-loading");
    row.projectId = projectId;
  },

  /* EXTRA-project-load-error — the editor's load-error surface. */
  async loadError(page, { screen }) {
    const projectId = await createProject(page, {
      title: "Capture · Load error",
      tracks: [{ id: "track-1", name: "Drums", clips: [{ id: "clip-1", title: "Loop" }] }],
      open: false,
    });
    await mock.brokenProject(page, projectId);
    await page.goto(`/studio/editor?project=${encodeURIComponent(projectId)}`);
    await must(screen, "load error", SEL(page, ".se-error"), ".se-error");
  },

  /* EXTRA-generation-refused / -legacy — a refused generation in the prompt bar. */
  async generationRefused(page, { screen }) {
    await mock.refusal(page);
    await createProject(page, {
      title: "Capture · Generation refused",
      tracks: [{ id: "track-1", name: "Drums", clips: [{ id: "clip-1", title: "Loop", audioUrl: "/demo-loop.wav" }] }],
    });
    await must(screen, "editor loaded", SEL(page, ".se-clip"), ".se-clip");
    await page.getByLabel("Describe a part to generate").fill("A refused loop");
    await page.getByRole("button", { name: "Generate this part" }).click();
    await must(screen, "refusal notice", SEL(page, ".se-assistant-notice"), ".se-assistant-notice");
  },

  /* S60 — Create ▸ a generation refused for policy reasons. */
  async moderation(page, { screen }) {
    await mock.quota(page, {});
    await mock.refusal(page, {
      code: "MODERATION_BLOCKED",
      message: "Your lyrics contain copyrighted material. Please change it and try again.",
    });
    await mock.generations(page, []);
    await page.goto("/create");
    // "Advanced" is the form mode the reference frame shows (mode=custom: style + lyrics).
    await page.getByRole("tab", { name: "Advanced", exact: true }).click();
    await ensureSection(page, "#create-style", "Expand styles");
    await must(screen, "create form", SEL(page, "#create-style"), "#create-style");
    await SEL(page, "#create-style").fill("khmer pop, warm bass");
    await ensureSection(page, "#create-lyrics", "Expand lyrics");
    await SEL(page, "#create-lyrics").fill("[Verse]\nA line that the policy will refuse");
    const title = page.getByPlaceholder("Song title");
    if (await title.count()) await title.first().fill("Refused song");
    await SEL(page, ".s-create-btn").first().click();
    await must(screen, "refusal", SEL(page, ".s-error"), ".s-error");
  },

  /* S61 — Create with no credits left. */
  async insufficientCredits(page, { screen }) {
    await mock.quota(page, { credits_remaining: 0, remaining: 0, daily_free_remaining: 0 });
    await mock.generations(page, []);
    await page.goto("/create");
    await page.getByRole("tab", { name: "Advanced", exact: true }).click();
    await ensureSection(page, "#create-style", "Expand styles");
    await must(screen, "create form", SEL(page, "#create-style"), "#create-style");
    await SEL(page, "#create-style").fill("khmer pop, warm bass");
    const title = page.getByPlaceholder("Song title");
    if (await title.count()) await title.first().fill("No credits");
  },

  /* S63 — 1280 px with the MIDI editor docked and the master chain selected. */
  async midiAt1280(page, { screen }) {
    await createProject(page, {
      title: "Capture · 1280 px",
      tracks: [{ id: "track-1", name: "Drums", clips: [{ id: "clip-1", title: "Loop", audioUrl: "/demo-loop.wav" }] }],
    });
    await must(screen, "editor loaded", SEL(page, ".se-clip"), ".se-clip");
    await page.getByRole("button", { name: /Add new track/ }).click();
    await page.getByRole("menuitem", { name: /MIDI/ }).click();
    await must(screen, "MIDI editor", page.getByRole("region", { name: "MIDI editor" }), 'role=region[name="MIDI editor"]');
    await page.getByRole("button", { name: "Main", exact: true }).click();
  },

  /* S01 — signed-out marketing page. */
  async marketingSignedOut(page, { screen }) {
    await page.goto("/studio");
    await must(screen, "marketing heading", page.getByRole("heading", { level: 1, name: /Camxora Studio/ }), "h1 Camxora Studio.");
  },

  /* S02 — the sign-in route (we ship a page, not the reference modal). */
  async signInPage(page, { screen }) {
    await page.goto("/login");
    await must(screen, "sign-in heading", page.getByRole("heading", { level: 1, name: "Welcome back." }), "h1 Welcome back.");
  },

  /* S56 — a share link opened with no cookies at all. */
  async sharedLoggedOut(page, state) {
    const { screen, browser, row } = state;
    await signIn(page);
    const projectId = await createProject(page, {
      title: "Capture · Shared link",
      tracks: [{ id: "track-1", name: "Drums", clips: [{ id: "clip-1", title: "Loop", audioUrl: "/demo-loop.wav" }] }],
      open: false,
    });
    const token = await page.evaluate(async (id) => {
      const response = await fetch(`/api/v3/web-music/studio/projects/${id}/shares`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ expires_days: 7, permission: "view" }),
      });
      if (!response.ok) throw new Error(`share failed: ${response.status}`);
      const body = await response.json();
      return body.token ?? "";
    }, projectId);
    if (!token) throw new CaptureError(screen, "share token", "POST /shares returned no token");

    const anon = await newContext(browser, row.viewport);
    const anonPage = await anon.newPage();
    await anonPage.goto(`/studio/shared/${token}`);
    await must(screen, "share page heading", anonPage.getByRole("heading", { name: "Capture · Shared link" }), "h_ Capture · Shared link");
    state.shootPage = anonPage;
    state.closeAfter = anon;
  },

  /* S62 — cold load while the browser is offline (the chrome error page is the state). */
  async offlineColdLoad(page, { screen }) {
    await page.context().setOffline(true);
    await page.goto("/studio").catch(() => undefined);
    await mustNot(screen, "no app shell", SEL(page, "header.se-head"), "header.se-head");
  },
};

// ------------------------------------------------------------------ work list
//
// One row per screen W3 must produce. `capture` is the file this run writes; `current`
// is what PAIRING.json points at today; `mode` says whether the pairing entry is replaced
// (the old file stays on disk as history) or added. Rows sharing one file declare the
// anchor in `sharedWith` — check:clone requires exactly one anchor per file.

const ROWS = [
  /* ---- 13 STATE frames: the paired capture shows the wrong app state ---- */
  {
    id: "S15",
    title: "What's This? card",
    frame: "S15-whats-this-card.jpeg",
    frameKind: "full",
    wrong: "No hover card in our frame; it shows the first-run explainer (an allowed additive).",
    state: "Tempo control hovered with What's This? on, card anchored under 120 BPM.",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1689, height: 1277 },
    expect: [
      { loc: (page) => page.getByRole("tooltip"), describe: 'role=tooltip (the .se-help-card)' },
      { loc: (page) => SEL(page, ".se-help-card"), describe: ".se-help-card" },
    ],
    mode: "replace",
    current: "ours-editor-1689.png",
    capture: "ours-whats-this.png",
    scenario: "whatsThis",
  },
  {
    id: "S25",
    title: "Clip selected / trim grips",
    frame: "S25-clip-selected.jpeg",
    frameKind: "full",
    wrong: "Dock is empty where the reference shows the master chain; clip bodies are stale (no waveform).",
    state: "Clip selected (outline + aria-pressed) with Main selected so the master chain fills the dock.",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1689, height: 1277 },
    expect: [
      { loc: (page) => SEL(page, '.se-clip[aria-pressed="true"]'), describe: '.se-clip[aria-pressed="true"]' },
      { loc: (page) => page.getByRole("region", { name: "Master chain" }), describe: 'role=region[name="Master chain"]' },
    ],
    mode: "replace",
    current: "ours-clip-selected.png",
    capture: "ours-clip-selected-master.png",
    scenario: "clipSelected",
  },
  {
    id: "S28",
    title: "Clip colour submenu",
    frame: "S28-clip-color-submenu.jpeg",
    frameKind: "crop",
    wrong: "The colour submenu is closed — only the parent row is hovered.",
    state: "Clip menu open with Clip Color expanded (Auto row + swatch grid).",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1689, height: 1277 },
    expect: [
      { loc: (page) => page.getByRole("menu", { name: "Clip options" }), describe: 'role=menu[name="Clip options"]' },
      { loc: (page) => page.getByRole("group", { name: "Clip colour" }), describe: 'role=group[name="Clip colour"]' },
      { loc: (page) => page.getByRole("button", { name: /Clip colour #/ }).first(), describe: "Clip colour swatches" },
    ],
    mode: "replace",
    current: "ours-clip-color.png",
    capture: "ours-clip-color-open.png",
    scenario: "clipColor",
  },
  {
    id: "S29",
    title: "Take lanes",
    frame: "S29-take-lanes.jpeg",
    frameKind: "full",
    wrong: "Our capture is the empty band (“Create a clip to see alternate takes here”), not numbered take rows.",
    state: "Two takes stacked under the clip, take 2 active (tick + aria-pressed).",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1689, height: 1277 },
    expect: [
      { loc: (page) => page.getByRole("region", { name: "Take lanes" }), describe: 'role=region[name="Take lanes"]' },
      { loc: (page) => page.getByRole("button", { name: "Use take 2" }), describe: 'role=button[name="Use take 2"]' },
      { loc: (page) => page.getByRole("button", { name: "Use take 1" }), describe: 'role=button[name="Use take 1"]' },
    ],
    mode: "replace",
    current: "ours-take-lanes.png",
    capture: "ours-take-lanes-populated.png",
    scenario: "takeLanes",
    alsoUnjudged: true,
  },
  {
    id: "S34",
    title: "Prompt bar idle",
    frame: "S34-magicbar-idle.jpeg",
    frameKind: "full",
    wrong: "Capture is cluttered: a track menu is open over the bar and the MIDI editor is docked.",
    state: "Idle editor: prompt bar with BETA badge, no menu open, no attachment chip.",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1689, height: 1277 },
    expect: [
      { loc: (page) => SEL(page, ".se-prompt"), describe: ".se-prompt" },
      { loc: (page) => page.getByLabel("Describe a part to generate"), describe: 'textarea[aria-label="Describe a part to generate"]' },
      { loc: (page) => page.getByRole("button", { name: "Generate this part" }), describe: 'role=button[name="Generate this part"]' },
    ],
    mode: "replace",
    current: "ours-magicbar.png",
    capture: "ours-magicbar-idle.png",
    scenario: "promptIdle",
  },
  {
    id: "S35",
    title: "Prompt bar attachment",
    frame: "S35-magicbar-attachment.jpeg",
    frameKind: "full",
    wrong: "Reused editor frame with no attachment chip; the attachment state is unevidenced.",
    state: "A clip attached to the prompt: chip with the clip title and an × control.",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1689, height: 1277 },
    expect: [
      { loc: (page) => SEL(page, ".se-prompt-context"), describe: ".se-prompt-context (attachment chip)" },
      { loc: (page) => page.getByRole("button", { name: "Clear track context" }), describe: 'role=button[name="Clear track context"]' },
    ],
    mode: "replace",
    current: "ours-prompt-attachment.png",
    capture: "ours-magicbar-attached.png",
    scenario: "promptAttachment",
  },
  {
    id: "S40",
    title: "Plugin dock · one slot",
    frame: "S40-plugin-dock-single.jpeg",
    frameKind: "full",
    wrong: "Our dock shows the selected track's chain with track-scoped footer chips; the reference dock is the master chain.",
    state: "Main selected, one EQ in the master chain, add-effect rail with ghost tiles.",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1689, height: 1277 },
    expect: [
      { loc: (page) => page.getByRole("region", { name: "Master chain" }), describe: 'role=region[name="Master chain"]' },
      { loc: (page) => page.getByRole("article", { name: "EQ slot" }), describe: 'role=article[name="EQ slot"]' },
      { loc: (page) => page.getByRole("button", { name: "Add Compressor" }), describe: 'role=button[name="Add Compressor"]' },
    ],
    mode: "replace",
    current: "ours-plugin-dock-eq-convolution.png",
    capture: "ours-plugin-dock-master-eq.png",
    scenario: "masterSingle",
  },
  {
    id: "S46",
    title: "Preset menu / stepper",
    frame: "S46-preset-menu.jpeg",
    frameKind: "crop",
    wrong: "The preset popover is closed; only the stepper is visible, so menu order/placement is unevidenced.",
    state: "Compressor card with its preset menu open (Clear all settings / Save preset… / Default / presets).",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1689, height: 1277 },
    expect: [
      { loc: (page) => page.getByRole("article", { name: "Compressor slot 1" }), describe: 'role=article[name="Compressor slot 1"]' },
      { loc: (page) => page.getByRole("menu", { name: "Compressor presets" }), describe: 'role=menu[name="Compressor presets"]' },
      {
        loc: (page) => page.getByRole("menu", { name: "Compressor presets" }).getByRole("menuitem", { name: "Clear all settings" }),
        describe: 'menuitem[name="Clear all settings"]',
      },
    ],
    mode: "replace",
    current: "ours-plugin-dock-eq-convolution.png",
    capture: "ours-plugin-preset-menu.png",
    scenario: "presetMenu",
  },
  {
    id: "S53",
    title: "Library songs",
    frame: "S53-library-songs.jpeg",
    frameKind: "full",
    wrong: "Capture predates the tag strip: “V6 PRO OK · 0:04” instead of model · key · BPM.",
    state: "Library ▸ All Songs with date groups and the model · key · BPM strip.",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1689, height: 1277 },
    expect: [
      { loc: (page) => page.getByRole("complementary", { name: "Library" }), describe: 'role=complementary[name="Library"]' },
      { loc: (page) => SEL(page, ".se-lib-song"), describe: ".se-lib-song rows" },
      { loc: (page) => SEL(page, ".se-lib-tags"), describe: ".se-lib-tags (model · key · BPM strip)" },
    ],
    mode: "replace",
    current: "ours-library-songs.png",
    capture: "ours-library-songs-tags.png",
    scenario: "librarySongs",
  },
  {
    id: "S56",
    title: "Shared link logged out",
    frame: "S56-shared-link-logged-out.jpeg",
    frameKind: "full",
    wrong: "Ours is stuck on “Loading project…”, AND the reference frame is the marketing hero — it contains no share surface at all.",
    state: "A no-cookie visitor opening /studio/shared/<token>: read-only heading, read-only timeline, “Sign in to fork”.",
    route: "/studio/shared/<token>",
    viewport: { width: 1920, height: 1211 },
    expect: [
      { loc: (page) => page.getByText("Read-only Studio share"), describe: "text Read-only Studio share" },
      { loc: (page) => page.getByLabel("Read-only project timeline"), describe: 'aria-label="Read-only project timeline"' },
      { loc: (page) => page.getByRole("link", { name: "Sign in to fork" }), describe: 'link[name="Sign in to fork"]' },
    ],
    mode: "replace",
    current: "ours-share-page-logged-out.png",
    capture: "ours-shared-link-readonly.png",
    scenario: "sharedLoggedOut",
  },
  {
    id: "S63",
    title: "1280 px",
    frame: "S63-1280px.jpeg",
    frameKind: "full",
    wrong: "Both fit at 1280, but the frames compare different bottom surfaces: the reference has a docked MIDI editor + master chips.",
    state: "1280×900, MIDI clip open in the docked editor, master chain selected.",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1280, height: 900 },
    expect: [
      { loc: (page) => page.getByRole("region", { name: "MIDI editor" }), describe: 'role=region[name="MIDI editor"]' },
      { loc: (page) => page.getByRole("region", { name: "Master chain" }), describe: 'role=region[name="Master chain"]' },
    ],
    mode: "replace",
    current: "ours-editor-1280-audit.png",
    capture: "ours-editor-1280-midi.png",
    scenario: "midiAt1280",
  },
  {
    id: "EXTRA-library-uploads",
    title: "Library uploads",
    frame: "EXTRA-library-uploads.jpeg",
    frameKind: "full",
    wrong: "Right surface, stuck on “Loading uploads…” — no row, tag or date group evidenced.",
    state: "Uploads view resolved: day headings and dated upload rows.",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1261, height: 1245 },
    expect: [
      { loc: (page) => SEL(page, ".se-lib-day"), describe: ".se-lib-day (date group)" },
      { loc: (page) => SEL(page, ".se-lib-upload"), describe: ".se-lib-upload rows" },
    ],
    mode: "replace",
    current: "ours-library-uploads.png",
    capture: "ours-library-uploads-resolved.png",
    scenario: "libraryUploads",
    alsoUnjudged: true,
  },
  {
    id: "EXTRA-take-lanes-empty",
    title: "Take lanes empty",
    frame: "EXTRA-take-lanes-empty.jpeg",
    frameKind: "full",
    wrong: "The first-run help card covers the band's right end, so the band cannot be judged.",
    state: "Empty take band with its captured copy, help card dismissed.",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1261, height: 1245 },
    expect: [
      { loc: (page) => SEL(page, ".se-takes-empty"), describe: ".se-takes-empty" },
      { loc: (page) => page.getByRole("region", { name: "Take lanes" }), describe: 'role=region[name="Take lanes"]' },
    ],
    mode: "replace",
    current: "ours-take-lanes-empty.png",
    capture: "ours-take-lanes-empty-clean.png",
    scenario: "takeLanesEmpty",
  },

  /* ---- 14 previously "cannot judge" screens without a paired capture ---- */
  {
    id: "S01",
    title: "Marketing signed out",
    frame: "S01-marketing-signed-out.jpeg",
    frameKind: "full",
    wrong: "No capture at all — the row was spec-only (behavioural).",
    state: "Signed-out /studio marketing page with product chrome.",
    route: "/studio",
    viewport: { width: 1116, height: 1245 },
    expect: [
      { loc: (page) => page.getByRole("heading", { level: 1, name: /Camxora Studio/ }), describe: "h1 Camxora Studio." },
    ],
    mode: "add",
    current: null,
    capture: "ours-marketing-signed-out.png",
    scenario: "marketingSignedOut",
  },
  {
    id: "S02",
    title: "Sign-in modal",
    frame: "S02-sign-in-modal.jpeg",
    frameKind: "full",
    wrong: "No capture at all; the reference is a modal over the marketing page, we ship a /login route (W0 decision still open).",
    state: "/login page: auth visual + “Welcome back.” card.",
    route: "/login",
    viewport: { width: 1250, height: 1245 },
    expect: [
      { loc: (page) => page.getByRole("heading", { level: 1, name: "Welcome back." }), describe: "h1 Welcome back." },
      { loc: (page) => page.getByLabel(/Email/i), describe: "email field" },
    ],
    mode: "add",
    current: null,
    capture: "ours-sign-in.png",
    scenario: "signInPage",
  },
  {
    id: "S43",
    title: "Compressor sidechain",
    frame: null,
    frameKind: "none",
    wrong:
      "Paired capture exists (ours-compressor-sidechain.png) but no filename starts with S43, so the harness cannot find a frame. The frame itself exists, misfiled as S46-compressor-routing-list.jpeg.",
    state: "Compressor card on a multi-track project with the Sidechain routing list open (each track twice: Pre-fx / Post-fader).",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1689, height: 1277 },
    expect: [
      { loc: (page) => page.getByRole("article", { name: "Compressor slot 1" }), describe: 'role=article[name="Compressor slot 1"]' },
      { loc: (page) => page.getByRole("menu", { name: "Sidechain routing" }), describe: 'role=menu[name="Sidechain routing"]' },
      { loc: (page) => page.getByRole("menuitem", { name: /Pre-fx/ }).first(), describe: "Pre-fx routing rows" },
      { loc: (page) => page.getByRole("menuitem", { name: /Post-fader/ }).first(), describe: "Post-fader routing rows" },
    ],
    mode: "add",
    current: "ours-compressor-sidechain.png",
    capture: "ours-compressor-sidechain-routing.png",
    scenario: "sidechain",
    blockedBy: "frame naming — see the plan §5 (rename the misfiled frame; do not invent one)",
  },
  {
    id: "S57",
    title: "Project loading blank",
    frame: "S57-project-loading-blank.jpeg",
    frameKind: "full",
    wrong: "No capture at all — spec-only. The reference frame is a blank canvas with no text.",
    state: "Editor holding the project-load state (slow GET), 1094×1245.",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1094, height: 1245 },
    expect: [{ loc: (page) => SEL(page, ".se-loading"), describe: ".se-loading" }],
    mode: "add",
    current: null,
    capture: "ours-project-loading-1094.png",
    scenario: "loadingState",
  },
  {
    id: "S60",
    title: "Moderation refusal",
    frame: "S60-moderation.jpeg",
    frameKind: "full",
    wrong: "No capture at all — spec-only (behavioural).",
    state: "Create ▸ Advanced submit refused by the content policy; the refusal is shown in the form.",
    route: "/create",
    viewport: { width: 1440, height: 900 },
    expect: [{ loc: (page) => SEL(page, ".s-error"), describe: ".s-error (form refusal)" }],
    mode: "add",
    current: null,
    capture: "ours-moderation-refusal.png",
    scenario: "moderation",
    note: "The reference shows an orange toast; our refusal renders inline in .s-error. Capture the reachable surface and record the copy/placement delta.",
  },
  {
    id: "S61",
    title: "Insufficient credits",
    frame: "S61-insufficient-credits.jpeg",
    frameKind: "full",
    wrong: "No capture at all; the reference has a “You're out of credits” modal + toast that our app does not ship.",
    state: "Create with a zero credit balance: the CTA is blocked and the warn note explains why.",
    route: "/create",
    viewport: { width: 1440, height: 900 },
    expect: [{ loc: (page) => SEL(page, ".s-note.warn"), describe: ".s-note.warn (not-enough-credits note)" }],
    mode: "add",
    current: null,
    capture: "ours-insufficient-credits.png",
    scenario: "insufficientCredits",
    note: "No modal exists (CreateStudio's creditsOpen state is unused). This frame is evidence for the W7 absence decision, not a layout claim.",
  },
  {
    id: "S62",
    title: "Offline cold load",
    frame: "S62-offline-cold-load.jpeg",
    frameKind: "full",
    wrong: "No capture at all — spec-only; the SCREENSHOT_INDEX records the reference as ERR_INTERNET_DISCONNECTED with no app shell.",
    state: "Browser offline, cold navigation to /studio: the network error page, no product chrome.",
    route: "/studio",
    viewport: { width: 1971, height: 1277 },
    expect: [],
    absent: [{ loc: (page) => SEL(page, "header.se-head"), describe: "header.se-head (no app shell offline)" }],
    mode: "add",
    current: null,
    capture: "ours-offline-cold-load.png",
    scenario: "offlineColdLoad",
  },
  {
    id: "EXTRA-generation-refused",
    title: "Generation refused (legacy copy)",
    frame: "EXTRA-generation-refused-legacy.jpeg",
    frameKind: "full",
    wrong: "No capture at all; there is also no exact frame — the only frame is the legacy crop.",
    state: "Prompt bar generation refused; the assistant notice explains the refusal.",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1250, height: 1245 },
    expect: [
      { loc: (page) => SEL(page, ".se-assistant-notice"), describe: ".se-assistant-notice" },
      { loc: (page) => page.getByText(/refused/i).first(), describe: "refusal copy" },
    ],
    mode: "add",
    current: null,
    capture: "ours-generation-refused.png",
    scenario: "generationRefused",
  },
  {
    id: "EXTRA-generation-refused-legacy",
    title: "Generation refused (legacy copy)",
    frame: "EXTRA-generation-refused-legacy.jpeg",
    frameKind: "full",
    wrong: "No capture at all.",
    state: "Same refusal state as EXTRA-generation-refused — one capture evidences both rows.",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1250, height: 1245 },
    expect: [],
    mode: "add",
    current: null,
    capture: "ours-generation-refused.png",
    scenario: "generationRefused",
    sharedWith: "EXTRA-generation-refused",
    skipRun: true,
  },
  {
    id: "EXTRA-library-song-detail",
    title: "Library song detail",
    frame: "EXTRA-library-song-detail.jpeg",
    frameKind: "full",
    wrong: "No capture at all; the evidence pointer is a component test, which is not a frame.",
    state: "Library ▸ All Songs ▸ a song opened in the read-only detail rail.",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1261, height: 1245 },
    expect: [
      { loc: (page) => page.getByRole("complementary", { name: "Song details" }), describe: 'role=complementary[name="Song details"]' },
      { loc: (page) => page.getByRole("tab", { name: /Info/ }), describe: 'role=tab[name="Info"]' },
    ],
    mode: "add",
    current: null,
    capture: "ours-library-song-detail.png",
    scenario: "librarySongDetail",
  },
  {
    id: "EXTRA-project-load-error",
    title: "Project load error",
    frame: "EXTRA-project-load-error.jpeg",
    frameKind: "full",
    wrong: "No capture at all.",
    state: "Editor after a failed project GET: the load-error alert.",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1689, height: 1277 },
    expect: [{ loc: (page) => SEL(page, ".se-error"), describe: ".se-error[role=alert]" }],
    mode: "add",
    current: null,
    capture: "ours-project-load-error.png",
    scenario: "loadError",
    note: "The reference offers Try again / Dismiss; our .se-error has neither. Record as a delta, not a state error.",
  },
  {
    id: "EXTRA-restoring-last-project",
    title: "Restoring last project",
    frame: "EXTRA-restoring-last-project.jpeg",
    frameKind: "full",
    wrong: "No capture at all.",
    state: "The state between reload and load: the editor holding its loading line at 1689×1277.",
    route: "/studio/editor?project=<seeded>",
    viewport: { width: 1689, height: 1277 },
    expect: [{ loc: (page) => SEL(page, ".se-loading"), describe: ".se-loading" }],
    mode: "add",
    current: null,
    capture: "ours-restoring-last-project.png",
    scenario: "loadingState",
    note: "Our copy is “Loading project…”, not “Restoring your last project…” — copy delta, same state.",
  },
];

// ------------------------------------------------------------------ runner

function selectedRows() {
  if (only.size === 0) return ROWS.filter((row) => !row.skipRun);
  const unknown = [...only].filter((id) => !ROWS.some((row) => row.id === id));
  if (unknown.length) {
    console.error(`unknown screen id(s): ${unknown.join(", ")}`);
    console.error(`known: ${ROWS.map((row) => row.id).join(", ")}`);
    process.exit(2);
  }
  // A subset still needs every file its rows share; run the anchor for shared captures.
  const ids = new Set(only);
  for (const row of ROWS) {
    if (row.sharedWith && ids.has(row.id)) ids.add(row.sharedWith);
  }
  return ROWS.filter((row) => ids.has(row.id) && !row.skipRun);
}

function printList() {
  console.log(`${ROWS.length} rows → ${new Set(ROWS.map((row) => row.capture)).size} capture files\n`);
  for (const row of ROWS) {
    const viewport = `${row.viewport.width}x${row.viewport.height}`;
    const frame = row.frame ? row.frame : "— (no frame)";
    console.log(
      `${row.id.padEnd(30)} ${viewport.padEnd(11)} ${row.frameKind.padEnd(5)} ${row.capture.padEnd(38)} ${frame}`
    );
  }
}

async function main() {
  if (flag("list")) {
    printList();
    return;
  }

  // Validate the selection before touching Playwright so a typo reports as a typo.
  const rows = selectedRows();
  if (rows.length === 0) {
    console.error("nothing selected");
    process.exit(2);
  }

  if (!existsSync(COMPARE)) mkdirSync(COMPARE, { recursive: true });
  if (!existsSync(FAILURES)) mkdirSync(FAILURES, { recursive: true });

  let chromium;
  try {
    ({ chromium } = await import("@playwright/test"));
  } catch {
    console.error("Playwright is not installed. Run: cd camxora.com && npm ci && npx playwright install chromium");
    process.exit(2);
  }


  const browser = await chromium.launch({ headless: !flag("headed") });
  const failures = [];
  const written = [];

  for (const row of rows) {
    const label = `${row.id} (${row.viewport.width}x${row.viewport.height})`;
    process.stdout.write(`… ${label} ${row.capture}\n`);
    const context = await newContext(browser, row.viewport);
    const page = await context.newPage();
    const started = Date.now();
    try {
      if (!["marketingSignedOut", "signInPage", "offlineColdLoad"].includes(row.scenario)) {
        await signIn(page);
      }
      const state = { screen: row.id, row, context, browser };
      await SCENARIOS[row.scenario](page, state);

      const shootPage = state.shootPage ?? page;
      for (const check of row.expect ?? []) {
        await must(row.id, row.scenario, check.loc(shootPage), check.describe);
      }
      for (const check of row.absent ?? []) {
        await mustNot(row.id, row.scenario, check.loc(shootPage), check.describe);
      }

      // Let fonts, decoded waveforms and layout settle before the frame is taken.
      await shootPage.evaluate(() => (document.fonts ? document.fonts.ready : null)).catch(() => undefined);
      await shootPage.waitForTimeout(400);
      await shootPage.screenshot({ path: join(COMPARE, row.capture), animations: "disabled" });

      written.push(row.capture);
      console.log(`  ✓ ${row.id} → docs/studio/compare/${row.capture} (${Math.round((Date.now() - started) / 1000)}s)`);
      if (state.closeAfter) await state.closeAfter.close();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      failures.push(`${row.id}: ${message}\n    url ${page.url()}`);
      try {
        await page.screenshot({ path: join(FAILURES, `${row.id.replace(/[^\w.-]+/g, "-")}.png`) });
      } catch {
        /* the page may be gone; the log is the evidence */
      }
      console.error(`  ✗ ${row.id}: ${message}`);
    } finally {
      await context.close().catch(() => undefined);
    }
  }

  await browser.close();

  const files = [...new Set(written)];
  console.log("");
  console.log(
    `capture-screens — ${rows.length} row(s), ${files.length} file(s) written into docs/studio/compare`
  );
  if (failures.length) {
    console.error("");
    console.error(`FAIL — ${failures.length} capture(s):`);
    for (const failure of failures) console.error(`  ${failure}`);
    console.error("");
    console.error("Fix the selector or the fixture, then re-run with --only <id>. Do not hand-edit a capture.");
    process.exit(1);
  }
  console.log("");
  console.log("Next: apply the PAIRING.json edits from docs/studio/reports/2026-11-17-capture-plan.md §6,");
  console.log("then run `npm run check:clone` and `npm run check:pixels`.");
}

await main();
