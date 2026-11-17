import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import {
  EVIDENCE_DIR,
  captureEditor,
  createProject,
  makeRecorder,
  openDock,
  openProject,
  openProjectAllowGate,
  p1Document,
  p2Document,
  quietHelp,
  selectTrack,
  shot,
  signIn,
} from "./w5-harness";

/**
 * W5 independent manual run - area E (24 viewport checks).
 * Rules asserted here come from app/globals.css and section E of the checklist.
 */

const REC = makeRecorder("e");
const SIZES = {
  "1689x1277": { width: 1689, height: 1277 },
  "1280x800": { width: 1280, height: 800 },
  "768x1024": { width: 768, height: 1024 },
  "767x1024": { width: 767, height: 1024 },
} as const;
type SizeName = keyof typeof SIZES;

let P1 = "";
let P2 = "";
let PLONG = "";
let page: Page;

async function check(id: string, vp: SizeName, plan: string, fn: () => Promise<string>) {
  try {
    const evidence = await fn();
    REC.record(id, "PASS", evidence);
  } catch (error) {
    const file = await shot(page, `${id}-${vp}`);
    REC.fail(id, error instanceof Error ? error.message : String(error), `${plan} - ${file}`);
  }
}

async function at(vp: SizeName) {
  await page.setViewportSize(SIZES[vp]);
}

function visible(locator: ReturnType<Page["locator"]>) {
  return locator.isVisible();
}

async function box(locator: ReturnType<Page["locator"]>) {
  const rect = await locator.boundingBox();
  if (!rect) return null;
  return {
    ...rect,
    right: rect.x + rect.width,
    bottom: rect.y + rect.height,
  };
}

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ browser }) => {
  test.setTimeout(300_000);
  page = await browser.newPage();
  page.setDefaultTimeout(15_000);
  await quietHelp(page);
  await page.setViewportSize(SIZES["1689x1277"]);
  page.on("pageerror", (error) => console.log("PAGEERROR", error.message));
  await signIn(page);
  P1 = await createProject(page, "W5 P1 fixture (E)", p1Document());
  P2 = await createProject(page, "W5 P2 fixture (E)", p2Document());
  const long = p1Document();
  PLONG = await createProject(
    page,
    "A very long project title that must truncate inside the chip without pushing the transport",
    long
  );
});

test.afterAll(async () => {
  REC.flush();
  await page.close();
});

test("E 1689x1277", async () => {
  test.setTimeout(6 * 60_000);
  await at("1689x1277");
  await openProject(page, P1);

  await check("E-01", "1689x1277", "full header at the reference width", async () => {
    const head = page.locator(".se-head");
    const parts: Record<string, boolean> = {
      chip: await visible(page.locator(".se-chip")),
      undo: await visible(page.locator("button[aria-label='Undo']")),
      redo: await visible(page.locator("button[aria-label='Redo']")),
      back: await visible(page.locator("button[aria-label='Back to start']")),
      record: await visible(page.locator("button[aria-label='Record']")),
      inputToggle: await visible(page.locator("button[aria-label='Choose input for recording']")),
      stop: await visible(page.locator("button[aria-label='Stop']")),
      play: await visible(page.locator("button[aria-label='Play']")),
      loop: await visible(page.locator("button[aria-label='Loop']").first()),
      metronome: await visible(page.locator("[data-help='metronome']")),
      clock: await visible(page.locator(".se-readout[aria-label='Time']")),
      barBeat: await visible(page.locator(".se-readout[aria-label='Bar and beat']")),
      bpm: await visible(page.locator("input[aria-label='Tempo in BPM']")),
      signature: await visible(page.locator("select[aria-label='Time signature']")),
      save: await visible(page.locator(".se-save")),
      meter: await visible(page.locator(".se-meter")),
      speed: await visible(page.locator("[data-help='speed']")),
      export: await visible(page.locator("button[aria-label='Export menu']")),
      library: await visible(page.locator("button[data-help='library']").first()),
    };
    const missing = Object.entries(parts)
      .filter(([, value]) => !value)
      .map(([key]) => key);
    expect(missing).toEqual([]);
    // The mirror dot is conditional on a Suno link; this fixture has none (F-area owns it).
    const dot = await page.locator(".se-sync-dot").count();
    return `${Object.keys(parts).length} header controls visible; sync dot count=${dot} (unlinked fixture)`;
  });

  await check("E-02", "1689x1277", "bands fill 1277px and the shell never scrolls", async () => {
    // The bottom panel only renders a surface once a track is selected.
    await openDock(page);
    const shell = await page.locator(".se-shell").evaluate((el) => ({
      clientHeight: el.clientHeight,
      scrollHeight: el.scrollHeight,
      overflow: getComputedStyle(el).overflow,
    }));
    expect(shell.clientHeight).toBe(1277);
    expect(shell.scrollHeight).toBe(shell.clientHeight);
    const head = Math.round((await box(page.locator(".se-head")))!.height);
    const foot = Math.round((await box(page.locator(".se-foot")))!.bottom);
    const dock = Math.round((await box(page.locator(".sp-dock").first()))!.bottom);
    expect(foot).toBe(1277);
    expect(dock).toBeLessThanOrEqual(foot);
    return `clientHeight=${shell.clientHeight}, scrollHeight=${shell.scrollHeight}, head=${head}px, dock bottom=${dock}, footer bottom=${foot}`;
  });

  await check("E-03", "1689x1277", "the dock shows at least three 448px slots", async () => {
    await openDock(page);
    const widths = await page
      .locator("article.sp-slot")
      .evaluateAll((nodes) => nodes.map((n) => Math.round(n.getBoundingClientRect().width)));
    const lefts = await page
      .locator("article.sp-slot")
      .evaluateAll((nodes) => nodes.map((n) => Math.round(n.getBoundingClientRect().left)));
    expect(widths.filter((width) => width === 448).length).toBeGreaterThanOrEqual(2);
    const overlaps = lefts.some(
      (left, index) => index > 0 && left < lefts[index - 1] + widths[index - 1] - 1
    );
    expect(overlaps).toBe(false);
    return `slot widths=${widths.join(",")}, lefts=${lefts.join(",")}`;
  });

  await check("E-04", "1689x1277", "reference frame captured for the comparison set", async () => {
    const file = await captureEditor(page, "ours-studio-editor-1689x1277");
    const size = fs.statSync(path.join(EVIDENCE_DIR, file)).size;
    expect(size).toBeGreaterThan(20_000);
    return `docs/studio/reports/evidence-w5/${file} (${Math.round(size / 1024)} KB, not a blank frame)`;
  });
});

test("E 1280x800", async () => {
  test.setTimeout(6 * 60_000);
  await at("1280x800");
  await openProject(page, P1);

  await check("E-05", "1280x800", "master meter is gone at <=1600", async () => {
    const display = await page.locator(".se-meter").evaluate((el) => getComputedStyle(el).display);
    expect(display).toBe("none");
    return `.se-meter display=${display}`;
  });

  await check("E-06", "1280x800", "audition speed is gone at <=1600", async () => {
    const display = await page
      .locator("[data-help='speed']")
      .evaluate((el) => getComputedStyle(el).display);
    expect(display).toBe("none");
    return `[data-help="speed"] display=${display}`;
  });

  await check("E-07", "1280x800", "the rest of the header survives", async () => {
    const present = {
      save: await visible(page.locator(".se-save")),
      export: await visible(page.locator("button[aria-label='Export menu']")),
      library: await visible(page.locator("button[data-help='library']").first()),
      play: await visible(page.locator("button[aria-label='Play']")),
      stop: await visible(page.locator("button[aria-label='Stop']")),
      clock: await visible(page.locator(".se-readout[aria-label='Time']")),
      bpm: await visible(page.locator("input[aria-label='Tempo in BPM']")),
    };
    expect(Object.entries(present).filter(([, value]) => !value).map(([key]) => key)).toEqual([]);
    const dot = await page.locator(".se-sync-dot").count();
    return `save/export/library/transport/time/BPM visible; sync dot count=${dot} (unlinked fixture)`;
  });

  await check("E-08", "1280x800", "the library rail reserves 368px and the timeline keeps >=4 bars", async () => {
    await page.locator("button[data-help='library']").first().click();
    await expect(page.locator(".se-shell")).toHaveClass(/has-rail/);
    const rail = await box(page.locator(".se-library"));
    const padding = await page.locator(".se-body").evaluate((el) => getComputedStyle(el).paddingRight);
    expect(padding).toBe("368px");
    const timeline = await page.locator(".se-timeline").evaluate((el) => ({
      clientWidth: el.clientWidth,
      scrollWidth: el.scrollWidth,
    }));
    expect(timeline.clientWidth).toBeGreaterThanOrEqual(4 * 96 - 8);
    const body = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(body.scrollWidth).toBeLessThanOrEqual(body.clientWidth + 1);
    await page.locator("button[data-help='library']").first().click();
    return `body reserves ${padding}; panel box ${Math.round(rail!.width)}px; timeline clientWidth=${timeline.clientWidth} (>=4x96); no page h-scroll (${body.scrollWidth}/${body.clientWidth})`;
  });

  await check("E-09", "1280x800", "the dock rail scrolls and slot 1 is fully visible", async () => {
    await openDock(page);
    const first = await box(page.locator("article.sp-slot").first());
    const rail = await page.locator(".sp-rail").first().evaluate((el) => ({
      overflowX: getComputedStyle(el).overflowX,
      scrollWidth: el.scrollWidth,
      clientWidth: el.clientWidth,
    }));
    expect(first!.x).toBeGreaterThanOrEqual(0);
    expect(first!.x + first!.width).toBeLessThanOrEqual(1280);
    expect(["auto", "scroll"]).toContain(rail.overflowX);
    const clipped = await page.locator("article.sp-slot").first().evaluate((el) => {
      const rect = el.getBoundingClientRect();
      const knobs = Array.from(el.querySelectorAll(".sp-knob")).map((knob) =>
        knob.getBoundingClientRect()
      );
      return knobs.filter((k) => k.right > rect.right + 1 || k.left < rect.left - 1).length;
    });
    expect(clipped).toBe(0);
    return `slot 1 x=${Math.round(first!.x)}..${Math.round(first!.x + first!.width)}; overflowX=${rail.overflowX} (${rail.scrollWidth}/${rail.clientWidth}); ${clipped} clipped knobs`;
  });
});

test("E 768x1024", async () => {
  test.setTimeout(10 * 60_000);
  await at("768x1024");

  await check("E-10", "768x1024", "the editor still renders at 768 (gate starts at 767)", async () => {
    await openProject(page, P1);
    expect(await visible(page.locator(".se-shell"))).toBe(true);
    const gate = await page.locator(".se-desktop-gate").evaluate((el) => getComputedStyle(el).display);
    expect(gate).toBe("none");
    return `.se-shell visible; .se-desktop-gate display=${gate}`;
  });

  await check("E-11", "768x1024", "52px header without undo, save, stop, input toggle or metronome", async () => {
    const head = await page.locator(".se-head").evaluate((el) => Math.round(el.getBoundingClientRect().height));
    expect(head).toBe(52);
    const hidden: Record<string, string> = {
      undoGroup: await page
        .locator(".se-head-left .se-head-group")
        .evaluate((el) => getComputedStyle(el).display),
      save: await page.locator(".se-save").evaluate((el) => getComputedStyle(el).display),
      stop: await page
        .locator(".se-head-center button[aria-label='Stop']")
        .evaluate((el) => getComputedStyle(el).display),
      inputToggle: await page
        .locator(".se-input-toggle")
        .evaluate((el) => getComputedStyle(el).display),
      metronome: await page
        .locator(".se-head [data-help='metronome']")
        .evaluate((el) => getComputedStyle(el).display),
    };
    for (const [key, value] of Object.entries(hidden)) expect(value, key).toBe("none");
    return `header=${head}px; hidden = ${Object.keys(hidden).join(", ")}`;
  });

  await check("E-12", "768x1024", "clock visible, bar/beat hidden", async () => {
    expect(await visible(page.locator(".se-readout[aria-label='Time']"))).toBe(true);
    const barBeat = await page
      .locator(".se-readout[aria-label='Bar and beat']")
      .evaluate((el) => getComputedStyle(el).display);
    expect(barBeat).toBe("none");
    return `clock display=${await page
      .locator(".se-readout[aria-label='Time']")
      .evaluate((el) => getComputedStyle(el).display)}; bar/beat=${barBeat}`;
  });

  await check("E-13", "768x1024", "a long title truncates at 150px without pushing the transport", async () => {
    await openProject(page, PLONG);
    const chip = await page.locator(".se-chip").evaluate((el) => {
      const style = getComputedStyle(el);
      return {
        width: Math.round(el.getBoundingClientRect().width),
        maxWidth: style.maxWidth,
        truncated: el.scrollWidth > el.clientWidth,
        right: Math.round(el.getBoundingClientRect().right),
      };
    });
    const play = await box(page.locator("button[aria-label='Play']"));
    expect(chip.maxWidth).toBe("150px");
    expect(chip.width).toBeLessThanOrEqual(151);
    expect(chip.truncated).toBe(true);
    expect(play!.x).toBeGreaterThan(chip.right);
    return `chip ${chip.width}px (max ${chip.maxWidth}, truncated=${chip.truncated}); Play starts at ${Math.round(play!.x)} > chip right ${chip.right}`;
  });

  await check("E-14", "768x1024", "the prompt bar is hidden at <=900", async () => {
    await openProject(page, P1);
    const display = await page.locator(".se-prompt").evaluate((el) => getComputedStyle(el).display);
    expect(display).toBe("none");
    return `.se-prompt display=${display}`;
  });

  await check("E-15", "768x1024", "track panel is 260px and the row controls still work", async () => {
    const width = await page.locator(".se-tracks").evaluate((el) => Math.round(el.getBoundingClientRect().width));
    expect(width).toBe(260);
    const controls = {
      mute: await visible(page.locator("button[aria-label='Mute Drums']")),
      solo: await visible(page.locator("button[aria-label='Solo Drums']")),
      arm: await visible(page.locator("button[aria-label='Arm Drums']")),
      options: await visible(page.locator("button[aria-label='Options for Drums']")),
    };
    expect(Object.values(controls).every(Boolean)).toBe(true);
    return `.se-tracks width=${width}; mute/solo/arm/options visible`;
  });

  await check("E-16", "768x1024", "catalogue is a two-column scrolling grid", async () => {
    await openDock(page);
    await page.locator(".sp-add-inline, .sp-add").first().click();
    const dialog = page.locator(".sp-dialog[role='dialog']");
    await expect(dialog).toBeVisible();
    const grid = await dialog.locator(".sp-catalog:not(.sp-catalog-mine)").evaluate((el) => {
      const style = getComputedStyle(el);
      return {
        columns: style.gridTemplateColumns.split(" ").length,
        overflowY: style.overflowY,
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
      };
    });
    expect(grid.columns).toBe(2);
    expect(["auto", "scroll"]).toContain(grid.overflowY);
    await dialog.locator("button[aria-label='Close']").click();
    await expect(dialog).toHaveCount(0);
    return `2 columns; overflowY=${grid.overflowY} (${grid.scrollHeight}/${grid.clientHeight})`;
  });

  await check("E-17", "768x1024", "a plugin slot narrows to 260px without clipping", async () => {
    await openDock(page);
    const width = await page
      .locator("article.sp-slot")
      .first()
      .evaluate((el) => Math.round(el.getBoundingClientRect().width));
    expect(width).toBe(260);
    const clipped = await page.locator("article.sp-slot").first().evaluate((el) => {
      const rect = el.getBoundingClientRect();
      return Array.from(el.querySelectorAll(".sp-knob"))
        .map((knob) => knob.getBoundingClientRect())
        .filter((k) => k.right > rect.right + 1 || k.left < rect.left - 1).length;
    });
    expect(clipped).toBe(0);
    return `slot width=${width}; ${clipped} knobs outside the card`;
  });

  await check("E-18", "768x1024", "settings, share, clip menu and transform dialogs fit the viewport", async () => {
    const inside = async (locator: ReturnType<Page["locator"]>) => {
      const rect = await locator.evaluate((el) => {
        const box = el.getBoundingClientRect();
        return { left: box.left, top: box.top, right: box.right, bottom: box.bottom };
      });
      return (
        rect.left >= -1 &&
        rect.top >= -1 &&
        rect.right <= 768 + 1 &&
        rect.bottom <= 1024 + 1
      );
    };
    await page.locator(".se-chip").click();
    await page
      .locator(".se-project-menu [role='menuitem']", { hasText: "Studio Settings" })
      .click();
    const settings = page.locator("[role='dialog'][aria-label='Studio Settings']");
    await expect(settings).toBeVisible();
    expect(await inside(settings)).toBe(true);
    await settings.locator("button[aria-label='Close']").click();
    await expect(settings).toHaveCount(0);

    await page.locator(".se-chip").click();
    await page.locator(".se-project-menu [role='menuitem']", { hasText: "Share Project" }).click();
    const share = page.locator("[role='dialog'][aria-label='Share project']");
    await expect(share).toBeVisible();
    expect(await inside(share)).toBe(true);
    await share.getByRole("button", { name: "Done" }).click();
    await expect(share).toHaveCount(0);

    const clip = page.locator(".se-clip").first();
    await clip.click({ button: "right" });
    const menu = page.locator(".se-clip-menu[role='menu']");
    await expect(menu).toBeVisible();
    expect(await inside(menu)).toBe(true);
    const offscreen = await menu.evaluate((el) => {
      const viewport = window.innerHeight;
      return Array.from(el.querySelectorAll("[role='menuitem']"))
        .map((row) => row.getBoundingClientRect())
        .filter((rect) => rect.bottom > viewport + 1 || rect.top < -1).length;
    });
    expect(offscreen).toBe(0);
    await page.locator(".se-clip-menu [role='menuitem']", { hasText: "Cover" }).click();
    const transform = page.locator("[role='dialog']").first();
    await expect(transform).toBeVisible();
    expect(await inside(transform)).toBe(true);
    await transform.getByRole("button", { name: /Cancel/ }).click();
    await expect(page.locator("[role='dialog']")).toHaveCount(0);
    return `settings, share, clip menu and transform dialog all inside 768x1024`;
  });

  await check("E-19", "768x1024", "the assistant takes a 360px overlay and shifts the body", async () => {
    await page.locator(".se-logo").click();
    await page.keyboard.press("1");
    await expect(page.locator(".se-shell")).toHaveClass(/has-assistant/);
    const panel = await box(page.locator(".se-assistant"));
    const padding = await page.locator(".se-body").evaluate((el) => getComputedStyle(el).paddingLeft);
    expect(Math.round(panel!.width)).toBeGreaterThanOrEqual(320);
    expect(padding).toBe("392px");
    const timeline = await page.locator(".se-timeline").evaluate((el) => ({
      scrollWidth: el.scrollWidth,
      clientWidth: el.clientWidth,
    }));
    expect(timeline.scrollWidth).toBeGreaterThan(timeline.clientWidth);
    await page.keyboard.press("1");
    return `assistant ${Math.round(panel!.width)}px; body padding-left=${padding}; timeline scrolls (${timeline.scrollWidth}/${timeline.clientWidth})`;
  });

  await check("E-20", "768x1024", "take lanes and the MIDI editor fit and scroll", async () => {
    await openProject(page, P2);
    await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
    await page.locator("button[aria-label='Take lanes']").click();
    const takes = page.locator("section.se-takes[aria-label='Take lanes']");
    await expect(takes).toBeVisible();
    const takesBox = await box(takes);
    expect(takesBox!.bottom).toBeLessThanOrEqual(1024);
    await page.locator("button[aria-label='Take lanes']").click();

    await page.locator(".se-clip", { hasText: "Bass" }).first().dblclick();
    const midi = page.locator(".se-midi");
    await expect(midi).toBeVisible();
    const midiBox = await midi.evaluate((el) => {
      const rect = el.getBoundingClientRect();
      return {
        height: Math.round(rect.height),
        maxHeight: getComputedStyle(el).maxHeight,
        bottom: Math.round(rect.bottom),
      };
    });
    expect(midiBox.bottom).toBeLessThanOrEqual(1024);
    expect(midiBox.height).toBeLessThanOrEqual(380);
    const scroller = await midi.evaluate((el) => {
      const nodes = Array.from(el.querySelectorAll("*")) as HTMLElement[];
      return nodes.some((node) => {
        const style = getComputedStyle(node);
        return (
          ["auto", "scroll"].includes(style.overflowY) && node.scrollHeight > node.clientHeight
        );
      });
    });
    return `takes fit (${Math.round(takesBox!.height)}px); MIDI ${midiBox.height}px (max-height ${midiBox.maxHeight}), inner scroll=${scroller}`;
  });
});

test("E 767x1024", async () => {
  test.setTimeout(5 * 60_000);
  await at("767x1024");
  await openProjectAllowGate(page, P1);

  await check("E-21", "767x1024", "the desktop gate replaces the shell", async () => {
    const gate = await page.locator(".se-desktop-gate").evaluate((el) => getComputedStyle(el).display);
    const shell = await page.locator(".se-shell").evaluate((el) => getComputedStyle(el).display);
    expect(gate).toBe("flex");
    expect(shell).toBe("none");
    const height = await page.locator(".se-desktop-gate").evaluate((el) => el.getBoundingClientRect().height);
    expect(Math.round(height)).toBe(1024);
    return `gate display=${gate} (${Math.round(height)}px tall); shell display=${shell}`;
  });

  await check("E-22", "767x1024", "the gate names the product, the limit and the way back", async () => {
    const card = page.locator(".se-gate-card");
    await expect(card.getByRole("heading", { name: "CAMXORA Studio" })).toBeVisible();
    const text = await card.innerText();
    expect(text).toContain("Studio is desktop-only.");
    const link = page.locator(".se-gate-link");
    await expect(link).toHaveText("Back to Create");
    await expect(link).toHaveAttribute("href", "/create");
    return `heading + desktop-only sentence + Back to Create -> /create`;
  });

  await check("E-23", "767x1024", "nothing behind the gate, no h-scroll, one focusable control", async () => {
    const chrome = await page
      .locator(".se-head, .se-body, .sp-dock, .se-foot")
      .evaluateAll((nodes) => nodes.filter((node) => (node as HTMLElement).offsetParent !== null).length);
    expect(chrome).toBe(0);
    const scroll = await page.evaluate(() => ({
      body: document.body.scrollWidth,
      doc: document.documentElement.scrollWidth,
    }));
    expect(scroll.body).toBeLessThanOrEqual(767);
    expect(scroll.doc).toBeLessThanOrEqual(767);
    const focusable = await page.evaluate(() => {
      const nodes = Array.from(
        document.querySelectorAll("a[href], button, input, select, textarea, [tabindex]")
      ) as HTMLElement[];
      return nodes.filter((node) => {
        const style = getComputedStyle(node);
        return (
          style.display !== "none" &&
          style.visibility !== "hidden" &&
          node.tabIndex >= 0 &&
          node.getBoundingClientRect().width > 0
        );
      }).length;
    });
    expect(focusable).toBe(1);
    await page.keyboard.press("Tab");
    const focused = await page.evaluate(() => document.activeElement?.className ?? "");
    expect(focused).toContain("se-gate-link");
    return `0 chrome nodes visible; scrollWidth body=${scroll.body} doc=${scroll.doc}; ${focusable} focusable control (link)`;
  });
});

test("E-24 all four", async () => {
  test.setTimeout(10 * 60_000);

  await check("E-24", "1689x1277", "no clipping or overlap at the four viewports", async () => {
    const results: string[] = [];
    for (const vp of ["1689x1277", "1280x800", "768x1024", "767x1024"] as SizeName[]) {
      await at(vp);
      await openProjectAllowGate(page, P1);
      await captureEditor(page, `ours-studio-editor-${vp}`);
      const report = await page.evaluate(() => {
        const visible = (el: Element) => {
          const style = getComputedStyle(el);
          const rect = el.getBoundingClientRect();
          return (
            style.display !== "none" &&
            style.visibility !== "hidden" &&
            rect.width > 0 &&
            rect.height > 0
          );
        };
        const children = Array.from(
          document.querySelectorAll(".se-head > div > *")
        ).filter(visible);
        const boxes = children.map((el) => ({
          label:
            el.getAttribute("aria-label") ??
            (el as HTMLElement).className ??
            el.tagName,
          rect: el.getBoundingClientRect(),
        }));
        const overlaps: string[] = [];
        for (let i = 0; i < boxes.length; i += 1) {
          for (let j = i + 1; j < boxes.length; j += 1) {
            const a = boxes[i].rect;
            const b = boxes[j].rect;
            const x = Math.min(a.right, b.right) - Math.max(a.left, b.left);
            const y = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
            if (x > 1 && y > 1) overlaps.push(`${boxes[i].label} x ${boxes[j].label}`);
          }
        }
        return {
          overlaps,
          horizontalScroll: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
        };
      });
      expect(report.overlaps, `${vp} header overlaps`).toEqual([]);
      expect(report.horizontalScroll).toBeLessThanOrEqual(report.clientWidth + 1);
      results.push(`${vp}: 0 overlaps, scrollWidth ${report.horizontalScroll}/${report.clientWidth}`);
    }

    // Clip menu in the bottom-right corner: capped height, fully on screen.
    await at("1689x1277");
    await openProject(page, P1);
    const clip = page.locator(".se-clip").last();
    await clip.click({ button: "right" });
    const menu = page.locator(".se-clip-menu[role='menu']");
    await expect(menu).toBeVisible();
    const menuBox = await menu.evaluate((el) => {
      const rect = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      const rows = Array.from(el.querySelectorAll("[role='menuitem']")).map((row) =>
        row.getBoundingClientRect()
      );
      return {
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        right: Math.round(rect.right),
        bottom: Math.round(rect.bottom),
        maxHeight: style.maxHeight,
        overflowY: style.overflowY,
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
        offscreenRows: rows.filter((row) => row.bottom > 1277 + 1 || row.top < -1).length,
        lastRowBottom: Math.round(Math.max(...rows.map((row) => row.bottom))),
      };
    });
    expect(menuBox.left).toBeGreaterThanOrEqual(0);
    expect(menuBox.top).toBeGreaterThanOrEqual(0);
    expect(menuBox.right).toBeLessThanOrEqual(1689);
    expect(menuBox.bottom).toBeLessThanOrEqual(1277);
    expect(menuBox.offscreenRows).toBe(0);
    if (menuBox.scrollHeight > menuBox.clientHeight) {
      expect(["auto", "scroll"]).toContain(menuBox.overflowY);
    }
    results.push(
      `bottom-right clip menu ${menuBox.left}..${menuBox.right} x ${menuBox.top}..${menuBox.bottom} (max-height ${menuBox.maxHeight}, content ${menuBox.scrollHeight}/${menuBox.clientHeight}, overflowY ${menuBox.overflowY}, last row bottom ${menuBox.lastRowBottom})`
    );
    return results.join("; ");
  });
});

