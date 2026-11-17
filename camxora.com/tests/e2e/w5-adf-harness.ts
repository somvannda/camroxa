import { expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

import { EMAIL, PASSWORD } from "./w5-harness";

/**
 * W5-ADF harness (areas A, D, F).
 *
 * Same contract as w5-harness: every verdict is measured by driving the UI, and the
 * rows are written to docs/studio/reports/evidence-adf/results-<area>.json so the
 * report is generated from the run instead of memory.
 */

const ROOT = process.cwd();
export const EVIDENCE_DIR = path.join(ROOT, "..", "docs", "studio", "reports", "evidence-adf");

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
    pass(id: string, evidence: string) {
      rows.push({ id, verdict: "PASS", evidence });
      console.log(`PASS    ${id}  ${evidence}`);
    },
    fail(id: string, message: string, evidence: string) {
      rows.push({ id, verdict: "FAIL", evidence, detail: message });
      console.log(`FAIL    ${id}  ${evidence} :: ${message}`);
    },
    na(id: string, message: string) {
      rows.push({ id, verdict: "N/A", evidence: message });
      console.log(`N/A     ${id}  ${message}`);
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
  await page.screenshot({ path: path.join(EVIDENCE_DIR, `${name}.png`) });
  return `${name}.png`;
}

/**
 * Screenshot that gives up instead of hanging the run. Used where a renderer stall is
 * itself the finding: the row must still be recorded.
 */
export async function safeShot(page: Page, name: string, timeoutMs = 6000) {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
  const file = path.join(EVIDENCE_DIR, `${name}.png`);
  const result = await Promise.race([
    page.screenshot({ path: file, timeout: timeoutMs }).then(() => `${name}.png`),
    new Promise<string>((resolve) => setTimeout(() => resolve(`screenshot-timeout`), timeoutMs + 500)),
  ]).catch(() => "screenshot-error");
  return result;
}

/** True when the page's main thread answers a trivial evaluate. */
export async function pageResponsive(page: Page, timeoutMs = 4000) {
  return Promise.race([
    page.evaluate(() => 1).then(() => true),
    new Promise<boolean>((resolve) => setTimeout(() => resolve(false), timeoutMs)),
  ]).catch(() => false);
}

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

/** Turn the hover help off so its card cannot sit over a control under test. */
export async function quietHelp(page: Page, clearDrafts = true) {
  await page.addInitScript((wipe) => {
    try {
      const raw = window.localStorage.getItem("studio:settings");
      const parsed = raw ? JSON.parse(raw) : {};
      window.localStorage.setItem(
        "studio:settings",
        JSON.stringify({ ...parsed, whatsThis: false })
      );
      if (!wipe) return;
      for (const key of Object.keys(window.localStorage)) {
        if (key.startsWith("studio:draft:")) window.localStorage.removeItem(key);
      }
    } catch {
      /* storage unavailable */
    }
  }, clearDrafts);
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

type Doc = { bpm: number; time_signature: string; data: Record<string, unknown> };

/** P1: Drums (2 song clips) / Bass (MIDI) / Vox (uploaded) / Scratch (hidden+muted). */
export function adfDocument(): Doc {
  const midi = Array.from({ length: 8 }, (_, index) => ({
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
          volumeAutomation: [
            { id: "a-1", time: 0, value: 60 },
            { id: "a-2", time: 4, value: 90 },
          ],
          panAutomation: [],
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
          songId: "song-adf-1",
        },
        {
          id: "c-d2",
          trackId: "t-drums",
          title: "Drums B",
          start: 8,
          duration: 4,
          audioUrl: "/seed/demo-loop.wav",
          songId: "song-adf-1",
        },
        {
          id: "c-bass",
          trackId: "t-bass",
          title: "Bass",
          start: 0,
          duration: 8,
          midi: { notes: midi, bend: [], mod: [] },
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
      markers: [{ id: "m-1", time: 4, label: "Verse", color: "#3dafff" }],
      chains: {
        "t-drums": [
          {
            entryId: "e-comp",
            pluginId: "compressor",
            presetId: null,
            presetName: "Default",
            dirty: false,
            params: { threshold: -18, ratio: 4, knee: 6, attack: 10, release: 120, gain: 0 },
            assetId: null,
            bypassed: false,
            poppedOut: false,
          },
          {
            entryId: "e-rev",
            pluginId: "reverb",
            presetId: null,
            presetName: "Default",
            dirty: false,
            params: {
              time: 2.4,
              mix: 25,
              width: 100,
              damping: 40,
              predelay: 20,
              lowCut: 120,
              highCut: 14000,
            },
            assetId: null,
            bypassed: false,
            poppedOut: false,
          },
        ],
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

/** P-warp: P1 where Drums A carries stretch state + clip settings. */
export function warpDocument(): Doc {
  const doc = adfDocument();
  const lanes = (doc.data as { lanes: Array<Record<string, unknown>> }).lanes;
  const clip = lanes[0];
  clip.warp = {
    on: false,
    mode: "start-end",
    formant: 0,
    markers: [],
  };
  clip.audio = { gainDb: 0, loop: false, reverse: false, pitch: 0, speed: 100 };
  return doc;
}

export async function createProject(page: Page, title: string, doc: Doc): Promise<string> {
  await dismissOverlays(page);
  return page.evaluate(
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
}

export async function openProject(page: Page, projectId: string, expectClip = true) {
  await page.goto(`/studio/editor?project=${projectId}`);
  await dismissOverlays(page);
  await expect(page.locator(".se-track").first()).toBeVisible({ timeout: 30_000 });
  if (expectClip) {
    await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  }
  await dismissOverlays(page);
}

export async function savedProject(page: Page, projectId: string) {
  return page.evaluate(async (id) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${id}`, {
      cache: "no-store",
    });
    return (await response.json()) as Record<string, any>;
  }, projectId);
}

export function savedLanes(doc: Record<string, any>): Array<Record<string, any>> {
  return ((doc.data ?? doc) as { lanes?: Array<Record<string, any>> }).lanes ?? [];
}

export function laneOf(doc: Record<string, any>, id: string): Record<string, any> | undefined {
  return savedLanes(doc).find((clip) => clip.id === id);
}

export async function waitSaved(page: Page) {
  await expect(page.locator(".se-save")).toContainText("Saved", { timeout: 25_000 });
  await page.waitForTimeout(600);
}

/** Bar width comes from the ruler geometry, so measurements do not hardcode the zoom. */
export async function barMetrics(page: Page) {
  return page.evaluate(() => {
    const ruler = document.querySelector(".se-ruler-inner") as HTMLElement | null;
    const bars = document.querySelectorAll(".se-bar-line").length;
    if (!ruler || !bars) return { barWidth: 0, barCount: 0 };
    return { barWidth: ruler.getBoundingClientRect().width / bars, barCount: bars };
  });
}

export async function lanesBox(page: Page) {
  const box = await page.locator(".se-lanes-inner").boundingBox();
  if (!box) throw new Error("no lanes box");
  return box;
}

export async function clipBox(page: Page, title: string) {
  const box = await page.locator(".se-clip", { hasText: title }).first().boundingBox();
  if (!box) throw new Error(`no clip box for ${title}`);
  return box;
}

export async function clickClip(page: Page, title: string) {
  await page.locator(".se-clip", { hasText: title }).first().click();
  await page.waitForTimeout(120);
}

export async function selectTrack(page: Page, name: string) {
  await dismissOverlays(page);
  await page.locator(".se-track-name", { hasText: name }).first().click();
  await page.waitForTimeout(120);
}

/** Drag with a real pointer press, several moves (past the 3 px threshold) and a release. */
export async function drag(
  page: Page,
  from: { x: number; y: number },
  to: { x: number; y: number },
  steps = 14
) {
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  // Editors that attach their move listener on the press (MIDI notes, warp markers)
  // need the state update to land before the pointer moves.
  await page.waitForTimeout(120);
  await page.mouse.move(to.x, to.y, { steps });
  await page.mouse.up();
  await page.waitForTimeout(250);
}

export async function setRange(page: Page, startBar: number, endBar: number) {
  const { barWidth } = await barMetrics(page);
  const box = await lanesBox(page);
  const y = box.y + 6;
  await drag(
    page,
    { x: box.x + startBar * barWidth + 2, y },
    { x: box.x + endBar * barWidth - 2, y }
  );
}

/** Pointer position (client coords) inside the bar ruler at a given bar. */
export async function rulerPoint(page: Page, bar: number, yOffset = 8) {
  const { barWidth } = await barMetrics(page);
  const ruler = await page.locator(".se-ruler-bars").boundingBox();
  if (!ruler) throw new Error("no ruler");
  return { x: ruler.x + bar * barWidth, y: ruler.y + yOffset };
}

export async function clipMenu(page: Page, title: string) {
  await page.locator(".se-clip", { hasText: title }).first().click({ button: "right" });
  await expect(page.locator(".se-clip-menu[role='menu']")).toBeVisible({ timeout: 10_000 });
  return page.locator(".se-clip-menu[role='menu']");
}

export async function clipMenuRow(page: Page, label: string) {
  return page.locator(".se-clip-menu[role='menuitem'], .se-clip-menu button", { hasText: label }).first();
}

export async function bodyScroll(page: Page) {
  return page.evaluate(() => document.body.scrollWidth);
}
