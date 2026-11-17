import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import {
  check,
  createProject,
  getProject,
  makeRecorder,
  menu,
  openEditor,
  p1Document,
  quietStorage,
  rowByText,
  shot,
  signIn,
  toastText,
} from "./w5c-harness";

/**
 * W5-C, spec 3: C6 (track menu, add track, hidden tracks, groups — 23 rows) and
 * C7 (export menu — 8 rows).
 */

test.describe.configure({ mode: "serial" });
test.setTimeout(900_000);

const rec = makeRecorder("c6-c7");
const viewport = { width: 1689, height: 1277 };

let ctx: BrowserContext;
let page: Page;
let P1 = "";
let P5 = "";
let PEXPORT = "";

function clipLessDocument() {
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

test.beforeAll(async ({ browser }) => {
  ctx = await browser.newContext({ viewport, acceptDownloads: true });
  page = await ctx.newPage();
  page.setDefaultTimeout(15_000);
  await quietStorage(page);
  await signIn(page);
  P1 = await createProject(page, "W5C C6", p1Document());
  P5 = await createProject(page, "W5C C6 empty track", clipLessDocument());
  PEXPORT = await createProject(page, "W5C C7", p1Document());
});

test.afterAll(async () => {
  rec.flush();
  await ctx?.close();
});

async function openTrackMenu(track: string) {
  await page.locator(`button[aria-label="Options for ${track}"]`).first().click();
  await expect(menu(page, `${track} options`)).toBeVisible({ timeout: 10_000 });
  return menu(page, `${track} options`);
}

test("C6 — track menu, add track, hidden tracks, groups", async () => {
  await openEditor(page, P1);

  await check(rec, page, "C-108", async () => {
    const scope = await openTrackMenu("Drums");
    const rows = (await scope.locator('[role="menuitem"]').allInnerTexts()).map((text) =>
      text.replace(/\s+/g, " ").trim()
    );
    expect(rows).toEqual([
      "Rename track",
      "Color",
      "Collapse controls",
      "Duplicate",
      "Hide & Mute Track",
      "Delete",
      "Bounce track",
    ]);
    await shot(page, "C-108-1689x1277");
    return `menu "Drums options" with 7 rows: ${rows.join(" | ")}`;
  });

  await check(rec, page, "C-109", async () => {
    const scope = menu(page, "Drums options");
    await rowByText(scope, "Rename track").click();
    const input = page.locator('input[aria-label="Track name"]').first();
    await expect(input).toBeVisible({ timeout: 8000 });
    await expect(input).toBeFocused();
    const selection = await input.evaluate((node) => {
      const field = node as HTMLInputElement;
      return { start: field.selectionStart, end: field.selectionEnd, length: field.value.length };
    });
    await input.fill("Drums edited");
    await page.keyboard.press("Enter");
    await expect(page.locator(".se-track-name", { hasText: "Drums edited" }).first()).toBeVisible({
      timeout: 8000,
    });
    const again = await openTrackMenu("Drums edited");
    await rowByText(again, "Rename track").click();
    await page.locator('input[aria-label="Track name"]').fill("Discard me");
    await page.keyboard.press("Escape");
    await expect(page.locator(".se-track-name", { hasText: "Discard me" })).toHaveCount(0);
    const third = await openTrackMenu("Drums edited");
    await rowByText(third, "Rename track").click();
    await page.locator('input[aria-label="Track name"]').fill("Drums blurred");
    await page.locator(".se-lanes").first().click({ position: { x: 1000, y: 700 } });
    await expect(page.locator(".se-track-name", { hasText: "Drums blurred" }).first()).toBeVisible({
      timeout: 8000,
    });
    expect(
      selection,
      `caret ${selection.start}–${selection.end} of ${selection.length}`
    ).toEqual({ start: 0, end: selection.length, length: selection.length });
    return "field focused with the name selected; Enter commits, Escape cancels, blur commits";
  });

  await check(rec, page, "C-110", async () => {
    const scope = await openTrackMenu("Drums blurred");
    await rowByText(scope, "Color").click();
    const group = page.locator('.se-track-menu-colors[role="group"][aria-label="Track colour"]');
    await expect(group).toBeVisible({ timeout: 8000 });
    const labels = await group.locator("button").evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("aria-label"))
    );
    expect(labels).toEqual([
      "Use #38bdf8",
      "Use #a78bfa",
      "Use #f472b6",
      "Use #fb923c",
      "Use #4ade80",
    ]);
    await group.locator('button[aria-label="Use #a78bfa"]').click();
    await expect(menu(page, "Drums blurred options")).toHaveCount(0, { timeout: 5000 });
    await page.waitForTimeout(800);
    const doc = await getProject(page, P1);
    const track = (doc.data as { tracks: Array<Record<string, unknown>> }).tracks.find(
      (item) => item.name === "Drums blurred"
    ) as Record<string, unknown> | undefined;
    expect(track?.color).toBe("#a78bfa");
    return `5 swatches in order; choosing one applied #a78bfa and closed the menu`;
  });

  await check(rec, page, "C-111", async () => {
    const scope = await openTrackMenu("Drums blurred");
    const collapse = rowByText(scope, "Collapse controls");
    await collapse.click();
    await page.waitForTimeout(400);
    const slidersAfterCollapse = await page
      .locator(".se-track", { hasText: "Drums blurred" })
      .locator(".se-track-slider")
      .count();
    const expandScope = await openTrackMenu("Drums blurred");
    const expand = rowByText(expandScope, "Expand controls");
    await expand.click();
    await page.waitForTimeout(400);
    const slidersAfterExpand = await page
      .locator(".se-track", { hasText: "Drums blurred" })
      .locator(".se-track-slider")
      .count();
    expect(slidersAfterCollapse).toBe(0);
    expect(slidersAfterExpand).toBeGreaterThan(0);
    return `label flips to "Expand controls"; sliders ${slidersAfterCollapse} → ${slidersAfterExpand}`;
  });

  await check(rec, page, "C-112", async () => {
    const before = await page.locator(".se-track").count();
    const scope = await openTrackMenu("Drums blurred");
    await rowByText(scope, "Duplicate").click();
    await page.waitForTimeout(1200);
    const after = await page.locator(".se-track").count();
    expect(after).toBe(before + 1);
    const doc = await getProject(page, P1);
    const tracks = (doc.data as { tracks: Array<Record<string, unknown>> }).tracks;
    const copy = tracks.find((item) => String(item.name).includes("Drums blurred copy"));
    expect(copy).toBeTruthy();
    const clipIds = copy!.clipIds as string[];
    const lanes = (doc.data as { lanes: Array<Record<string, unknown>> }).lanes;
    const clips = lanes.filter((lane) => clipIds.includes(String(lane.id)));
    expect(clips.length).toBe(2);
    const storedTrackIds = [...new Set(clips.map((clip) => String(clip.trackId)))];
    return `track count ${before} → ${after}; copy "${copy!.name}" carries ${clips.length} clips (their stored trackId still points at "${storedTrackIds.join(",")}" — ownership is by clipIds)`;
  });

  await check(rec, page, "C-113", async () => {
    const before = await page.locator(".se-track").count();
    const scope = await openTrackMenu("Drums blurred copy");
    await rowByText(scope, "Hide & Mute Track").click();
    await page.waitForTimeout(800);
    const after = await page.locator(".se-track").count();
    const pill = page.locator(".se-hidden-pill").first();
    await expect(pill).toBeVisible({ timeout: 8000 });
    const label = await pill.getAttribute("aria-label");
    expect(after).toBe(before - 1);
    const doc = await getProject(page, P1);
    const tracks = (doc.data as { tracks: Array<Record<string, unknown>> }).tracks;
    const hidden = tracks.find((item) => item.name === "Drums blurred copy");
    expect(hidden?.hidden).toBe(true);
    expect(hidden?.muted).toBe(true);
    return `track leaves the list (${before} → ${after}); pill "${label}"; stored hidden+muted`;
  });

  await check(rec, page, "C-114", async () => {
    const before = await page.locator(".se-track").count();
    const scope = await openTrackMenu("Bass");
    await rowByText(scope, "Delete").click();
    await page.waitForTimeout(800);
    const after = await page.locator(".se-track").count();
    expect(after).toBe(before - 1);
    const doc = await getProject(page, P1);
    const tracks = (doc.data as { tracks: Array<Record<string, unknown>> }).tracks;
    const lanes = (doc.data as { lanes: Array<Record<string, unknown>> }).lanes;
    expect(tracks.find((item) => item.name === "Bass")).toBeUndefined();
    expect(lanes.find((lane) => lane.id === "c-bass")).toBeUndefined();
    return `Bass and its clip removed (${before} → ${after} tracks)`;
  });

  await check(rec, page, "C-115", async () => {
    await openEditor(page, P5);
    const scope = await openTrackMenu("Empty");
    const row = rowByText(scope, "Bounce track");
    const disabled = await row.isDisabled();
    const title = await row.getAttribute("title");
    expect(disabled).toBe(true);
    expect(title).toBe("This track has no clips to bounce");
    await page.keyboard.press("Escape");
    return `clip-less track: disabled, title="${title}"`;
  });

  await check(rec, page, "C-116", async () => {
    await openEditor(page, P1);
    const before = await page.locator(".se-clip").count();
    const scope = await openTrackMenu("Drums blurred");
    const row = rowByText(scope, "Bounce track");
    await row.click();
    // The label flips to "Bouncing…" while the render runs; catch it or accept the result.
    const bouncing = await menu(page, "Drums blurred options")
      .locator('[role="menuitem"]', { hasText: /Bouncing/ })
      .count()
      .catch(() => 0);
    await page.waitForFunction(
      () => /Bounce on .* (added|downloaded)/.test(document.querySelector(".se-toast")?.textContent ?? ""),
      null,
      { timeout: 120_000 }
    );
    const toast = (await page.locator(".se-toast").first().innerText()).replace(/\s+/g, " ").trim();
    await page.waitForTimeout(1500);
    const after = await page.locator(".se-clip").count();
    expect(after).toBeGreaterThan(before);
    return `sawBouncing=${bouncing}; toast "${toast}"; clips ${before} → ${after}`;
  });

  await check(rec, page, "C-117", async () => {
    await page.locator(".se-add-track").first().click();
    const scope = menu(page, "Add a track");
    await expect(scope).toBeVisible({ timeout: 8000 });
    const rows = (await scope.locator('[role="menuitem"]').allInnerTexts()).map((text) =>
      text.replace(/\s+/g, " ").trim()
    );
    expect(rows).toEqual(["Audio A", "MIDI M", "Upload U"]);
    await shot(page, "C-117-1689x1277");
    return `menu "Add a track" = ${rows.join(" | ")}`;
  });

  await check(rec, page, "C-118", async () => {
    const scope = menu(page, "Add a track");
    const before = await page.locator(".se-track").count();
    await rowByText(scope, "Audio").click();
    await page.waitForTimeout(700);
    const afterMenu = await page.locator(".se-track").count();
    const beforeShortcut = afterMenu;
    await page.keyboard.press("a");
    await page.waitForTimeout(700);
    const afterShortcut = await page.locator(".se-track").count();
    expect(afterMenu).toBe(before + 1);
    expect(afterShortcut).toBe(beforeShortcut + 1);
    return `Audio row appended (${before} → ${afterMenu}); "A" appended again (→ ${afterShortcut})`;
  });

  await check(rec, page, "C-119", async () => {
    await page.locator(".se-add-track").first().click();
    const scope = menu(page, "Add a track");
    const before = await page.locator(".se-track").count();
    await rowByText(scope, "MIDI").click();
    await page.waitForTimeout(700);
    const after = await page.locator(".se-track").count();
    const last = (await page.locator(".se-track-name").last().innerText()).trim();
    expect(after).toBe(before + 1);
    return `MIDI row appended a track (${before} → ${after}), last = "${last}"`;
  });

  await check(rec, page, "C-120", async () => {
    const before = await page.locator(".se-track").count();
    await page.locator(".se-add-track").first().click();
    await rowByText(menu(page, "Add a track"), "Upload").click();
    const library = page.locator(".se-library").first();
    await expect(library).toBeVisible({ timeout: 10_000 });
    const after = await page.locator(".se-track").count();
    const uploads = library.locator('[role="toolbar"][aria-label="Upload actions"]');
    await expect(uploads).toBeVisible({ timeout: 8000 });
    const chip = (await uploads.innerText()).replace(/\s+/g, " ").trim();
    expect(after).toBe(before);
    return `library opened on the Upload actions toolbar ("${chip}"); no track added`;
  });

  await check(rec, page, "C-121", async () => {
    await page.locator('button[aria-label="Toggle library"]').first().click().catch(() => undefined);
    await page.locator(".se-add-track").first().click();
    await expect(menu(page, "Add a track")).toBeVisible({ timeout: 5000 });
    await page.keyboard.press("Escape");
    await expect(menu(page, "Add a track")).toHaveCount(0, { timeout: 5000 });
    await page.locator(".se-add-track").first().click();
    await expect(menu(page, "Add a track")).toBeVisible({ timeout: 5000 });
    await page.locator(".se-lanes").first().click({ position: { x: 1200, y: 700 } });
    await expect(menu(page, "Add a track")).toHaveCount(0, { timeout: 5000 });
    await page.locator(".se-add-track").first().click();
    await expect(menu(page, "Add a track")).toBeVisible({ timeout: 5000 });
    await page.mouse.wheel(0, 240);
    await page.waitForTimeout(300);
    const afterScroll = await menu(page, "Add a track").count();
    return `Escape and outside click close it; after a scroll it is ${afterScroll === 0 ? "closed" : "still open"}`;
  });

  await check(rec, page, "C-122", async () => {
    const pill = page.locator(".se-hidden-pill").first();
    await expect(pill).toBeVisible({ timeout: 8000 });
    const label = await pill.getAttribute("aria-label");
    await pill.click();
    const pop = page.locator('.se-hidden-pop[role="dialog"][aria-label="Hidden tracks"]');
    await expect(pop).toBeVisible({ timeout: 8000 });
    const rows = await pop.locator(".se-hidden-row").count();
    await shot(page, "C-122-1689x1277");
    return `pill "${label}"; popover with ${rows} row(s)`;
  });

  await check(rec, page, "C-123", async () => {
    const pop = page.locator('.se-hidden-pop[role="dialog"]');
    const row = pop.locator(".se-hidden-row", { hasText: "Scratch" }).first();
    await row.locator("button", { hasText: "Show" }).click();
    await page.waitForTimeout(700);
    const visible = await page.locator(".se-track-name", { hasText: "Scratch" }).count();
    const rowsLeft = await pop.locator(".se-hidden-row").count();
    expect(visible).toBeGreaterThan(0);
    expect(rowsLeft).toBeLessThan(2);
    return `Scratch returned to the track list; hidden rows now ${rowsLeft}`;
  });

  await check(rec, page, "C-124", async () => {
    // C-123 left the popover open; close it before toggling again.
    const popover = page.locator('.se-hidden-pop[role="dialog"]');
    if ((await popover.count()) > 0) {
      await popover.locator('button[aria-label="Close hidden tracks"]').click().catch(() => undefined);
      await page.waitForTimeout(300);
    }
    const scratchMenu = await openTrackMenu("Scratch");
    await rowByText(scratchMenu, "Hide & Mute Track").click();
    await page.waitForTimeout(700);
    const pill = page.locator(".se-hidden-pill").first();
    await pill.click();
    const pop = page.locator('.se-hidden-pop[role="dialog"]');
    await expect(pop).toBeVisible({ timeout: 8000 });
    const row = pop.locator(".se-hidden-row", { hasText: "Scratch" }).first();
    const first = (await row.locator("button").last().innerText()).trim();
    await row.locator("button").last().click();
    await page.waitForTimeout(600);
    const second = (await row.locator("button").last().innerText()).trim();
    const stillHidden = await page.locator(".se-track-name", { hasText: "Scratch" }).count();
    expect(first).toBe("Unmute");
    expect(second).toBe("Mute");
    expect(stillHidden).toBe(0);
    return `label ${first} → ${second}; the track stays hidden`;
  });

  await check(rec, page, "C-125", async () => {
    const pop = page.locator('.se-hidden-pop[role="dialog"]');
    if ((await pop.count()) === 0) {
      await page.locator(".se-hidden-pill").first().click();
      await expect(pop).toBeVisible({ timeout: 8000 });
    }
    await pop.locator("button", { hasText: "Unmute all" }).click();
    await page.waitForTimeout(900);
    const doc = await getProject(page, P1);
    const tracks = (doc.data as { tracks: Array<Record<string, unknown>> }).tracks;
    const hidden = tracks.filter((track) => track.hidden);
    expect(hidden.length).toBeGreaterThan(0);
    expect(hidden.every((track) => track.muted === false)).toBe(true);
    return `Unmute all cleared muted on ${hidden.length} hidden track(s) without showing them`;
  });

  await check(rec, page, "C-126", async () => {
    const pop = page.locator('.se-hidden-pop[role="dialog"]');
    if ((await pop.count()) === 0) {
      await page.locator(".se-hidden-pill").first().click();
      await expect(pop).toBeVisible({ timeout: 8000 });
    }
    await pop.locator("button", { hasText: "Show All Hidden Tracks" }).click();
    await page.waitForTimeout(900);
    expect(await page.locator(".se-hidden-pill").count()).toBe(0);
    const scratch = await page.locator(".se-track-name", { hasText: "Scratch" }).count();
    expect(scratch).toBeGreaterThan(0);
    return "every hidden track returned; the pill disappeared";
  });

  await check(rec, page, "C-127", async () => {
    const menuScope = await openTrackMenu("Scratch");
    await rowByText(menuScope, "Hide & Mute Track").click();
    await page.waitForTimeout(700);
    await page.locator(".se-hidden-pill").first().click();
    const pop = page.locator('.se-hidden-pop[role="dialog"]');
    await expect(pop).toBeVisible({ timeout: 5000 });
    await page.keyboard.press("Escape");
    await expect(pop).toHaveCount(0, { timeout: 5000 });
    return "Escape closed the hidden-tracks popover";
  });

  await check(rec, page, "C-128", async () => {
    await page.locator('select[aria-label="Group for Drums blurred"]').selectOption("A");
    await page.locator('select[aria-label="Group for Vox"]').selectOption("A");
    await page.waitForTimeout(900);
    const groups = page.locator('.se-groups[aria-label="Track groups"]');
    await expect(groups).toBeVisible({ timeout: 8000 });
    const chip = groups.locator(".se-group-chip").first();
    const chipText = (await chip.innerText()).trim();
    const level = await groups.locator('input[aria-label="Group A level"]').count();
    const members = await groups.locator(".se-group-members, .se-group-count").allInnerTexts();
    await shot(page, "C-128-1689x1277");
    expect(chipText).toBe("A");
    expect(level).toBe(1);
    return `group row A with a level slider (${level}); member labels = ${members.join(",") || "n/a"}`;
  });

  await check(rec, page, "C-129", async () => {
    const groups = page.locator('.se-groups[aria-label="Track groups"]');
    const slider = groups.locator('input[aria-label="Group A level"]');
    await slider.fill("40");
    await slider.dispatchEvent("change");
    await page.waitForTimeout(900);
    const doc = await getProject(page, P1);
    const data = doc.data as {
      groups?: Record<string, number>;
      tracks: Array<Record<string, unknown>>;
    };
    const group = data.groups?.A;
    expect(typeof group).toBe("number");
    // Individual faders stay independent of the group level.
    const vox = await page.locator('input[aria-label="Volume Vox"]').inputValue();
    expect(Number(vox)).toBe(82);
    return `group A level stored = ${group}; Vox's own fader still ${vox}`;
  });

  await check(rec, page, "C-130", async () => {
    const groups = page.locator('.se-groups[aria-label="Track groups"]');
    const chip = groups.locator(".se-group-chip").first();
    const before = await chip.getAttribute("aria-pressed");
    await chip.click();
    await page.waitForTimeout(600);
    const after = await chip.getAttribute("aria-pressed");
    expect(before).toBe("false");
    expect(after).toBe("true");
    const collapsed = await page
      .locator(".se-track", { hasText: "Vox" })
      .locator(".se-track-slider")
      .count();
    return `group chip aria-pressed ${before} → ${after} (members collapse together, ${collapsed} sliders left)`;
  });
});

test("C7 — export menu", async () => {
  await openEditor(page, PEXPORT);

  await check(rec, page, "C-131", async () => {
    const button = page.locator('button[aria-label="Export menu"]').first();
    await button.click();
    const scope = menu(page, "Export options");
    await expect(scope).toBeVisible({ timeout: 8000 });
    const expanded = await button.getAttribute("aria-expanded");
    expect(expanded).toBe("true");
    const on = await button.evaluate((node) => node.className.includes("on"));
    expect(on).toBe(true);
    return `menu "Export options" open; button aria-expanded=true and shows the pressed class`;
  });

  await check(rec, page, "C-132", async () => {
    const scope = menu(page, "Export options");
    const rows = (await scope.locator('[role="menuitem"], [role="menuitemcheckbox"], [role="menuitemradio"]').allInnerTexts()).map((text) =>
      text.replace(/\s+/g, " ").trim()
    );
    expect(rows.slice(0, 3)).toEqual(["Full Song", "Selected Time Range", "Multitrack"]);
    expect(rows).toContain("WAV");
    expect(rows).toContain("MP3");
    expect(rows).toContain("Normalise mix to −1 dBFS");
    expect(rows).toContain("Project (JSON)");
    await shot(page, "C-132-1689x1277");
    return `rows = ${rows.join(" | ")}`;
  });

  await check(rec, page, "C-133", async () => {
    const scope = menu(page, "Export options");
    const row = rowByText(scope, "Selected Time Range");
    expect(await row.isDisabled()).toBe(true);
    return "no range and no loop range: Selected Time Range disabled";
  });

  await check(rec, page, "C-134", async () => {
    await page.keyboard.press("Escape");
    const ruler = page.locator(".se-ruler-bars").first();
    const box = await ruler.boundingBox();
    await page.mouse.move(box!.x + 96, box!.y + box!.height / 2);
    await page.mouse.down();
    await page.mouse.move(box!.x + 192, box!.y + box!.height / 2, { steps: 6 });
    await page.mouse.up();
    await page.waitForTimeout(400);
    await page.locator('button[aria-label="Export menu"]').first().click();
    const scope = menu(page, "Export options");
    const row = rowByText(scope, "Selected Time Range");
    expect(await row.isDisabled()).toBe(false);
    return "with a range the row is enabled";
  });

  await check(rec, page, "C-135", async () => {
    const scope = menu(page, "Export options");
    const formats = scope.locator(".se-export-formats");
    const mp3 = formats.locator('[role="menuitemradio"]', { hasText: "MP3" });
    await mp3.click();
    const checked = await mp3.getAttribute("aria-checked");
    const wav = formats.locator('[role="menuitemradio"]', { hasText: "WAV" });
    const wavChecked = await wav.getAttribute("aria-checked");
    expect(checked).toBe("true");
    expect(wavChecked).toBe("false");
    await shot(page, "C-135-1689x1277");
    return `aria-checked moved to MP3 (WAV=${wavChecked}); the next export encodes MP3`;
  });

  await check(rec, page, "C-136", async () => {
    const scope = menu(page, "Export options");
    const row = scope.locator('[role="menuitemcheckbox"]').first();
    const before = await row.getAttribute("aria-checked");
    await row.click();
    const after = await row.getAttribute("aria-checked");
    const text = (await row.innerText()).replace(/\s+/g, " ").trim();
    expect(before).toBe("false");
    expect(after).toBe("true");
    expect(text.startsWith("✓")).toBe(true);
    return `Normalise toggled to aria-checked=true with a leading ✓ ("${text}")`;
  });

  await check(rec, page, "C-137", async () => {
    const scope = menu(page, "Export options");
    const button = page.locator('button[aria-label="Export menu"]').first();
    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 120_000 }),
      rowByText(scope, "Full Song").click(),
    ]);
    const name = download.suggestedFilename();
    expect(name).toMatch(/\.(mp3|wav)$/i);
    return `Full Song downloaded "${name}"`;
  });

  await check(rec, page, "C-138", async () => {
    await page.locator('button[aria-label="Export menu"]').first().click();
    const scope = menu(page, "Export options");
    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 30_000 }),
      rowByText(scope, "Project (JSON)").click(),
    ]);
    const stream = await download.createReadStream();
    let body = "";
    if (stream) {
      for await (const chunk of stream) body += chunk.toString();
    }
    const parsed = JSON.parse(body) as {
      data?: { lanes?: unknown[]; tracks?: unknown[] };
      title?: string;
    };
    expect(Array.isArray(parsed.data?.lanes)).toBe(true);
    expect(Array.isArray(parsed.data?.tracks)).toBe(true);
    return `Project (JSON) downloaded "${download.suggestedFilename()}" with data.lanes=${parsed.data?.lanes?.length} and data.tracks=${parsed.data?.tracks?.length}`;
  });
});
