import { expect, type Locator, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

/**
 * W5-C independent manual-run harness (area C: every menu, dialog, settings pane,
 * home, share page and onboarding).
 *
 * Fixtures are created through the sandbox API from inside the page, so the rows assert
 * the running product rather than a hand-made database. One verdict row is written per
 * checklist id to docs/studio/reports/evidence-w5c/results-c.json.
 */

export const EMAIL = process.env.STUDIO_SMOKE_EMAIL ?? "somvannda@gmail.com";
export const PASSWORD = process.env.STUDIO_SMOKE_PASSWORD ?? "StudioLocal!2026";

const ROOT = process.cwd();
export const EVIDENCE_DIR = path.join(ROOT, "..", "docs", "studio", "reports", "evidence-w5c");

export type Verdict = "PASS" | "FAIL" | "N/A" | "BLOCKED";
export type Row = { id: string; verdict: Verdict; evidence: string; detail?: string };

export function makeRecorder(area: string) {
  const rows: Row[] = [];
  return {
    rows,
    record(id: string, verdict: Verdict, evidence: string, detail?: string) {
      rows.push({ id, verdict, evidence, detail });
      console.log(`${verdict.padEnd(7)} ${id}  ${evidence}`);
    },
    flush() {
      fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
      const file = path.join(EVIDENCE_DIR, `results-${area}.json`);
      let existing: Row[] = [];
      try {
        existing = JSON.parse(fs.readFileSync(file, "utf8")) as Row[];
      } catch {
        existing = [];
      }
      const merged = new Map(existing.map((row) => [row.id, row]));
      for (const row of rows) merged.set(row.id, row);
      fs.writeFileSync(file, JSON.stringify([...merged.values()], null, 2), "utf8");
    },
  };
}

export async function shot(page: Page, name: string): Promise<string> {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
  const file = path.join(EVIDENCE_DIR, `${name}.png`);
  await page.screenshot({ path: file }).catch(() => undefined);
  return path.basename(file);
}

/** Run one checklist row: record PASS with its measured evidence, FAIL with the cause. */
export async function check(
  rec: ReturnType<typeof makeRecorder>,
  page: Page,
  id: string,
  fn: () => Promise<string | void>,
  opts: { shotOnFail?: boolean } = {}
) {
  try {
    const evidence = (await fn()) || "verified";
    rec.record(id, "PASS", String(evidence));
  } catch (cause) {
    const message = cause instanceof Error ? cause.message : String(cause);
    let file = "";
    if (opts.shotOnFail !== false) file = await shot(page, id);
    console.log(`  ↳ ${id} FAILED: ${message.split("\n").slice(0, 6).join(" | ")}`);
    rec.record(id, "FAIL", file ? `see ${file}` : "", message.split("\n").slice(0, 4).join(" "));
  }
}

export function notes(rec: ReturnType<typeof makeRecorder>, id: string, evidence: string) {
  rec.record(id, "PASS", evidence);
}

// ---------------------------------------------------------------- auth and fixtures

export async function signIn(page: Page) {
  await page.goto("/studio", { waitUntil: "domcontentloaded" });
  const status = await page.evaluate(
    async ({ email, password }) => {
      const login = await fetch("/api/v3/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      return login.status;
    },
    { email: EMAIL, password: PASSWORD }
  );
  if (status !== 200) throw new Error(`login failed: ${status}`);
}

export async function api<T = unknown>(
  page: Page,
  pathname: string,
  init: { method?: string; body?: unknown } = {}
): Promise<T> {
  return (await page.evaluate(
    async ({ pathname: p, method, body }) => {
      const response = await fetch(p, {
        method: method ?? "GET",
        credentials: "include",
        headers: body === undefined ? undefined : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const text = await response.text();
      let parsed: unknown = null;
      try {
        parsed = text ? JSON.parse(text) : null;
      } catch {
        parsed = text;
      }
      if (!response.ok) {
        throw new Error(`${method ?? "GET"} ${p} -> ${response.status}: ${text.slice(0, 240)}`);
      }
      return parsed;
    },
    { pathname, method: init.method, body: init.body }
  )) as T;
}

const DEFAULTS: Record<string, Record<string, number>> = {
  compressor: { threshold: -18, ratio: 4, knee: 6, attack: 10, release: 120, gain: 0 },
  reverb: {
    time: 2.4,
    mix: 25,
    width: 100,
    damping: 40,
    predelay: 20,
    lowCut: 120,
    highCut: 14000,
  },
};

function entry(pluginId: string, entryId: string, extra: Record<string, unknown> = {}) {
  return {
    entryId,
    pluginId,
    presetId: null,
    presetName: "Default",
    dirty: false,
    params: { ...(DEFAULTS[pluginId] ?? {}) },
    assetId: null,
    bypassed: false,
    poppedOut: false,
    ...extra,
  };
}

/** P1: 120 BPM 4/4, Drums (two song clips), Bass (MIDI), Vox (upload), Scratch (hidden+muted). */
export function p1Document() {
  const midiNotes = Array.from({ length: 8 }, (_, index) => ({
    id: `n-${index}`,
    pitch: 36 + index,
    start: (index % 4) * 0.5,
    length: 0.5,
    velocity: 100,
  }));
  return {
    bpm: 120,
    time_signature: "4/4",
    data: {
      tracks: [
        {
          id: "t-drums",
          name: "Drums",
          color: "#38bdf8",
          index: 0,
          volume: 80,
          pan: 0,
          muted: false,
          solo: false,
          hidden: false,
          groupId: null,
          chain: [],
          clipIds: ["c-d1", "c-d2"],
          sends: { delay: 0, reverb: 0 },
        },
        {
          id: "t-bass",
          name: "Bass",
          color: "#a78bfa",
          index: 1,
          volume: 78,
          pan: 0,
          muted: false,
          solo: false,
          hidden: false,
          groupId: null,
          chain: [],
          clipIds: ["c-bass"],
          sends: { delay: 0, reverb: 0 },
        },
        {
          id: "t-vox",
          name: "Vox",
          color: "#f472b6",
          index: 2,
          volume: 82,
          pan: 0,
          muted: false,
          solo: false,
          hidden: false,
          groupId: null,
          chain: [],
          clipIds: ["c-vox"],
          sends: { delay: 0, reverb: 0 },
        },
        {
          id: "t-scratch",
          name: "Scratch",
          color: "#fbbf24",
          index: 3,
          volume: 70,
          pan: 0,
          muted: true,
          solo: false,
          hidden: true,
          groupId: null,
          chain: [],
          clipIds: ["c-scratch"],
          sends: { delay: 0, reverb: 0 },
        },
      ],
      lanes: [
        {
          id: "c-d1",
          trackId: "t-drums",
          title: "Drums A",
          start: 0,
          duration: 4,
          audioUrl: "/seed/demo-loop.wav",
          songId: "song-w5c-1",
        },
        {
          id: "c-d2",
          trackId: "t-drums",
          title: "Drums B",
          start: 8,
          duration: 4,
          audioUrl: "/seed/demo-loop.wav",
          songId: "song-w5c-1",
        },
        {
          id: "c-bass",
          trackId: "t-bass",
          title: "Bass",
          start: 0,
          duration: 8,
          midi: { notes: midiNotes, bend: [], mod: [] },
        },
        {
          id: "c-vox",
          trackId: "t-vox",
          title: "Vox",
          start: 4,
          duration: 4,
          audioUrl: "/seed/demo-loop.wav",
          fadeIn: 0.5,
          fadeOut: 0.75,
          audio: { volume: 0.8 },
        },
        {
          id: "c-scratch",
          trackId: "t-scratch",
          title: "Scratch",
          start: 0,
          duration: 2,
          audioUrl: "/seed/transients.wav",
        },
      ],
      chains: {
        "t-drums": [entry("compressor", "e-comp"), entry("reverb", "e-rev")],
      },
      pluginPresets: [],
      masterChain: [
        {
          id: "master-limiter",
          type: "limiter",
          enabled: true,
          params: { lookahead: 3, preGain: 0, attack: 1, release: 60, link: 1 },
        },
      ],
    },
  };
}

export function p2Document() {
  const doc = p1Document();
  const clip = doc.data.lanes[0] as Record<string, unknown>;
  clip.sourceAudioUrl = "/seed/transients.wav";
  clip.sourceDuration = 4;
  clip.takes = [
    { id: "take-1", title: "Original", audioUrl: "/seed/demo-loop.wav", active: false },
    { id: "take-2", title: "Extended", audioUrl: "/seed/demo-loop.wav", active: true },
  ];
  return doc;
}

/** P0: no tracks at all (onboarding + empty-state surfaces). */
export function emptyDocument() {
  return {
    bpm: 120,
    time_signature: "4/4",
    data: { tracks: [], lanes: [], chains: {}, pluginPresets: [], masterChain: [] },
  };
}

/** P5: P1 plus a fifth, clip-less track (Bounce track disabled row). */
export function clipLessTrackDocument() {
  const doc = p1Document();
  (doc.data.tracks as Array<Record<string, unknown>>).push({
    id: "t-empty",
    name: "Empty",
    color: "#4ade80",
    index: 4,
    volume: 80,
    pan: 0,
    muted: false,
    solo: false,
    hidden: false,
    groupId: null,
    chain: [],
    clipIds: [],
    sends: { delay: 0, reverb: 0 },
  });
  return doc;
}

export async function createProject(
  page: Page,
  title: string,
  doc: { bpm: number; time_signature: string; data: unknown }
): Promise<string> {
  const created = await api<{ id: string }>(page, "/api/v3/web-music/studio/projects", {
    method: "POST",
    body: { title, ...doc },
  });
  return created.id;
}

export async function deleteProject(page: Page, id: string) {
  await api(page, `/api/v3/web-music/studio/projects/${id}`, { method: "DELETE" });
}

export async function getProject(page: Page, id: string) {
  return api<{ id: string; title: string; bpm: number; time_signature: string; data: unknown }>(
    page,
    `/api/v3/web-music/studio/projects/${id}`
  );
}

export async function createVersion(page: Page, id: string, label: string) {
  return api(page, `/api/v3/web-music/studio/projects/${id}/versions`, {
    method: "POST",
    body: { label },
  });
}

export async function createShare(page: Page, id: string) {
  return api<{ token: string; path: string }>(
    page,
    `/api/v3/web-music/studio/projects/${id}/shares`,
    { method: "POST", body: { expires_days: 7, permission: "view" } }
  );
}

// ---------------------------------------------------------------- page helpers

export async function dismissOverlays(page: Page) {
  const alert = page.locator(".se-conflict[role='alert']");
  if (await alert.count()) {
    const discard = alert.locator("button", { hasText: "Discard" }).first();
    if (await discard.count()) {
      await discard.click({ timeout: 5000 }).catch(() => undefined);
      await page.waitForTimeout(200);
    }
  }
}

export async function quietStorage(page: Page) {
  await page.addInitScript(() => {
    try {
      const raw = window.localStorage.getItem("studio:settings");
      const parsed = raw ? JSON.parse(raw) : {};
      window.localStorage.setItem(
        "studio:settings",
        JSON.stringify({ ...parsed, whatsThis: false })
      );
    } catch {
      /* storage unavailable */
    }
  });
}

export async function dismissOnboarding(page: Page, timeout = 2500) {
  // The overlay only exists for a project with no tracks: skip the wait on real fixtures.
  if ((await page.locator(".se-track").count()) > 0) return false;
  const backdrop = page.locator(".se-onboard-backdrop").first();
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (await backdrop.count()) {
      const start = backdrop.locator("button", { hasText: "Start empty" }).first();
      if (await start.count()) await start.click({ timeout: 5000 }).catch(() => undefined);
      else
        await backdrop
          .locator('button[aria-label="Close"]')
          .first()
          .click({ timeout: 5000 })
          .catch(() => undefined);
      await page.waitForTimeout(200);
      return true;
    }
    await page.waitForTimeout(150);
  }
  return false;
}

export async function openEditor(page: Page, projectId: string, opts: { onboarding?: boolean } = {}) {
  await page.setDefaultTimeout(15_000);
  await page.setDefaultNavigationTimeout(45_000);
  await page.goto(`/studio/editor?project=${projectId}`);
  await dismissOverlays(page);
  await expect(page.locator(".se-shell, .se-gate, .se-error").first()).toBeVisible({
    timeout: 40_000,
  });
  await expect(page.locator(".se-loading")).toHaveCount(0, { timeout: 40_000 });
  // The shell paints before getStudioProject resolves; the chip still reads the default
  // title for a moment. Settle so menus act on the loaded project (W5C C-29/C-39).
  await page.waitForTimeout(800);
  await dismissOverlays(page);
  if (!opts.onboarding) await dismissOnboarding(page);
}

export function menu(page: Page, label: string): Locator {
  return page.locator(`[role="menu"][aria-label="${label}"]`).first();
}

export function dialog(page: Page, label: string): Locator {
  return page.locator(`[role="dialog"][aria-label="${label}"]`).first();
}

export async function menuRowTexts(scope: Locator): Promise<string[]> {
  return (await scope.locator('[role="menuitem"], [role="menuitemcheckbox"], [role="menuitemradio"]')
    .allInnerTexts()).map((text) => text.replace(/\s+/g, " ").trim());
}

export function rowByText(scope: Locator, text: string): Locator {
  return scope
    .locator('[role="menuitem"], [role="menuitemcheckbox"], [role="menuitemradio"]')
    .filter({ hasText: text })
    .first();
}

export async function openProjectMenu(page: Page) {
  const open = page.locator('.se-project-menu[role="menu"][aria-label="Project options"]');
  if ((await open.count()) > 0) {
    await page.keyboard.press("Escape");
    await expect(open).toHaveCount(0, { timeout: 5000 });
  }
  await page.locator(".se-chip").first().click();
  await expect(menu(page, "Project options")).toBeVisible({ timeout: 10_000 });
  await page.waitForTimeout(150);
  return menu(page, "Project options");
}

export async function closeMenus(page: Page) {
  await page.keyboard.press("Escape");
  await page.waitForTimeout(120);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(120);
}

/** Clear any dialog/popover a failed row left behind (used at the start of a block). */
export async function closeDialogs(page: Page) {
  for (let index = 0; index < 3; index += 1) {
    const stray = page.locator(".se-dialog-backdrop, .studio-dialog-backdrop");
    if ((await stray.count()) === 0) return;
    await page.keyboard.press("Escape");
    await page.waitForTimeout(200);
    if ((await stray.count()) === 0) return;
    // Several dialogs have no Escape handler; Cancel is their documented close action.
    const cancel = stray.first().locator("button", { hasText: /^(Cancel|Close|Done|Keep project)$/ });
    if ((await cancel.count()) > 0) {
      await cancel.first().click({ timeout: 5000 }).catch(() => undefined);
      await page.waitForTimeout(200);
    }
  }
}

/** Right-click a clip by its title; `nth` picks among same-titled clips. */
export async function openClipMenu(page: Page, title: string, opts: { nth?: number } = {}) {
  const clip = page.locator(".se-clip", { hasText: title }).nth(opts.nth ?? 0);
  await clip.click({ button: "right" });
  await expect(menu(page, "Clip options")).toBeVisible({ timeout: 10_000 });
  return menu(page, "Clip options");
}

export async function openTrackMenu(page: Page, track: string) {
  await page.locator(`button[aria-label="Options for ${track}"]`).first().click();
  await expect(menu(page, `${track} options`)).toBeVisible({ timeout: 10_000 });
  return menu(page, `${track} options`);
}

export async function setPlayhead(page: Page, fractionOfBar = 0.5, barIndex = 0) {
  const ruler = page.locator(".se-ruler-bars").first();
  const box = await ruler.boundingBox();
  if (!box) throw new Error("ruler not visible");
  // 4 bars are on screen at the default zoom; the first bar starts at x=0 of the inner.
  await page.mouse.click(box.x + box.width * 0.05 + 96 * (barIndex + fractionOfBar), box.y + box.height / 2);
  await page.waitForTimeout(150);
}

export async function makeRange(page: Page, fromBar = 1, toBar = 2) {
  const ruler = page.locator(".se-ruler-bars").first();
  const box = await ruler.boundingBox();
  if (!box) throw new Error("ruler not visible");
  const y = box.y + box.height / 2;
  await page.mouse.move(box.x + 96 * fromBar, y);
  await page.mouse.down();
  await page.mouse.move(box.x + 96 * toBar, y, { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(200);
}

export async function toastText(page: Page): Promise<string> {
  const toast = page.locator(".se-toast").first();
  await expect(toast).toBeVisible({ timeout: 10_000 });
  return (await toast.innerText()).replace(/\s+/g, " ").trim();
}

export async function clearToast(page: Page) {
  const dismiss = page.locator('.se-toast button[aria-label="Dismiss export message"]').first();
  if (await dismiss.count()) await dismiss.click().catch(() => undefined);
  await page.waitForTimeout(100);
}
