import { expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

/**
 * W5 independent manual-run harness (area B + area E).
 *
 * Builds the checklist fixtures through the sandbox API from inside the page, then
 * records one verdict row per checklist id. Rows are written to
 * docs/studio/reports/evidence-w5/results-<area>.json so the report can be generated
 * from measured values rather than memory.
 */

export const EMAIL = process.env.STUDIO_SMOKE_EMAIL ?? "somvannda@gmail.com";
export const PASSWORD = process.env.STUDIO_SMOKE_PASSWORD ?? "StudioLocal!2026";

const ROOT = process.cwd();
export const EVIDENCE_DIR = path.join(ROOT, "..", "docs", "studio", "reports", "evidence-w5");

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
    fail(id: string, message: string, evidence: string) {
      rows.push({ id, verdict: "FAIL", evidence, detail: message });
      console.log(`FAIL    ${id}  ${evidence} :: ${message}`);
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

export async function shot(page: Page, name: string) {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
  const file = path.join(EVIDENCE_DIR, `${name}.png`);
  await page.screenshot({ path: file });
  return path.basename(file);
}

/** Capture a frame only after the editor (or the gate) has actually painted. */
export async function captureEditor(page: Page, name: string) {
  if (await page.locator(".se-desktop-gate").isVisible()) {
    await page.waitForTimeout(400);
  } else {
    await page.locator(".se-clip").first().waitFor({ state: "visible", timeout: 20_000 });
    await page.waitForTimeout(700);
  }
  return shot(page, name);
}

export async function signIn(page: Page) {
  await page.goto("/studio");
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

/** Turn the hover help off so its card cannot sit over a control under test. */
export async function quietHelp(page: Page) {
  await page.addInitScript(() => {
    try {
      const raw = window.localStorage.getItem("studio:settings");
      const parsed = raw ? JSON.parse(raw) : {};
      window.localStorage.setItem(
        "studio:settings",
        JSON.stringify({ ...parsed, whatsThis: false })
      );
      for (const key of Object.keys(window.localStorage)) {
        if (key.startsWith("studio:draft:")) window.localStorage.removeItem(key);
      }
    } catch {
      /* storage unavailable */
    }
  });
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
  delay: { time: 350, feedback: 35, mix: 25, lowCut: 120, highCut: 12000 },
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
          songId: "song-w5-1",
        },
        {
          id: "c-d2",
          trackId: "t-drums",
          title: "Drums B",
          start: 8,
          duration: 4,
          audioUrl: "/seed/demo-loop.wav",
          songId: "song-w5-1",
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
  clip.title = "Drums A";
  clip.sourceAudioUrl = "/seed/transients.wav";
  clip.sourceDuration = 4;
  clip.takes = [
    { id: "take-1", title: "Original", audioUrl: "/seed/demo-loop.wav", active: false },
    { id: "take-2", title: "Extended", audioUrl: "/seed/demo-loop.wav", active: true },
  ];
  return doc;
}

export async function createProject(
  page: Page,
  title: string,
  doc: { bpm: number; time_signature: string; data: unknown }
): Promise<string> {
  await dismissOverlays(page);
  const id = await page.evaluate(
    async ({ email, password, projectTitle, document }) => {
      const login = await fetch("/api/v3/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      if (login.status !== 200) throw new Error(`login failed: ${login.status}`);
      const created = await fetch("/api/v3/web-music/studio/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: projectTitle, ...document }),
      });
      if (!created.ok) throw new Error(`create failed: ${created.status}`);
      return ((await created.json()) as { id: string }).id;
    },
    { email: EMAIL, password: PASSWORD, projectTitle: title, document: doc }
  );
  return id;
}

/** A leftover draft alert covers the editor until it is dismissed. */
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

export async function openProject(page: Page, projectId: string) {
  await page.goto(`/studio/editor?project=${projectId}`);
  await dismissOverlays(page);
  await expect(page.locator(".se-track").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  await dismissOverlays(page);
}

/** Open a project when the viewport may be below the 767px desktop gate. */
export async function openProjectAllowGate(page: Page, projectId: string) {
  await page.goto(`/studio/editor?project=${projectId}`);
  await dismissOverlays(page);
  await expect(page.locator(".se-shell, .se-desktop-gate").first()).toBeVisible({
    timeout: 30_000,
  });
}

/** Select a track by name and make sure the plugin dock is visible. */
export async function selectTrack(page: Page, name: string) {
  await dismissOverlays(page);
  await page.locator(".se-track-name", { hasText: name }).first().click();
  if ((await page.locator("section.sp-dock").count()) === 0) {
    await page.keyboard.press("2");
  }
  await expect(page.locator("section.sp-dock")).toBeVisible({ timeout: 15_000 });
}

export async function openDock(page: Page, name = "Drums") {
  await selectTrack(page, name);
  await expect(page.locator("article.sp-slot").first()).toBeVisible({ timeout: 15_000 });
}

export function slot(page: Page, name: string) {
  return page.locator(`article.sp-slot[aria-label^="${name} slot"]`).first();
}

export function knob(page: Page, slotName: string, label: string) {
  return slot(page, slotName).locator(`input[aria-label="${label}"]`).first();
}

export async function readout(page: Page, slotName: string, label: string) {
  return (await knob(page, slotName, label).getAttribute("aria-valuetext")) ?? "";
}

export async function readAll(page: Page, slotName: string, labels: string[]) {
  const out: Record<string, string> = {};
  for (const label of labels) out[label] = await readout(page, slotName, label);
  return out;
}

/** Set a range knob through the native value setter + input/change events. */
export async function setKnob(
  page: Page,
  slotName: string,
  label: string,
  value: number
) {
  const input = knob(page, slotName, label);
  await input.evaluate((element, next) => {
    const el = element as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value"
    )?.set;
    setter?.call(el, String(next));
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }, value);
}

/** Set any range input through the native setter so React's value tracker sees it. */
export async function setRangeInput(
  locator: import("@playwright/test").Locator,
  value: number
) {
  await locator.evaluate((element, next) => {
    const el = element as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value"
    )?.set;
    setter?.call(el, String(next));
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }, value);
}

export async function openCatalog(page: Page) {
  await dismissOverlays(page);
  const add = page.locator(".sp-add-inline, .sp-add").first();
  await add.click({ timeout: 8000 });
  await expect(page.locator(".sp-dialog[role='dialog']")).toBeVisible({ timeout: 10_000 });
}

export async function addPlugin(page: Page, name: string) {
  await openCatalog(page);
  await page.locator(".sp-card", { hasText: new RegExp(`^${name}`) }).first().click();
  await expect(page.locator(".sp-dialog[role='dialog']")).toHaveCount(0);
}

export async function removeSlot(
  page: Page,
  name: string,
  which: "first" | "last" = "first"
) {
  const buttons = page.locator(`button[aria-label="Remove ${name}"]`);
  const target = which === "last" ? buttons.last() : buttons.first();
  await target.click({ timeout: 8000 });
  await page.waitForTimeout(150);
}

export async function removeAllSlots(page: Page) {
  for (let guard = 0; guard < 12; guard += 1) {
    const buttons = page.locator(".sp-slot-tools button[aria-label^='Remove ']");
    if ((await buttons.count()) === 0) break;
    await buttons.first().click({ timeout: 8000 });
    await page.waitForTimeout(120);
  }
}

export async function restoreChain(page: Page) {
  await removeAllSlots(page);
  await addPlugin(page, "Compressor");
  await addPlugin(page, "Reverb");
}

export async function waitSaved(page: Page) {
  await expect(page.locator(".se-save")).toContainText("Saved", { timeout: 25_000 });
  await page.waitForTimeout(700);
}

/** Open a slot's preset menu, tolerating an already-open menu. */
export async function ensurePresetMenu(page: Page, slotName: string) {
  const menu = slot(page, slotName).locator(".sp-preset-menu");
  if ((await menu.count()) === 0) {
    await slot(page, slotName).locator(".sp-preset").click();
  }
  await expect(menu).toBeVisible({ timeout: 10_000 });
  return menu;
}

/** Read the saved project document straight from the API. */
export async function savedProject(page: Page, projectId: string) {
  return page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`);
    return (await response.json()) as Record<string, unknown>;
  }, projectId);
}
