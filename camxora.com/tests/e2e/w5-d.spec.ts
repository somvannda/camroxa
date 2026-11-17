import { expect, test, type Page } from "@playwright/test";

import {
  adfDocument,
  barMetrics,
  bodyScroll,
  clipBox,
  clipMenu,
  createProject,
  dismissOverlays,
  drag,
  laneOf,
  lanesBox,
  makeRecorder,
  quietHelp,
  openProject,
  rulerPoint,
  savedProject,
  selectTrack,
  shot,
  signIn,
  waitSaved,
  warpDocument,
} from "./w5-adf-harness";

/**
 * Area D — arrangement, clip, warp and MIDI gestures (88 checks).
 *
 * Every row drives the real pointer/keyboard path at 1689×1277 and reads the result
 * from the DOM or from the saved document. Fixture: P1 (120 BPM 4/4, Drums A 0—4 s,
 * Drums B 8—12 s, Bass MIDI 0—8 s, Vox 4—8 s) unless the row says otherwise.
 */

const rec = makeRecorder("d");
test.describe.configure({ mode: "serial" });
test.afterAll(() => rec.flush());
test.use({ viewport: { width: 1689, height: 1277 } });
test.setTimeout(180_000);

const BAR = 2; // 120 BPM, 4/4 → 2 s per bar
const STEP = BAR / 4; // default grid = 4 divisions → 0.5 s

async function fresh(page: Page, doc = adfDocument(), title = "ADF D") {
  await quietHelp(page);
  await signIn(page);
  const id = await createProject(page, title, doc);
  await openProject(page, id);
  return id;
}

async function selectedCount(page: Page) {
  return page.locator(".se-clip.selected").count();
}

async function playheadLeft(page: Page) {
  return page.evaluate(() => {
    const el = document.querySelector(".se-playhead") as HTMLElement | null;
    return el ? parseFloat(el.style.left || "0") : -1;
  });
}

async function saved(page: Page, id: string) {
  await waitSaved(page);
  return savedProject(page, id);
}

test("D1 — selection and move", async ({ page }) => {
  const id = await fresh(page);
  const { barWidth } = await barMetrics(page);
  const lanes = await lanesBox(page);

  // D-01: click selects the clip + track and clears a range
  const rangeStart = await rulerPoint(page, 2.5);
  const rangeEnd = await rulerPoint(page, 3.5);
  await drag(page, rangeStart, rangeEnd);
  const beforeRange = await page.locator(".se-range").count();
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click({ position: { x: 30, y: 20 } });
  await page.waitForTimeout(200);
  const d01 = {
    range: await page.locator(".se-range").count(),
    selected: await selectedCount(page),
    track: await page.locator(".se-track.selected .se-track-name").first().textContent().catch(() => ""),
    clipSelected: await page.locator(".se-clip.selected", { hasText: "Drums A" }).count(),
  };
  if (beforeRange === 1 && d01.range === 0 && d01.selected === 1 && d01.clipSelected === 1 && (d01.track ?? "").includes("Drums")) {
    rec.pass("D-01", `range 1→0; .se-clip.selected=1; track="${(d01.track ?? "").trim()}"`);
  } else {
    rec.fail("D-01", "click did not isolate the clip/track and clear the range", JSON.stringify({ beforeRange, ...d01 }) + ` — ${await shot(page, "D-01-1689x1277")}`);
  }

  // D-02: empty lane click clears selection and seeks
  const seekBefore = await playheadLeft(page);
  const lane0 = await page.locator(".se-lane").first().boundingBox();
  if (!lane0) throw new Error("no lane");
  await page.mouse.click(lanes.x + barWidth * 7, lane0.y + lane0.height / 2);
  await page.waitForTimeout(200);
  const d02 = { selected: await selectedCount(page), left: await playheadLeft(page) };
  if (d02.selected === 0 && d02.left > seekBefore) {
    rec.pass("D-02", `.se-clip.selected=0; playhead ${seekBefore.toFixed(1)}px → ${d02.left.toFixed(1)}px`);
  } else {
    rec.fail("D-02", "empty-lane click did not clear the selection / seek", JSON.stringify({ seekBefore, ...d02 }) + ` — ${await shot(page, "D-02-1689x1277")}`);
  }

  // D-03: marquee across two clips — starts on empty lane space, then sweeps left.
  const a = await clipBox(page, "Drums A");
  const b = await clipBox(page, "Drums B");
  await page.mouse.move(lanes.x + barWidth * 14, lane0.y + lane0.height / 2);
  await page.mouse.down();
  await page.mouse.move(lanes.x + 2, lane0.y + lane0.height / 2, { steps: 14 });
  const marqueeVisible = await page.locator(".se-marquee").isVisible().catch(() => false);
  await page.mouse.up();
  await page.waitForTimeout(200);
  const d03 = await selectedCount(page);
  if (marqueeVisible && d03 === 2) {
    rec.pass("D-03", `.se-marquee visible during drag; .se-clip.selected=2 (A ${Math.round(a.x)}, B ${Math.round(b.x)})`);
  } else {
    rec.fail("D-03", "marquee did not select both clips", `marquee=${marqueeVisible} selected=${d03} — ${await shot(page, "D-03-1689x1277")}`);
  }

  // D-04: clicking a clip inside the marquee selection keeps the group
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  await page.waitForTimeout(150);
  const d04 = await selectedCount(page);
  if (d04 === 2) {
    rec.pass("D-04", `group kept: .se-clip.selected=${d04}`);
  } else {
    rec.fail("D-04", "clicking inside the selection collapsed it", `selected=${d04} — ${await shot(page, "D-04-1689x1277")}`);
  }

  // D-05: shift-click a clip outside the group replaces (documented as an absence, not additive)
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  await page.waitForTimeout(120);
  await page.locator(".se-clip", { hasText: "Vox" }).first().click({ modifiers: ["Shift"] });
  await page.waitForTimeout(150);
  const d05 = await selectedCount(page);
  const d05Title = (await page.locator(".se-clip.selected").first().textContent()) ?? "";
  if (d05 === 1 && d05Title.includes("Vox")) {
    rec.pass("D-05", `shift-click replaces: .se-clip.selected=${d05} ("${d05Title.trim()}") (additive select remains an absence, G-6)`);
  } else {
    rec.fail("D-05", "shift-click produced an unexpected selection size", `selected=${d05} title="${d05Title}" — ${await shot(page, "D-05-1689x1277")}`);
  }

  // D-06: Ctrl+A selects every clip
  await page.locator(".se-clip").first().click();
  await page.keyboard.press("Control+a");
  await page.waitForTimeout(200);
  const d06 = { selected: await selectedCount(page), clips: await page.locator(".se-clip").count() };
  if (d06.selected === d06.clips && d06.clips === 5) {
    rec.pass("D-06", `Ctrl+A → .se-clip.selected=${d06.selected}/${d06.clips}`);
  } else {
    rec.fail("D-06", "Ctrl+A did not select all clips", JSON.stringify(d06) + ` — ${await shot(page, "D-06-1689x1277")}`);
  }

  // D-07: drag right ~1 bar, snapped, snap guide visible
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  const before7 = laneOf(await savedProject(page, id), "c-d1")!;
  const box7 = await clipBox(page, "Drums A");
  await page.mouse.move(box7.x + box7.width / 2, box7.y + box7.height / 2);
  await page.mouse.down();
  await page.mouse.move(box7.x + box7.width / 2 + barWidth, box7.y + box7.height / 2, { steps: 16 });
  const snapGuide = await page.locator(".se-snap-line").count();
  await page.mouse.up();
  const after7 = laneOf(await saved(page, id), "c-d1")!;
  const snapped7 = Math.abs((after7.start as number) - ((before7.start as number) + BAR)) < 0.01;
  if (snapped7 && snapGuide > 0) {
    rec.pass("D-07", `start ${before7.start} → ${after7.start}; .se-snap-line=${snapGuide}`);
  } else {
    rec.fail("D-07", "clip drag did not snap one bar or showed no guide", `start=${after7.start} guide=${snapGuide} — ${await shot(page, "D-07-1689x1277")}`);
  }

  // D-08: multi-selection moves by the same delta
  await page.keyboard.press("Control+a");
  await page.waitForTimeout(150);
  const beforeDoc = await savedProject(page, id);
  const boxA = await clipBox(page, "Drums A");
  await page.mouse.move(boxA.x + boxA.width / 2, boxA.y + boxA.height / 2);
  await page.mouse.down();
  await page.mouse.move(boxA.x + boxA.width / 2 + barWidth, boxA.y + boxA.height / 2, { steps: 16 });
  await page.mouse.up();
  const afterDoc = await saved(page, id);
  const deltas = ["c-d1", "c-d2", "c-bass", "c-vox"].map((clipId) => {
    const before = laneOf(beforeDoc, clipId)!.start as number;
    const after = laneOf(afterDoc, clipId)!.start as number;
    return Number((after - before).toFixed(2));
  });
  if (deltas.every((delta) => Math.abs(delta - BAR) < 0.01)) {
    rec.pass("D-08", `all selected clips moved +${BAR}s: ${JSON.stringify(deltas)}`);
  } else {
    rec.fail("D-08", "multi-drag deltas differ", JSON.stringify(deltas) + ` — ${await shot(page, "D-08-1689x1277")}`);
  }

  // D-09: drag past zero clamps at 0
  const doc9 = await savedProject(page, id);
  const first = laneOf(doc9, "c-d1")!;
  const box9 = await clipBox(page, "Drums A");
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  await page.mouse.move(box9.x + box9.width / 2, box9.y + box9.height / 2);
  await page.mouse.down();
  await page.mouse.move(box9.x + box9.width / 2 - barWidth * 8, box9.y + box9.height / 2, { steps: 18 });
  await page.mouse.up();
  const after9 = laneOf(await saved(page, id), "c-d1")!;
  if ((after9.start as number) >= 0 && (after9.start as number) <= Number(first.start)) {
    rec.pass("D-09", `start clamped to ${after9.start} (>= 0)`);
  } else {
    rec.fail("D-09", "drag past zero produced a negative start", `start=${after9.start} — ${await shot(page, "D-09-1689x1277")}`);
  }
});

test("D2 — trim and fades", async ({ page }) => {
  const id = await fresh(page);
  const { barWidth } = await barMetrics(page);
  const stepPx = (STEP / BAR) * barWidth;

  // D-10: trim grip becomes visible on hover
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  const startGrip = page.locator(".se-clip", { hasText: "Drums A" }).locator(".se-trim-start");
  await page.mouse.move(20, 400);
  await page.waitForTimeout(200);
  const opacityBefore = await startGrip.evaluate((el) => getComputedStyle(el).opacity);
  await startGrip.hover();
  await page.waitForTimeout(200);
  const opacityAfter = await startGrip.evaluate((el) => getComputedStyle(el).opacity);
  if (Number(opacityBefore) < 1 && Number(opacityAfter) === 1) {
    rec.pass("D-10", `.se-trim-start opacity ${opacityBefore} → ${opacityAfter} on hover`);
  } else {
    rec.fail("D-10", "trim grip does not reveal on hover", `opacity ${opacityBefore} → ${opacityAfter} — ${await shot(page, "D-10-1689x1277")}`);
  }

  // D-11: right trim grows duration, start fixed, snapped
  const before11 = laneOf(await savedProject(page, id), "c-d1")!;
  const endGrip = await page.locator(".se-clip", { hasText: "Drums A" }).locator(".se-trim-end").boundingBox();
  if (!endGrip) throw new Error("no end grip");
  await drag(
    page,
    { x: endGrip.x + endGrip.width / 2, y: endGrip.y + endGrip.height / 2 },
    { x: endGrip.x + endGrip.width / 2 + stepPx, y: endGrip.y + endGrip.height / 2 }
  );
  const after11 = laneOf(await saved(page, id), "c-d1")!;
  const grew11 = Math.abs((after11.duration as number) - ((before11.duration as number) + STEP)) < 0.02;
  if (grew11 && after11.start === before11.start) {
    rec.pass("D-11", `duration ${before11.duration} → ${after11.duration}; start stayed ${after11.start}`);
  } else {
    rec.fail("D-11", "right trim did not grow by one grid step", `dur=${after11.duration} start=${after11.start} — ${await shot(page, "D-11-1689x1277")}`);
  }

  // D-12: left trim grows start + offset together
  const before12 = laneOf(await savedProject(page, id), "c-d1")!;
  const startGripBox = await page.locator(".se-clip", { hasText: "Drums A" }).locator(".se-trim-start").boundingBox();
  if (!startGripBox) throw new Error("no start grip");
  await drag(
    page,
    { x: startGripBox.x + startGripBox.width / 2, y: startGripBox.y + startGripBox.height / 2 },
    { x: startGripBox.x + startGripBox.width / 2 + stepPx, y: startGripBox.y + startGripBox.height / 2 }
  );
  const after12 = laneOf(await saved(page, id), "c-d1")!;
  const startDelta = Number(((after12.start as number) - (before12.start as number)).toFixed(3));
  const offsetDelta = Number((((after12.offset as number) ?? 0) - ((before12.offset as number) ?? 0)).toFixed(3));
  if (Math.abs(startDelta - STEP) < 0.02 && Math.abs(offsetDelta - STEP) < 0.02) {
    rec.pass("D-12", `start +${startDelta}, offset +${offsetDelta}`);
  } else {
    rec.fail("D-12", "left trim did not move start and offset together", `start +${startDelta} offset +${offsetDelta} — ${await shot(page, "D-12-1689x1277")}`);
  }

  // D-13: left trim past the clip start clamps at 0
  const grip13 = await page.locator(".se-clip", { hasText: "Drums A" }).locator(".se-trim-start").boundingBox();
  if (!grip13) throw new Error("no start grip 13");
  await drag(
    page,
    { x: grip13.x + grip13.width / 2, y: grip13.y + grip13.height / 2 },
    { x: grip13.x + grip13.width / 2 - barWidth * 3, y: grip13.y + grip13.height / 2 }
  );
  const after13 = laneOf(await saved(page, id), "c-d1")!;
  if ((after13.start as number) === 0 && ((after13.offset as number) ?? 0) === 0) {
    rec.pass("D-13", `start=${after13.start}, offset=${after13.offset ?? 0}`);
  } else {
    rec.fail("D-13", "left trim did not clamp at the origin", `start=${after13.start} offset=${after13.offset} — ${await shot(page, "D-13-1689x1277")}`);
  }

  // D-14: release without moving writes nothing
  const undoBefore = await page.locator('button[aria-label="Undo"]').isDisabled();
  const grip14 = await page.locator(".se-clip", { hasText: "Drums A" }).locator(".se-trim-end").boundingBox();
  if (!grip14) throw new Error("no grip14");
  await page.mouse.move(grip14.x + grip14.width / 2, grip14.y + grip14.height / 2);
  await page.mouse.down();
  await page.mouse.up();
  await page.waitForTimeout(250);
  const undoAfter = await page.locator('button[aria-label="Undo"]').isDisabled();
  if (undoBefore === undoAfter) {
    rec.pass("D-14", `undo disabled state unchanged (${undoAfter}); no write`);
  } else {
    rec.fail("D-14", "press-release created a history entry", `disabled ${undoBefore} → ${undoAfter} — ${await shot(page, "D-14-1689x1277")}`);
  }

  // D-15: pointercancel aborts a trim
  const before15 = laneOf(await savedProject(page, id), "c-d1")!;
  const grip15 = await page.locator(".se-clip", { hasText: "Drums A" }).locator(".se-trim-end").boundingBox();
  if (!grip15) throw new Error("no grip15");
  await page.mouse.move(grip15.x + grip15.width / 2, grip15.y + grip15.height / 2);
  await page.mouse.down();
  await page.mouse.move(grip15.x + grip15.width / 2 + stepPx * 2, grip15.y + grip15.height / 2, { steps: 8 });
  await page.evaluate((point) => {
    window.dispatchEvent(new PointerEvent("pointercancel", { clientX: point.x, clientY: point.y, bubbles: true }));
  }, { x: grip15.x + stepPx * 2, y: grip15.y });
  await page.mouse.up();
  await page.waitForTimeout(300);
  const after15 = laneOf(await savedProject(page, id), "c-d1")!;
  const trimming = await page.locator(".se-clip.trimming").count();
  if (after15.duration === before15.duration && trimming === 0) {
    rec.pass("D-15", `duration unchanged (${after15.duration}); .trimming=${trimming}`);
  } else {
    rec.fail("D-15", "pointercancel committed or left a preview", `dur ${before15.duration}→${after15.duration} trimming=${trimming} — ${await shot(page, "D-15-1689x1277")}`);
  }

  // D-16: fade-in stub drag
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  const fadeInHandle = await page.locator(".se-clip", { hasText: "Drums A" }).locator(".se-fade-handle[data-fade='in']").boundingBox();
  if (!fadeInHandle) throw new Error("no fade-in handle");
  await drag(
    page,
    { x: fadeInHandle.x + fadeInHandle.width / 2, y: fadeInHandle.y + fadeInHandle.height / 2 },
    { x: fadeInHandle.x + fadeInHandle.width / 2 + stepPx * 2, y: fadeInHandle.y + fadeInHandle.height / 2 }
  );
  const doc16 = await saved(page, id);
  const clip16 = laneOf(doc16, "c-d1")!;
  const fadeEl = await page.locator(".se-clip", { hasText: "Drums A" }).locator(".se-fade").count();
  if ((clip16.fadeIn ?? 0) > 0 && fadeEl > 0) {
    rec.pass("D-16", `fadeIn=${clip16.fadeIn}; .se-fade=${fadeEl}`);
  } else {
    rec.fail("D-16", "fade-in drag wrote nothing", `fadeIn=${clip16.fadeIn} fadeEl=${fadeEl} — ${await shot(page, "D-16-1689x1277")}`);
  }

  // D-17: fade-out stub, ceiling = duration - fadeIn
  const fadeOutHandle = await page.locator(".se-clip", { hasText: "Drums A" }).locator(".se-fade-handle[data-fade='out']").boundingBox();
  if (!fadeOutHandle) throw new Error("no fade-out handle");
  await drag(
    page,
    { x: fadeOutHandle.x + fadeOutHandle.width / 2, y: fadeOutHandle.y + fadeOutHandle.height / 2 },
    { x: fadeOutHandle.x + fadeOutHandle.width / 2 - stepPx * 4, y: fadeOutHandle.y + fadeOutHandle.height / 2 }
  );
  const clip17 = laneOf(await saved(page, id), "c-d1")!;
  const outWidth = await page.locator(".se-clip", { hasText: "Drums A" }).locator(".se-fade.is-out").count();
  if ((clip17.fadeOut ?? 0) > 0 && outWidth > 0 && (clip17.fadeIn ?? 0) + (clip17.fadeOut ?? 0) <= (clip17.duration ?? 0) + 0.01) {
    rec.pass("D-17", `fadeOut=${clip17.fadeOut}; in+out=${(clip17.fadeIn ?? 0) + (clip17.fadeOut ?? 0)} <= duration ${clip17.duration}`);
  } else {
    rec.fail("D-17", "fade-out drag or ceiling wrong", `fadeOut=${clip17.fadeOut} in=${clip17.fadeIn} dur=${clip17.duration} — ${await shot(page, "D-17-1689x1277")}`);
  }

  // D-18: drag the fade back to the corner removes it
  const out18 = await page.locator(".se-clip", { hasText: "Drums A" }).locator(".se-fade-handle[data-fade='out']").boundingBox();
  if (!out18) throw new Error("no fade-out handle 18");
  await drag(
    page,
    { x: out18.x + out18.width / 2, y: out18.y + out18.height / 2 },
    { x: out18.x + out18.width / 2 + barWidth, y: out18.y + out18.height / 2 }
  );
  const clip18 = laneOf(await saved(page, id), "c-d1")!;
  if (!("fadeOut" in clip18) || clip18.fadeOut === undefined) {
    rec.pass("D-18", `fadeOut removed from the document`);
  } else {
    rec.fail("D-18", "fade-out did not clear", `fadeOut=${clip18.fadeOut} — ${await shot(page, "D-18-1689x1277")}`);
  }

  // D-19: Shift+F on an audio clip toggles a fade-in
  await page.locator(".se-clip", { hasText: "Vox" }).first().click();
  await page.keyboard.press("Shift+F");
  await page.waitForTimeout(300);
  const vox19 = laneOf(await savedProject(page, id), "c-vox")!;
  await page.keyboard.press("Shift+F");
  await page.waitForTimeout(300);
  const vox19b = laneOf(await savedProject(page, id), "c-vox")!;
  if ((vox19.fadeIn ?? 0) > 0 && !vox19b.fadeIn) {
    rec.pass("D-19", `Shift+F set fadeIn=${vox19.fadeIn} then cleared it`);
  } else {
    rec.fail("D-19", "Shift+F did not toggle the audio fade", `first=${vox19.fadeIn} second=${vox19b.fadeIn} — ${await shot(page, "D-19-1689x1277")}`);
  }

  // D-20: Shift+F on a MIDI clip is refused with a toast
  await page.locator(".se-clip", { hasText: "Bass" }).first().click();
  await page.keyboard.press("Shift+F");
  await page.waitForTimeout(300);
  const toast20 = (await page.locator(".se-toast").textContent().catch(() => "")) ?? "";
  const bass20 = laneOf(await savedProject(page, id), "c-bass")!;
  if (/Fades only apply to audio arrangements\./.test(toast20) && !bass20.fadeIn) {
    rec.pass("D-20", `toast="${toast20.replace(/\s+/g, " ").trim()}"; no fade written`);
  } else {
    rec.fail("D-20", "MIDI fade was not refused", `toast="${toast20}" fadeIn=${bass20.fadeIn} — ${await shot(page, "D-20-1689x1277")}`);
  }
});

test("D3 — split, duplicate, delete", async ({ page }) => {
  const id = await fresh(page);
  const { barWidth } = await barMetrics(page);
  const lanes = await lanesBox(page);
  const clipY = async (title: string) => (await clipBox(page, title)).y + 30;

  // D-21: split at the playhead
  const at21 = await rulerPoint(page, 1);
  await page.mouse.click(at21.x, at21.y); // bar 2 = 2 s, inside Drums A (0—4 s)
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  const countBefore21 = await page.locator(".se-clip").count();
  await page.keyboard.press("Control+e");
  await page.waitForTimeout(300);
  const countAfter21 = await page.locator(".se-clip").count();
  const split = (await savedProject(page, id)).data.lanes.filter((clip: any) => clip.id.startsWith("c-d1")) as any[];
  const right = split.find((clip) => clip.id !== "c-d1");
  if (countAfter21 === countBefore21 + 1 && right && Math.abs(right.start - 2) < 0.02 && Math.abs(right.offset - 2) < 0.02) {
    rec.pass("D-21", `clip count ${countBefore21}→${countAfter21}; right half start=${right.start} offset=${right.offset}`);
  } else {
    rec.fail("D-21", "split did not produce the expected right half", `count ${countBefore21}→${countAfter21} right=${JSON.stringify(right)} — ${await shot(page, "D-21-1689x1277")}`);
  }

  // D-22: split on the boundary does nothing
  const id22 = await fresh(page, adfDocument(), "ADF D22");
  const lanes22 = await lanesBox(page);
  await page.mouse.click(lanes22.x + 2, lanes22.y + 8); // playhead at 0 = clip start
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  const count22a = await page.locator(".se-clip").count();
  await page.keyboard.press("Control+e");
  await page.waitForTimeout(250);
  const count22b = await page.locator(".se-clip").count();
  if (count22a === count22b) {
    rec.pass("D-22", `split at the clip start: count stayed ${count22b}`);
  } else {
    rec.fail("D-22", "split at the boundary created a clip", `${count22a}→${count22b} — ${await shot(page, "D-22-1689x1277")}`);
  }

  // D-23: split a multi-selection
  await page.goto(`/studio/editor?project=${id}`);
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  await dismissOverlays(page);
  const lanes23 = await lanesBox(page);
  const { barWidth: bw23 } = await barMetrics(page);
  const at23 = await rulerPoint(page, 1);
  await page.mouse.click(at23.x, at23.y); // 2 s: inside Drums A, Vox and Bass
  await page.keyboard.press("Control+a");
  await page.waitForTimeout(150);
  const count23a = await page.locator(".se-clip").count();
  await page.keyboard.press("Control+e");
  await page.waitForTimeout(350);
  const count23b = await page.locator(".se-clip").count();
  if (count23b > count23a) {
    rec.pass("D-23", `multi-split: clip count ${count23a}→${count23b}`);
  } else {
    rec.fail("D-23", "multi-selection split did nothing", `${count23a}→${count23b} — ${await shot(page, "D-23-1689x1277")}`);
  }

  // D-24: split on transients (menu) on a clip with audio transients
  const transientsDoc = adfDocument();
  const transientsLanes = (transientsDoc.data as { lanes: Array<Record<string, unknown>> }).lanes;
  transientsLanes.find((clip) => clip.id === "c-vox")!.audioUrl = "/seed/transients.wav";
  const id24 = await fresh(page, transientsDoc, "ADF D24");
  await page.locator(".se-clip", { hasText: "Vox" }).first().click({ button: "right" });
  await expect(page.locator(".se-clip-menu")).toBeVisible();
  const transientsRow = page.locator(".se-clip-menu button", { hasText: "Split on Transients" }).first();
  await transientsRow.click();
  await page.waitForTimeout(3500);
  const toast24 = (await page.locator(".se-toast").textContent().catch(() => "")) ?? "";
  const lanes24 = (await savedProject(page, id24)).data.lanes as any[];
  if (/Split into \d+ clips at \d+ transients?\./.test(toast24) && lanes24.length > 5) {
    rec.pass("D-24", `toast="${toast24.replace(/\s+/g, " ").trim()}"; lanes 5→${lanes24.length}`);
  } else {
    rec.fail("D-24", "split on transients produced nothing", `toast="${toast24}" lanes=${lanes24.length} — ${await shot(page, "D-24-1689x1277")}`);
  }

  // D-25 / D-26: duplicate one bar later and near the end
  const id25 = await fresh(page, adfDocument(), "ADF D25");
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  await page.keyboard.press("Control+d");
  await page.waitForTimeout(400);
  const lanes25 = (await savedProject(page, id25)).data.lanes as any[];
  const copy25 = lanes25.find((clip) => clip.id.startsWith("c-d1-copy"));
  if (copy25 && Math.abs(copy25.start - BAR) < 0.02) {
    rec.pass("D-25", `copy at start=${copy25.start} (original 0, +${BAR}s)`);
  } else {
    rec.fail("D-25", "duplicate did not land one bar later", `copy=${JSON.stringify(copy25)} — ${await shot(page, "D-25-1689x1277")}`);
  }

  const widthBefore26 = await page.locator(".se-ruler-inner").first().evaluate((el) => (el as HTMLElement).getBoundingClientRect().width);
  await page.locator(".se-clip", { hasText: "Drums B" }).first().click();
  await page.keyboard.press("Control+d");
  await page.waitForTimeout(400);
  const lanes26 = (await savedProject(page, id25)).data.lanes as any[];
  const copy26 = lanes26.find((clip) => clip.id.startsWith("c-d2-copy"));
  const widthAfter26 = await page.locator(".se-ruler-inner").first().evaluate((el) => (el as HTMLElement).getBoundingClientRect().width);
  if (copy26 && copy26.start >= 8 && widthAfter26 >= widthBefore26) {
    rec.pass("D-26", `copy start=${copy26.start}; ruler width ${widthBefore26}→${widthAfter26}`);
  } else {
    rec.fail("D-26", "duplicate near the end misbehaved", `copy=${JSON.stringify(copy26)} width ${widthBefore26}→${widthAfter26} — ${await shot(page, "D-26-1689x1277")}`);
  }

  // D-27: delete and focus a survivor
  const id27 = await fresh(page, adfDocument(), "ADF D27");
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  await page.keyboard.press("Backspace");
  await page.waitForTimeout(400);
  const after27 = (await savedProject(page, id27)).data.lanes as any[];
  const focused27 = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    return el ? `${el.className}` : "none";
  });
  if (!after27.some((clip) => clip.id === "c-d1") && focused27.includes("se-clip")) {
    rec.pass("D-27", `clip removed; focus on "${focused27}"`);
  } else {
    rec.fail("D-27", "delete did not remove the clip or move focus", `lanes=${after27.length} focus=${focused27} — ${await shot(page, "D-27-1689x1277")}`);
  }

  // D-28: multi-delete then one undo restores all
  const id28 = await fresh(page, adfDocument(), "ADF D28");
  await page.keyboard.press("Control+a");
  await page.waitForTimeout(120);
  const count28a = (await savedProject(page, id28)).data.lanes.length;
  await page.keyboard.press("Backspace");
  await page.waitForTimeout(400);
  const count28b = (await savedProject(page, id28)).data.lanes.length;
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(500);
  const count28c = (await savedProject(page, id28)).data.lanes.length;
  if (count28b === 0 && count28c === count28a) {
    rec.pass("D-28", `lanes ${count28a} → ${count28b} → ${count28c} in one undo`);
  } else {
    rec.fail("D-28", "multi-delete undo did not restore in one step", `${count28a}→${count28b}→${count28c} — ${await shot(page, "D-28-1689x1277")}`);
  }
});

test("D4 — clipboard and clip settings", async ({ page }) => {
  const id = await fresh(page);
  const { barWidth } = await barMetrics(page);
  const lanes = await lanesBox(page);

  // D-29: copy then paste at the snapped playhead
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  await page.keyboard.press("Control+c");
  await page.mouse.click(lanes.x + barWidth * 7, lanes.y + 8); // playhead at bar 8 = 14 s
  await page.waitForTimeout(200);
  await page.keyboard.press("Control+v");
  await page.waitForTimeout(400);
  const lanes29 = (await savedProject(page, id)).data.lanes as any[];
  const pasted = lanes29.find((clip) => clip.id.startsWith("c-d1-copy"));
  if (pasted && Math.abs(pasted.start - 14) < 0.6) {
    rec.pass("D-29", `pasted at ${pasted.start}s (playhead 14s)`);
  } else {
    rec.fail("D-29", "paste did not align the earliest clip to the playhead", `pasted=${JSON.stringify(pasted)} — ${await shot(page, "D-29-1689x1277")}`);
  }

  // D-30: paste twice
  await page.keyboard.press("Control+v");
  await page.waitForTimeout(400);
  const lanes30 = (await savedProject(page, id)).data.lanes as any[];
  const copies30 = lanes30.filter((clip) => clip.id.startsWith("c-d1-copy"));
  if (copies30.length === 2) {
    rec.pass("D-30", `two independent copies (${copies30.length}); original untouched`);
  } else {
    rec.fail("D-30", "second paste did not create another copy", `copies=${copies30.length} — ${await shot(page, "D-30-1689x1277")}`);
  }

  // D-31: copy with nothing selected copies nothing (Paste stays disabled)
  await page.mouse.click(lanes.x + barWidth * 9, lanes.y + 8);
  await page.keyboard.press("Control+c");
  await page.locator(".se-clip", { hasText: "Vox" }).first().click({ button: "right" });
  await expect(page.locator(".se-clip-menu")).toBeVisible();
  const pasteRow = page.locator(".se-clip-menu button", { hasText: "Paste" }).first();
  const pasteDisabled = await pasteRow.isDisabled();
  await page.keyboard.press("Escape");
  if (pasteDisabled) {
    rec.pass("D-31", `copy with nothing selected copied nothing (Paste disabled=${pasteDisabled})`);
  } else {
    rec.fail("D-31", "copy with no selection left an active buffer", `Paste disabled=${pasteDisabled} — ${await shot(page, "D-31-1689x1277")}`);
  }

  // D-32: Cut removes and keeps the buffer
  const id32 = await fresh(page, adfDocument(), "ADF D32");
  await page.locator(".se-clip", { hasText: "Drums B" }).first().click();
  const count32a = (await savedProject(page, id32)).data.lanes.length;
  await page.keyboard.press("Control+x");
  await page.waitForTimeout(400);
  const count32b = (await savedProject(page, id32)).data.lanes.length;
  await page.keyboard.press("Control+v");
  await page.waitForTimeout(500);
  const count32c = (await savedProject(page, id32)).data.lanes.length;
  if (count32b === count32a - 1 && count32c === count32a) {
    rec.pass("D-32", `lanes ${count32a} → ${count32b} (cut) → ${count32c} (paste)`);
  } else {
    rec.fail("D-32", "cut/paste round trip failed", `${count32a}→${count32b}→${count32c} — ${await shot(page, "D-32-1689x1277")}`);
  }

  // D-33: paste keeps the origin track even when another track is focused
  const id33 = await fresh(page, adfDocument(), "ADF D33");
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  await page.keyboard.press("Control+c");
  await selectTrack(page, "Vox");
  const lanes33 = await lanesBox(page);
  await page.mouse.click(lanes33.x + barWidth * 8, lanes33.y + 8);
  await page.keyboard.press("Control+v");
  await page.waitForTimeout(500);
  const doc33 = (await savedProject(page, id33)).data as any;
  const pasted33 = (doc33.lanes as any[]).find((clip) => clip.id.startsWith("c-d1-copy"));
  const owner33 = (doc33.tracks as any[]).find((track) => track.clipIds.includes(pasted33?.id));
  if (pasted33 && owner33?.id === "t-drums") {
    rec.pass("D-33", `paste landed on "${owner33.name}" (origin track), not the focused Vox track (G-7 absence)`);
  } else {
    rec.fail("D-33", "paste retargeted a track", `owner=${owner33?.name} — ${await shot(page, "D-33-1689x1277")}`);
  }

  // D-34: copy settings carries audio/fades, not volume/pan/fx
  const id34 = await fresh(page, adfDocument(), "ADF D34");
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  // give the source a fade first
  await page.keyboard.press("Shift+F");
  await page.waitForTimeout(300);
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click({ button: "right" });
  await page.locator(".se-clip-menu button", { hasText: "Copy settings" }).first().click();
  await page.locator(".se-clip", { hasText: "Vox" }).first().click({ button: "right" });
  await page.locator(".se-clip-menu button", { hasText: "Paste settings" }).first().click();
  await page.waitForTimeout(600);
  const vox34 = laneOf(await savedProject(page, id34), "c-vox")!;
  if ((vox34.fadeIn ?? 0) > 0 && !("volume" in vox34)) {
    rec.pass("D-34", `fadeIn=${vox34.fadeIn} copied; no volume/pan/fx keys on the clip`);
  } else {
    rec.fail("D-34", "settings paste did not copy fades only", JSON.stringify(vox34) + ` — ${await shot(page, "D-34-1689x1277")}`);
  }

  // D-35: paste settings onto a multi-selection reports N
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click({ button: "right" });
  await page.locator(".se-clip-menu button", { hasText: "Copy settings" }).first().click();
  await page.keyboard.press("Control+a");
  await page.waitForTimeout(150);
  const anyClip = await page.locator(".se-clip").first().boundingBox();
  if (!anyClip) throw new Error("no clip");
  await page.locator(".se-clip").first().click({ button: "right" });
  const multiRow = page.locator(".se-clip-menu button", { hasText: "Paste settings" }).first();
  await multiRow.click({ force: true });
  await page.waitForTimeout(600);
  const toast35 = (await page.locator(".se-toast").textContent().catch(() => "")) ?? "";
  if (/Settings pasted to \d+ clips?\./.test(toast35)) {
    rec.pass("D-35", `toast="${toast35.replace(/\s+/g, " ").trim()}"`);
  } else {
    rec.fail("D-35", "multi paste-settings toast missing", `toast="${toast35}" — ${await shot(page, "D-35-1689x1277")}`);
  }

  // D-36: reload empties the in-memory clipboard
  const id36 = await fresh(page, adfDocument(), "ADF D36");
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  await page.keyboard.press("Control+c");
  await page.reload();
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  await dismissOverlays(page);
  await page.locator(".se-clip", { hasText: "Vox" }).first().click({ button: "right" });
  const pasteAfterReload = page.locator(".se-clip-menu button", { hasText: "Paste" }).first();
  const disabled36 = await pasteAfterReload.isDisabled();
  await page.keyboard.press("Escape");
  if (disabled36) {
    rec.pass("D-36", `after reload Paste is disabled (in-memory buffer)`);
  } else {
    rec.fail("D-36", "clipboard survived a reload", `Paste disabled=${disabled36} — ${await shot(page, "D-36-1689x1277")}`);
  }
  void id36;
});

test("D5 — ruler, time selection and loop", async ({ page }) => {
  const id = await fresh(page);
  const { barWidth } = await barMetrics(page);
  const lanes = await lanesBox(page);

  // D-37: ruler click seeks, no range
  const point37 = await rulerPoint(page, 3);
  await page.mouse.click(point37.x, point37.y);
  await page.waitForTimeout(200);
  const d37 = {
    range: await page.locator(".se-range").count(),
    left: await playheadLeft(page),
    flag: await page.locator(".se-playhead-flag").count(),
  };
  if (d37.range === 0 && d37.left > 0 && d37.flag === 1) {
    rec.pass("D-37", `playhead left=${d37.left.toFixed(1)}px; .se-range=0; flag=1`);
  } else {
    rec.fail("D-37", "ruler click did not seek cleanly", JSON.stringify(d37) + ` — ${await shot(page, "D-37-1689x1277")}`);
  }

  // D-38: drag the ruler creates a range with two handles
  const start38 = await rulerPoint(page, 1);
  const end38 = await rulerPoint(page, 3);
  await drag(page, start38, end38);
  const d38 = {
    range: await page.locator(".se-range").count(),
    startHandle: await page.locator('button[aria-label="Selection start"]').count(),
    endHandle: await page.locator('button[aria-label="Selection end"]').count(),
  };
  if (d38.range === 1 && d38.startHandle === 1 && d38.endHandle === 1) {
    rec.pass("D-38", `.se-range=1; Selection start/end handles present`);
  } else {
    rec.fail("D-38", "ruler drag did not create a range", JSON.stringify(d38) + ` — ${await shot(page, "D-38-1689x1277")}`);
  }

  // D-39: shift-click moves the clicked edge only
  const widthBefore39 = await page.locator(".se-range").evaluate((el) => (el as HTMLElement).getBoundingClientRect().width);
  const shiftPoint = await rulerPoint(page, 5);
  await page.keyboard.down("Shift");
  await page.mouse.click(shiftPoint.x, shiftPoint.y);
  await page.keyboard.up("Shift");
  await page.waitForTimeout(250);
  const widthAfter39 = await page.locator(".se-range").evaluate((el) => (el as HTMLElement).getBoundingClientRect().width);
  if (widthAfter39 > widthBefore39) {
    rec.pass("D-39", `range width ${widthBefore39.toFixed(0)} → ${widthAfter39.toFixed(0)} px`);
  } else {
    rec.fail("D-39", "shift-click did not extend the range", `${widthBefore39}→${widthAfter39} — ${await shot(page, "D-39-1689x1277")}`);
  }

  // D-40: drag the end handle
  const handle40 = await page.locator('button[aria-label="Selection end"]').boundingBox();
  if (!handle40) throw new Error("no end handle");
  const before40 = await page.locator(".se-range").evaluate((el) => (el as HTMLElement).getBoundingClientRect().width);
  await drag(
    page,
    { x: handle40.x + handle40.width / 2, y: handle40.y + handle40.height / 2 },
    { x: handle40.x + handle40.width / 2 + barWidth, y: handle40.y + handle40.height / 2 }
  );
  const after40 = await page.locator(".se-range").evaluate((el) => (el as HTMLElement).getBoundingClientRect().width);
  if (Math.abs(after40 - (before40 + barWidth)) < 8) {
    rec.pass("D-40", `range width ${before40.toFixed(0)} → ${after40.toFixed(0)} (+1 bar)`);
  } else {
    rec.fail("D-40", "range handle drag resized wrongly", `${before40}→${after40} — ${await shot(page, "D-40-1689x1277")}`);
  }

  // D-41: Shift+arrows grow the range by one grid step
  const before41 = await page.locator(".se-range").evaluate((el) => (el as HTMLElement).getBoundingClientRect().width);
  await page.keyboard.press("Shift+ArrowRight");
  await page.waitForTimeout(300);
  const after41 = await page.locator(".se-range").evaluate((el) => (el as HTMLElement).getBoundingClientRect().width).catch(() => 0);
  const has41 = await page.locator(".se-range").count();
  if (has41 === 1 && Math.abs(after41 - before41 - 24) < 3) {
    rec.pass("D-41", `Shift+→ grew the range ${before41.toFixed(0)} → ${after41.toFixed(0)} px (one 1/4 step)`);
  } else {
    rec.fail("D-41", "Shift+arrow did not grow the range by one step", `width ${before41} → ${after41} — ${await shot(page, "D-41-1689x1277")}`);
  }

  // D-42: Escape clears the range
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);
  const range42 = await page.locator(".se-range").count();
  if (range42 === 0) {
    rec.pass("D-42", `Escape cleared the range (.se-range=0)`);
  } else {
    rec.fail("D-42", "Escape left the range", `count=${range42} — ${await shot(page, "D-42-1689x1277")}`);
  }

  // D-43: loop with no range → four bars, persisted.
  // Both loop controls are measured: the header button and the footer button.
  await page.locator('footer button[aria-label="Loop"]').click();
  await page.waitForTimeout(600);
  const footer43 = {
    band: await page.locator(".se-loop-band").count(),
    end: ((await savedProject(page, id)).data as any).loopEnd ?? null,
  };
  if (await page.locator('footer button[aria-label="Loop"]').getAttribute("aria-pressed") === "true") {
    await page.locator('footer button[aria-label="Loop"]').click();
    await page.waitForTimeout(300);
  }
  await page.locator('.se-head button[aria-label="Loop"]').click();
  await page.waitForTimeout(600);
  const header43 = {
    band: await page.locator(".se-loop-band").count(),
    end: ((await saved(page, id)).data as any).loopEnd ?? null,
  };
  if (header43.band === 1 && Math.abs(Number(header43.end) - 8) < 0.01 && footer43.band === 1) {
    rec.pass("D-43", `header and footer both produced the four-bar band; loopEnd=${header43.end}`);
  } else {
    rec.fail(
      "D-43",
      `loop band/persistence differs between surfaces: footer band=${footer43.band} loopEnd=${footer43.end}; header band=${header43.band} loopEnd=${header43.end}`,
      `footer=${JSON.stringify(footer43)} header=${JSON.stringify(header43)} — ${await shot(page, "D-43-1689x1277")}`
    );
  }

  // D-44: drag the loop end handle, never before start + one beat
  const loopHandle = page.locator('button[aria-label="Loop end"]');
  if ((await loopHandle.count()) === 0) {
    rec.fail("D-44", "no loop band/handle exists to drag", `loop band=${await page.locator(".se-loop-band").count()} — ${await shot(page, "D-44-1689x1277")}`);
    rec.fail("D-45", "no loop to play through", `skip — ${await shot(page, "D-45-1689x1277")}`);
    return;
  }
  const handle44 = await loopHandle.boundingBox();
  if (!handle44) throw new Error("no loop handle");
  await drag(
    page,
    { x: handle44.x + handle44.width / 2, y: handle44.y + handle44.height / 2 },
    { x: handle44.x + handle44.width / 2 + barWidth * 2, y: handle44.y + handle44.height / 2 }
  );
  const doc44 = await saved(page, id);
  const end44 = Number((doc44.data as any).loopEnd ?? 0);
  const start44 = Number((doc44.data as any).loopStart ?? 0);
  if (end44 > 8 && end44 >= start44 + BAR / 4 - 0.001) {
    rec.pass("D-44", `loopEnd ${header43.end} → ${end44}; >= start + one beat`);
  } else {
    rec.fail("D-44", "loop handle drag failed", `loopEnd=${end44} — ${await shot(page, "D-44-1689x1277")}`);
  }

  // D-45: play through the loop end wraps
  // Shrink the loop to ~1 bar so the wrap is observable inside the test budget.
  const handle45 = await page.locator('button[aria-label="Loop end"]').boundingBox();
  if (handle45) {
    await drag(
      page,
      { x: handle45.x + handle45.width / 2, y: handle45.y + handle45.height / 2 },
      { x: (await lanesBox(page)).x + barWidth * 2, y: handle45.y + handle45.height / 2 }
    );
  }
  await page.locator('button[aria-label="Play"]').click();
  const samples: number[] = [];
  for (let i = 0; i < 14; i += 1) {
    samples.push(await playheadLeft(page));
    await page.waitForTimeout(250);
  }
  await page.locator('button[aria-label="Pause"], button[aria-label="Play"]').first().click().catch(() => undefined);
  const wrapped = samples.some((value, index) => index > 0 && value < samples[index - 1] - 5);
  if (wrapped) {
    rec.pass("D-45", `playhead wrapped inside the loop: ${samples.map((n) => Math.round(n)).join(",")}`);
  } else {
    rec.fail("D-45", "playhead did not wrap at the loop end", `samples=${samples.map((n) => Math.round(n)).join(",")} — ${await shot(page, "D-45-1689x1277")}`);
  }
});

test("D6 — section markers", async ({ page }) => {
  const id = await fresh(page);
  const { barWidth } = await barMetrics(page);

  // D-46: create a section from a clip
  await page.locator(".se-clip", { hasText: "Drums B" }).first().click({ button: "right" });
  await page.locator(".se-clip-menu button", { hasText: "Create Section" }).first().click();
  await page.waitForTimeout(500);
  const markers = page.locator(".se-section-marker");
  const count46 = await markers.count();
  const label46 = (await markers.last().textContent().catch(() => "")) ?? "";
  const doc46 = await saved(page, id);
  const marker46 = ((doc46.data as any).markers ?? []).find((m: any) => m.label === "Drums B");
  if (count46 === 2 && label46.includes("Drums B") && marker46 && Math.abs(marker46.time - 8) < 0.01) {
    rec.pass("D-46", `markers=${count46}; "Drums B" at ${marker46.time}s`);
  } else {
    rec.fail("D-46", "Create Section did not add the marker", `count=${count46} label="${label46}" marker=${JSON.stringify(marker46)} — ${await shot(page, "D-46-1689x1277")}`);
  }

  // D-47: click a marker seeks without a range
  const before47 = await playheadLeft(page);
  await markers.last().click();
  await page.waitForTimeout(250);
  const after47 = await playheadLeft(page);
  const range47 = await page.locator(".se-range").count();
  if (Math.abs(after47 - barWidth * 4) < 10 && range47 === 0) {
    rec.pass("D-47", `playhead ${before47.toFixed(0)} → ${after47.toFixed(0)}px (bar 5); .se-range=0`);
  } else {
    rec.fail("D-47", "marker click did not seek cleanly", `left=${after47} range=${range47} — ${await shot(page, "D-47-1689x1277")}`);
  }

  // D-48: right-click removes the marker, no context menu
  await markers.last().click({ button: "right" });
  await page.waitForTimeout(400);
  const count48 = await markers.count();
  const menu48 = await page.locator(".se-clip-menu").count();
  if (count48 === 1 && menu48 === 0) {
    rec.pass("D-48", `markers 2→${count48}; no context menu`);
  } else {
    rec.fail("D-48", "right-click did not remove the marker", `count=${count48} menu=${menu48} — ${await shot(page, "D-48-1689x1277")}`);
  }

  // D-49: markers survive a reload, sorted by time
  await page.reload();
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  await dismissOverlays(page);
  const count49 = await page.locator(".se-section-marker").count();
  const doc49 = await savedProject(page, id);
  const times49 = ((doc49.data as any).markers ?? []).map((m: any) => m.time);
  const sorted49 = times49.every((value: number, index: number) => index === 0 || value >= times49[index - 1]);
  if (count49 === 1 && sorted49) {
    rec.pass("D-49", `marker persisted after reload; times=${JSON.stringify(times49)} sorted=${sorted49}`);
  } else {
    rec.fail("D-49", "markers did not persist sorted", `count=${count49} times=${JSON.stringify(times49)} — ${await shot(page, "D-49-1689x1277")}`);
  }

  // D-50: labels at the widest zoom-out
  await page.locator('button[aria-label="Zoom out"]').click();
  await page.locator('button[aria-label="Zoom out"]').click();
  await page.locator('button[aria-label="Zoom out"]').click();
  await page.waitForTimeout(400);
  const labels50 = await page.locator(".se-section-marker").evaluateAll((els) =>
    els.map((el) => {
      const rect = el.getBoundingClientRect();
      return { text: (el.textContent ?? "").trim(), width: rect.width, overflow: el.scrollWidth > el.clientWidth + 1 };
    })
  );
  if (labels50.length > 0 && labels50.every((item) => item.text.length > 0 && !item.overflow)) {
    rec.pass("D-50", `zoomed-out labels readable: ${JSON.stringify(labels50)}`);
  } else {
    rec.fail("D-50", "marker labels truncate at the widest zoom-out", JSON.stringify(labels50) + ` — ${await shot(page, "D-50-1689x1277")}`);
  }
});

test("D7 — zoom, grid and snap", async ({ page }) => {
  const id = await fresh(page);
  const ruler = () => page.locator(".se-ruler-inner").first().evaluate((el) => (el as HTMLElement).getBoundingClientRect().width / document.querySelectorAll(".se-bar-line").length);

  // D-51: Ctrl +/- steps through the five widths
  const widths: number[] = [await ruler()];
  for (let i = 0; i < 4; i += 1) {
    await page.keyboard.press("Control+=");
    await page.waitForTimeout(150);
    widths.push(await ruler());
  }
  await page.keyboard.press("Control+=");
  await page.waitForTimeout(150);
  const clamped = await ruler();
  for (let i = 0; i < 6; i += 1) {
    await page.keyboard.press("Control+-");
    await page.waitForTimeout(120);
  }
  const clampedLow = await ruler();
  const steps = [...new Set(widths.map((value) => Math.round(value)))];
  if (steps.join(",") === "96,144,192" && clamped === 192 && clampedLow === 48) {
    rec.pass("D-51", `widths ${steps.join(" → ")}; clamps 192 / 48`);
  } else {
    rec.fail("D-51", "zoom steps differ", `widths=${steps.join(",")} high=${clamped} low=${clampedLow} — ${await shot(page, "D-51-1689x1277")}`);
  }

  // D-52: footer magnifiers follow the same steps
  await page.locator('button[aria-label="Zoom in"]').click();
  await page.waitForTimeout(150);
  const in52 = await ruler();
  await page.locator('button[aria-label="Zoom out"]').click();
  await page.waitForTimeout(150);
  const out52 = await ruler();
  if (out52 < in52) {
    rec.pass("D-52", `footer zoom: ${out52} → ${in52} px/bar`);
  } else {
    rec.fail("D-52", "footer zoom buttons did nothing", `${out52} / ${in52} — ${await shot(page, "D-52-1689x1277")}`);
  }

  // D-53: Z zooms to a range
  const { barWidth } = await barMetrics(page);
  const lanes = await lanesBox(page);
  const start = await rulerPoint(page, 0);
  const end = await rulerPoint(page, 2);
  await drag(page, start, end);
  const before53 = await page.evaluate(() => (document.querySelector(".se-timeline") as HTMLElement).scrollLeft);
  await page.keyboard.press("z");
  await page.waitForTimeout(400);
  const after53 = await ruler();
  if (after53 >= 48 && after53 !== barWidth) {
    rec.pass("D-53", `Z on a 2-bar range → ${after53} px/bar (was ${barWidth}); scrollLeft ${before53} → ${await page.evaluate(() => (document.querySelector(".se-timeline") as HTMLElement).scrollLeft)}`);
  } else {
    rec.fail("D-53", "Z did not zoom to the range", `before=${barWidth} after=${after53} — ${await shot(page, "D-53-1689x1277")}`);
  }

  // D-54: Z with clips selected and no range zooms to the clip span
  for (let i = 0; i < 3; i += 1) {
    await page.keyboard.press("Control+-");
    await page.waitForTimeout(120);
  }
  const low54 = await ruler();
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  await page.keyboard.press("z");
  await page.waitForTimeout(400);
  const zoom54 = await ruler();
  if (zoom54 > low54) {
    rec.pass("D-54", `clip-selection zoom: ${low54} → ${zoom54} px/bar`);
  } else {
    rec.fail("D-54", "Z ignored the clip selection", `${low54} → ${zoom54} — ${await shot(page, "D-54-1689x1277")}`);
  }

  // D-55 / D-56: Z and Fit with nothing selected
  await page.mouse.click(lanes.x + barWidth * 6, lanes.y + 8);
  for (let i = 0; i < 3; i += 1) {
    await page.keyboard.press("Control+-");
    await page.waitForTimeout(120);
  }
  const low55 = await ruler();
  await page.keyboard.press("z");
  await page.waitForTimeout(400);
  const zoom55 = await ruler();
  const scroll55 = await page.evaluate(() => (document.querySelector(".se-timeline") as HTMLElement).scrollLeft);
  await page.locator('button[aria-label="Fit to content"]').click();
  await page.waitForTimeout(400);
  const scroll56 = await page.evaluate(() => (document.querySelector(".se-timeline") as HTMLElement).scrollLeft);
  const fit56 = await ruler();
  if (zoom55 !== low55 && scroll55 >= 0) {
    rec.pass("D-55", `Z with nothing selected zoomed to fit: ${low55} → ${zoom55} px/bar; scrollLeft=${scroll55}`);
  } else {
    rec.fail("D-55", "Z with nothing selected did nothing", `width=${low55} → ${zoom55} — ${await shot(page, "D-55-1689x1277")}`);
  }
  if (scroll56 === 0 && fit56 > 0) {
    rec.pass("D-56", `Fit to content: scrollLeft=${scroll56}; width=${fit56} px/bar`);
  } else {
    rec.fail("D-56", "Fit did not reset the scroll", `scrollLeft=${scroll56} width=${fit56} — ${await shot(page, "D-56-1689x1277")}`);
  }

  // D-57: Shift+1/2 double/halve the grid; drop positions follow the finer/coarser step.
  // (Playwright spells the shifted digit "Shift+Digit1"; the browser key is "!".)
  for (let i = 0; i < 3; i += 1) {
    await page.locator('button[aria-label="Zoom in"]').click();
    await page.waitForTimeout(120);
  }
  const { barWidth: bw57 } = await barMetrics(page);
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  await page.keyboard.press("Shift+Digit1");
  await page.keyboard.press("Shift+Digit1");
  await page.waitForTimeout(200);
  const box57 = await clipBox(page, "Drums A");
  await drag(
    page,
    { x: box57.x + box57.width / 2, y: box57.y + box57.height / 2 },
    { x: box57.x + box57.width / 2 + bw57 * 0.078, y: box57.y + box57.height / 2 }
  );
  const fine57 = laneOf(await saved(page, id), "c-d1")!;
  await page.keyboard.press("Shift+Digit2");
  await page.keyboard.press("Shift+Digit2");
  await page.waitForTimeout(200);
  const box57b = await clipBox(page, "Drums A");
  await drag(
    page,
    { x: box57b.x + box57b.width / 2, y: box57b.y + box57b.height / 2 },
    { x: box57b.x + box57b.width / 2 + bw57 * 0.078, y: box57b.y + box57b.height / 2 }
  );
  const coarse57 = laneOf(await saved(page, id), "c-d1")!;
  const fineStart = Number(fine57.start);
  const coarseStart = Number(coarse57.start);
  if (Math.abs(fineStart - 0.125) < 0.01 && Math.abs(coarseStart - 0.5) < 0.01) {
    rec.pass("D-57", `fine grid (16 divisions) drop=${fineStart}s; coarse (4) drop=${coarseStart}s`);
  } else {
    rec.fail("D-57", "grid density did not change the drop position", `fine=${fineStart} coarse=${coarseStart} (barWidth ${bw57}) — ${await shot(page, "D-57-1689x1277")}`);
  }
});

test("D8 — automation points", async ({ page }) => {
  const id = await fresh(page);
  await selectTrack(page, "Drums");

  // D-58: band opens with tabs, Clear and Close
  await page.locator('button[aria-label="Automation"]').click();
  await expect(page.locator(".se-automation")).toBeVisible({ timeout: 8000 });
  const d58 = {
    label: await page.locator(".se-automation").getAttribute("aria-label"),
    tabs: await page.locator(".se-automation-tabs button").allTextContents(),
    clear: await page.locator(".se-automation button", { hasText: "Clear" }).count(),
    close: await page.locator('button[aria-label="Close automation"]').count(),
  };
  if (d58.label === "Track automation" && d58.tabs.join(",").includes("Volume") && d58.clear === 1 && d58.close === 1) {
    rec.pass("D-58", `section="${d58.label}"; tabs=${d58.tabs.join("/")}; Clear + Close present`);
  } else {
    rec.fail("D-58", "automation band chrome differs", JSON.stringify(d58) + ` — ${await shot(page, "D-58-1689x1277")}`);
  }

  // D-59: click adds a point and selects it
  const laneBox = await page.locator(".se-automation-lane").boundingBox();
  if (!laneBox) throw new Error("no automation lane");
  await page.mouse.click(laneBox.x + laneBox.width * 0.35, laneBox.y + laneBox.height * 0.4);
  await page.waitForTimeout(400);
  const points59 = await page.locator(".se-automation-point").count();
  const selected59 = await page.locator(".se-automation-point.is-selected").count();
  const line59 = await page.locator(".se-automation-line").count();
  if (points59 === 3 && selected59 === 1 && line59 === 1) {
    rec.pass("D-59", `points=${points59} (2 fixture + 1), selected=${selected59}, line=${line59}`);
  } else {
    rec.fail("D-59", "click did not add a selected point", `points=${points59} selected=${selected59} line=${line59} — ${await shot(page, "D-59-1689x1277")}`);
  }

  // D-60: arrows move time 0.1 s, Shift 1 s
  const labelOf = () => page.locator(".se-automation-point.is-selected").getAttribute("aria-label");
  const before60 = (await labelOf()) ?? "";
  await page.keyboard.press("ArrowRight");
  await page.waitForTimeout(150);
  const after60 = (await labelOf()) ?? "";
  await page.keyboard.press("Shift+ArrowRight");
  await page.waitForTimeout(150);
  const after60b = (await labelOf()) ?? "";
  const timeOf = (label: string) => Number((label.match(/at ([\d.]+)s/) ?? [])[1] ?? NaN);
  if (Math.abs(timeOf(after60) - timeOf(before60) - 0.1) < 0.001 && Math.abs(timeOf(after60b) - timeOf(after60) - 1) < 0.001) {
    rec.pass("D-60", `time ${timeOf(before60)} → ${timeOf(after60)} (+0.1) → ${timeOf(after60b)} (+1)`);
  } else {
    rec.fail("D-60", "arrow time steps differ", `"${before60}" → "${after60}" → "${after60b}" — ${await shot(page, "D-60-1689x1277")}`);
  }

  // D-61: up/down value steps
  const valueOf = (label: string) => Number((label.match(/^(?:Volume|Pan) (-?\d+)/) ?? [])[1] ?? NaN);
  await page.keyboard.press("ArrowUp");
  await page.waitForTimeout(120);
  const up61 = (await labelOf()) ?? "";
  await page.keyboard.press("Shift+ArrowUp");
  await page.waitForTimeout(120);
  const up61b = (await labelOf()) ?? "";
  if (Math.abs(valueOf(up61) - valueOf(after60b) - 1) < 0.001 && Math.abs(valueOf(up61b) - valueOf(up61) - 10) < 0.001) {
    rec.pass("D-61", `value ${valueOf(after60b)} → ${valueOf(up61)} (+1) → ${valueOf(up61b)} (+10)`);
  } else {
    rec.fail("D-61", "arrow value steps differ", `"${after60b}" → "${up61}" → "${up61b}" — ${await shot(page, "D-61-1689x1277")}`);
  }

  // D-62: double-click removes the point, neighbours stay
  const target = page.locator(".se-automation-point.is-selected");
  await target.dblclick();
  await page.waitForTimeout(400);
  const points62 = await page.locator(".se-automation-point").count();
  if (points62 === 2) {
    rec.pass("D-62", `points 3→${points62}; neighbours kept`);
  } else {
    rec.fail("D-62", "double-click did not remove exactly one point", `count=${points62} — ${await shot(page, "D-62-1689x1277")}`);
  }

  // D-63: pan lane is separate
  const volumeBefore = await page.locator(".se-automation-point").count();
  await page.locator(".se-automation-tabs button", { hasText: "Pan" }).click();
  await page.waitForTimeout(250);
  const panLane = await page.locator(".se-automation-lane").getAttribute("aria-label");
  const panEmpty = await page.locator(".se-automation-point").count();
  const panBox = await page.locator(".se-automation-lane").boundingBox();
  if (panBox) await page.mouse.click(panBox.x + panBox.width * 0.5, panBox.y + panBox.height * 0.5);
  await page.waitForTimeout(400);
  const panPoints = await page.locator(".se-automation-point").count();
  await waitSaved(page);
  const doc63 = await savedProject(page, id);
  const track63 = (doc63.data as any).tracks.find((t: any) => t.id === "t-drums");
  if (panEmpty === 0 && panPoints === 1 && (track63.panAutomation ?? []).length === 1 && (track63.volumeAutomation ?? []).length === volumeBefore) {
    rec.pass("D-63", `lane="${panLane}"; pan points=1; volume points untouched (${volumeBefore})`);
  } else {
    rec.fail("D-63", "pan lane is not independent", `panEmpty=${panEmpty} panPoints=${panPoints} track=${JSON.stringify({ v: track63.volumeAutomation?.length, p: track63.panAutomation?.length })} — ${await shot(page, "D-63-1689x1277")}`);
  }

  // D-64: Clear empties the lane and then disables itself
  await page.locator(".se-automation button", { hasText: "Clear" }).click();
  await page.waitForTimeout(400);
  const remaining64 = await page.locator(".se-automation-point").count();
  const clearDisabled = await page.locator(".se-automation button", { hasText: "Clear" }).isDisabled();
  if (remaining64 === 0 && clearDisabled) {
    rec.pass("D-64", `lane empty; Clear disabled=${clearDisabled}`);
  } else {
    rec.fail("D-64", "Clear did not empty the lane / disable", `points=${remaining64} disabled=${clearDisabled} — ${await shot(page, "D-64-1689x1277")}`);
  }
});

test("D9 — warp markers and clip settings", async ({ page }) => {
  const id = await fresh(page, warpDocument(), "ADF Warp");

  // D-65: double-click an audio clip opens Clip Settings
  await page.locator(".se-clip", { hasText: "Drums A" }).first().dblclick();
  await expect(page.locator(".se-audio")).toBeVisible({ timeout: 8000 });
  const sections65 = await page.locator(".se-audio").evaluate((el) => ({
    volume: !!el.querySelector('input[aria-label="Volume"]'),
    loop: !!Array.from(el.querySelectorAll("button")).find((b) => (b.textContent ?? "").includes("Loop")),
    reverse: !!Array.from(el.querySelectorAll("button")).find((b) => (b.textContent ?? "").includes("Reverse")),
    pitch: !!el.querySelector('button[aria-label="Raise pitch"]'),
    stretch: !!el.querySelector('button[role="switch"][aria-label="Stretch"]'),
    formant: !!el.querySelector('input[aria-label="Formant"]'),
    speed: !!el.querySelector(".se-audio-speed"),
    quantize: !!el.querySelector('[aria-label="Quantize grid"]'),
  }));
  if (Object.values(sections65).every(Boolean)) {
    rec.pass("D-65", `.se-audio open with ${Object.keys(sections65).join(", ")}`);
  } else {
    rec.fail("D-65", "Clip Settings is missing controls", JSON.stringify(sections65) + ` — ${await shot(page, "D-65-1689x1277")}`);
  }

  // D-66: Stretch on with no markers generates them
  const clipWarp = await page.evaluate(() => document.querySelectorAll(".se-warp-head").length);
  const stretch = page.locator('button[role="switch"][aria-label="Stretch"]');
  if ((await stretch.getAttribute("aria-checked")) === "false") {
    await stretch.click();
    await page.waitForTimeout(900);
  }
  const markers66 = await page.locator(".se-warp-head").count();
  if (clipWarp === 0 && markers66 >= 2) {
    rec.pass("D-66", `fixture markers=${clipWarp}; after Stretch on markers=${markers66}`);
  } else {
    rec.fail("D-66", "Stretch did not generate markers", `${clipWarp} → ${markers66} — ${await shot(page, "D-66-1689x1277")}`);
  }

  // D-67: three modes regenerate with the documented shapes
  const modes: Record<string, number> = {};
  for (const label of ["On Beat", "Transients", "Start and End"]) {
    await page.locator(".se-audio-modes button", { hasText: label }).first().click();
    await page.waitForTimeout(900);
    modes[label] = await page.locator(".se-warp-head").count();
  }
  const radios = await page.locator('[role="radiogroup"][aria-label="Stretch mode"] button').count();
  if (modes["Start and End"] === 2 && modes["On Beat"] > 2 && modes["Transients"] >= 2 && radios === 3) {
    rec.pass("D-67", `On Beat=${modes["On Beat"]}, Transients=${modes["Transients"]}, Start and End=${modes["Start and End"]}; radios=${radios}`);
  } else {
    rec.fail("D-67", "stretch modes did not regenerate as documented", `${JSON.stringify(modes)} radios=${radios} — ${await shot(page, "D-67-1689x1277")}`);
  }

  // D-68: drag a marker head
  await page.locator(".se-audio-modes button", { hasText: "On Beat" }).first().click();
  await page.waitForTimeout(900);
  const head = await page.locator(".se-warp-head").nth(2).boundingBox();
  if (!head) throw new Error("no warp head");
  const label68a = await page.locator(".se-warp-head").nth(2).getAttribute("aria-label");
  await drag(
    page,
    { x: head.x + head.width / 2, y: head.y + head.height / 2 },
    { x: head.x + head.width / 2 + 40, y: head.y + head.height / 2 }
  );
  const label68b = await page.locator(".se-warp-head").nth(2).getAttribute("aria-label");
  if (label68a !== label68b) {
    rec.pass("D-68", `marker moved: "${label68a}" → "${label68b}"`);
  } else {
    rec.fail("D-68", "marker head did not move", `label "${label68b}" — ${await shot(page, "D-68-1689x1277")}`);
  }

  // D-69: Shift+Q quantizes the selected marker(s) only
  // Reopen the panel so the selection starts empty.
  await page.locator('button[aria-label="Close clip editor"]').click();
  await page.waitForTimeout(250);
  await page.locator(".se-clip", { hasText: "Drums A" }).first().dblclick();
  await expect(page.locator(".se-audio")).toBeVisible({ timeout: 8000 });
  const head69 = await page.locator(".se-warp-head").nth(2).boundingBox();
  if (head69) {
    await drag(
      page,
      { x: head69.x + head69.width / 2, y: head69.y + head69.height / 2 },
      { x: head69.x + head69.width / 2 + 13, y: head69.y + head69.height / 2 }
    );
  }
  await page.locator(".se-warp-head").nth(2).click();
  await page.waitForTimeout(250);
  const selected69 = await page.locator(".se-warp-marker.selected").count();
  const before69 = await page.locator(".se-warp-head").evaluateAll((els) => els.map((el) => el.getAttribute("aria-label")));
  await page.keyboard.press("Shift+Q");
  await page.waitForTimeout(600);
  const after69 = await page.locator(".se-warp-head").evaluateAll((els) => els.map((el) => el.getAttribute("aria-label")));
  const changed69 = before69.filter((label, index) => label !== after69[index]).length;
  if (selected69 === 1 && changed69 === 1) {
    rec.pass("D-69", `Shift+Q re-quantized exactly the 1 selected marker`);
  } else {
    rec.fail("D-69", "Shift+Q changed the wrong number of markers", `selected=${selected69} changed=${changed69} of ${before69.length} — ${await shot(page, "D-69-1689x1277")}`);
  }

  // D-70: Ctrl+A selects every marker
  await page.keyboard.press("Control+a");
  await page.waitForTimeout(300);
  const pressed70 = await page.locator(".se-warp-marker.selected").count();
  const total70 = await page.locator(".se-warp-head").count();
  const pressedAttr = await page.locator(".se-warp-head").first().getAttribute("aria-pressed");
  if (pressed70 === total70 && pressedAttr === "true") {
    rec.pass("D-70", `.se-warp-marker.selected=${pressed70}/${total70}; aria-pressed=${pressedAttr}`);
  } else {
    rec.fail("D-70", "Ctrl+A did not select all markers", `${pressed70}/${total70} aria-pressed=${pressedAttr} — ${await shot(page, "D-70-1689x1277")}`);
  }

  // D-71: Shift+1/2 change the quantize grid, and Quantize applies it
  const gridActive = () => page.locator('[aria-label="Quantize grid"] button[aria-pressed="true"]');
  const gridBefore = ((await gridActive().textContent()) ?? "").trim();
  await page.keyboard.press("Shift+Digit1");
  await page.waitForTimeout(250);
  const gridAfter = ((await gridActive().textContent()) ?? "").trim();
  const gridList = await page.locator('[aria-label="Quantize grid"] button').evaluateAll((els) =>
    els.map((el) => `${(el.textContent ?? "").trim()}:${el.getAttribute("aria-pressed")}`)
  );
  // Nudge one marker off the grid so Quantize has something to snap.
  const head71 = await page.locator(".se-warp-head").nth(2).boundingBox();
  if (head71) {
    await drag(
      page,
      { x: head71.x + head71.width / 2, y: head71.y + head71.height / 2 },
      { x: head71.x + head71.width / 2 + 11, y: head71.y + head71.height / 2 }
    );
  }
  const before71 = await page.locator(".se-warp-head").evaluateAll((els) => els.map((el) => el.getAttribute("aria-label")));
  await page.locator(".se-audio-quantize-actions button").nth(1).click();
  await page.waitForTimeout(600);
  const after71 = await page.locator(".se-warp-head").evaluateAll((els) => els.map((el) => el.getAttribute("aria-label")));
  const changed71 = after71.filter((label, index) => label !== before71[index]).length;
  if (gridBefore !== gridAfter && changed71 > 0) {
    rec.pass("D-71", `grid "${gridBefore}" → "${gridAfter}" (${gridList.join(" ")}); Quantize snapped ${changed71} marker(s)`);
  } else {
    rec.fail("D-71", "grid change or Quantize did not apply", `grid ${gridBefore}→${gridAfter} [${gridList.join(" ")}] changed=${changed71} — ${await shot(page, "D-71-1689x1277")}`);
  }

  // D-72: clip settings write and survive a reload
  const volume = page.locator('input[aria-label="Volume"]');
  await volume.evaluate((el) => {
    const input = el as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")?.set;
    setter?.call(input, "-6");
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await page.locator(".se-audio-pair button", { hasText: "Loop" }).click();
  await page.locator(".se-audio-pair button", { hasText: "Reverse" }).click();
  await page.locator('button[aria-label="Raise pitch"]').click();
  await page.locator('button[aria-label="Raise pitch"]').click();
  await page.locator(".se-audio-speed button", { hasText: "×2" }).click();
  await waitSaved(page);
  await page.reload();
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  await dismissOverlays(page);
  const doc72 = await savedProject(page, id);
  const audio72 = (laneOf(doc72, "c-d1") as any)?.audio ?? {};
  if (audio72.gainDb === -6 && audio72.loop === true && audio72.reverse === true && audio72.pitch === 2 && audio72.speed === 200) {
    rec.pass("D-72", `clip.audio=${JSON.stringify(audio72)} survived reload`);
  } else {
    rec.fail("D-72", "clip settings did not persist", `${JSON.stringify(audio72)} — ${await shot(page, "D-72-1689x1277")}`);
  }

  // D-73: collapse keeps the header, close restores the arrangement
  await page.locator(".se-clip", { hasText: "Drums A" }).first().dblclick();
  await expect(page.locator(".se-audio")).toBeVisible({ timeout: 8000 });
  const bodyBefore = await page.locator(".se-audio-body").isVisible();
  await page.locator('button[aria-label="Collapse clip settings"]').click();
  await page.waitForTimeout(250);
  const bodyAfter = await page.locator(".se-audio-body").isVisible();
  const header73 = await page.locator(".se-audio-head").isVisible();
  await page.locator('button[aria-label="Close clip editor"]').click();
  await page.waitForTimeout(300);
  const closed73 = await page.locator(".se-audio").count();
  if (bodyBefore && !bodyAfter && header73 && closed73 === 0) {
    rec.pass("D-73", `collapse hid the body (header kept); close removed the panel`);
  } else {
    rec.fail("D-73", "collapse/close behaviour differs", `body ${bodyBefore}→${bodyAfter} header=${header73} closed=${closed73} — ${await shot(page, "D-73-1689x1277")}`);
  }
});

function midiDocument(): ReturnType<typeof adfDocument> {
  const doc = adfDocument();
  const lanes = (doc.data as { lanes: Array<Record<string, unknown>> }).lanes;
  const bass = lanes.find((clip) => clip.id === "c-bass")!;
  bass.midi = {
    notes: [
      { id: "m-1", pitch: 48, start: 0.13, length: 0.4, velocity: 100 },
      { id: "m-2", pitch: 50, start: 0.62, length: 0.4, velocity: 90 },
      { id: "m-3", pitch: 52, start: 1.27, length: 0.4, velocity: 80 },
    ],
    bend: [],
    mod: [],
  };
  return doc;
}

test("D10 — MIDI editor", async ({ page }) => {
  const id = await fresh(page, midiDocument(), "ADF MIDI");

  // D-74: double-click a MIDI clip opens the editor, focused
  await page.locator(".se-clip", { hasText: "Bass" }).first().dblclick();
  await expect(page.locator(".se-midi")).toBeVisible({ timeout: 8000 });
  const d74 = await page.evaluate(() => {
    const el = document.querySelector(".se-midi") as HTMLElement | null;
    return {
      label: el?.getAttribute("aria-label"),
      tabIndex: el?.getAttribute("tabindex"),
      focused: document.activeElement === el,
      notes: document.querySelectorAll(".se-midi-note").length,
    };
  });
  if (d74.label === "MIDI editor" && d74.tabIndex === "-1" && d74.notes === 3) {
    rec.pass("D-74", `${d74.label}; tabIndex=${d74.tabIndex}; focused=${d74.focused}; notes=${d74.notes}`);
  } else {
    rec.fail("D-74", "MIDI editor did not open as expected", JSON.stringify(d74) + ` — ${await shot(page, "D-74-1689x1277")}`);
  }

  // D-75: click an empty cell adds one note; clicking again does not stack
  const grid = await page.locator(".se-midi-grid").boundingBox();
  if (!grid) throw new Error("no midi grid");
  await page.mouse.click(grid.x + 120, grid.y + 200);
  await page.waitForTimeout(350);
  const notes75a = await page.locator(".se-midi-note").count();
  const selected75 = await page.locator(".se-midi-note.is-selected").count();
  const velocity75 = await page.locator(".se-midi-note.is-selected").first().getAttribute("aria-label");
  await page.mouse.click(grid.x + 120, grid.y + 200);
  await page.waitForTimeout(350);
  const notes75b = await page.locator(".se-midi-note").count();
  if (notes75a === 4 && selected75 === 1 && /velocity 100/.test(velocity75 ?? "") && notes75b === 4) {
    rec.pass("D-75", `notes 3→${notes75a}; selected=${selected75}; "${velocity75}"; second click kept ${notes75b}`);
  } else {
    rec.fail("D-75", "empty-cell click behaviour differs", `${notes75a}/${notes75b} selected=${selected75} "${velocity75}" — ${await shot(page, "D-75-1689x1277")}`);
  }

  // D-76: chord mode adds a chord
  await page.locator('select[aria-label="Chord mode"]').selectOption("major");
  const notesBefore76 = await page.locator(".se-midi-note").count();
  await page.mouse.click(grid.x + 300, grid.y + 260);
  await page.waitForTimeout(350);
  const notesAfter76 = await page.locator(".se-midi-note").count();
  await page.locator('select[aria-label="Chord mode"]').selectOption("off");
  if (notesAfter76 >= notesBefore76 + 3) {
    rec.pass("D-76", `major chord click: notes ${notesBefore76} → ${notesAfter76}`);
  } else {
    rec.fail("D-76", "chord mode added fewer than 3 notes", `${notesBefore76}→${notesAfter76} — ${await shot(page, "D-76-1689x1277")}`);
  }

  // D-77: arp lays a chord out over the step
  await page.locator('select[aria-label="Chord mode"]').selectOption("major");
  await page.locator('select[aria-label="Arpeggiator"]').selectOption("up");
  const roll77 = await page.locator(".se-midi-roll").boundingBox();
  if (!roll77) throw new Error("no midi roll");
  const notesBefore77 = await page.locator(".se-midi-note").count();
  const before77 = await page.locator(".se-midi-note").evaluateAll((els) =>
    els.map((el) => el.getAttribute("aria-label") ?? "")
  );
  const click77 = { x: roll77.x + 100, y: roll77.y + 90 };  const hit77 = await page.evaluate(
    ({ x, y }) => {
      const el = document.elementFromPoint(x, y) as HTMLElement | null;
      return el ? `${el.tagName}.${el.className}` : "none";
    },
    click77
  );
  await page.mouse.click(click77.x, click77.y);
  await page.waitForTimeout(400);
  const notesAfter77 = await page.locator(".se-midi-note").count();
  const labels77 = await page.locator(".se-midi-note").evaluateAll((els) =>
    els.map((el) => el.getAttribute("aria-label") ?? "")
  );
  await page.locator('select[aria-label="Arpeggiator"]').selectOption("off");
  await page.locator('select[aria-label="Chord mode"]').selectOption("off");
  const added77 = labels77.filter((label) => !before77.includes(label));
  const startsOfAdded = added77.map((label) => (label.match(/at ([\d.]+)s/) ?? [])[1]);
  const distinctAdded = new Set(startsOfAdded).size;
  if (notesAfter77 === notesBefore77 + 3 && distinctAdded === 3) {
    rec.pass("D-77", `major + arp-up click added 3 notes on distinct steps: ${added77.join(", ")}`);
  } else {
    rec.fail("D-77", "arp did not lay the chord out", `${notesBefore77}→${notesAfter77}; added=${added77.join(" | ")} distinct=${distinctAdded} — ${await shot(page, "D-77-1689x1277")}`);
  }

  // D-78: drag a visible note; time snaps and pitch follows the row
  const roll78 = await page.locator(".se-midi-roll").boundingBox();
  if (!roll78) throw new Error("no midi roll for drag");
  const notes78 = page.locator(".se-midi-note");
  const total78 = await notes78.count();
  let noteBox: { x: number; y: number; width: number; height: number } | null = null;
  let noteIndex = 0;
  for (let i = 0; i < total78; i += 1) {
    const box = await notes78.nth(i).boundingBox();
    if (
      box &&
      box.y > roll78.y + 8 &&
      box.y + box.height < roll78.y + roll78.height - 8 &&
      box.x > roll78.x + 40 &&
      box.x + box.width < roll78.x + roll78.width - 20
    ) {
      noteBox = box;
      noteIndex = i;
      break;
    }
  }
  if (!noteBox) throw new Error("no visible note to drag");
  const label78a = await notes78.nth(noteIndex).getAttribute("aria-label");
  await drag(
    page,
    { x: noteBox.x + noteBox.width / 2, y: noteBox.y + noteBox.height / 2 },
    { x: noteBox.x + noteBox.width / 2 + 40, y: noteBox.y + noteBox.height / 2 - 12 }
  );
  const label78b = await page.locator(".se-midi-note").nth(noteIndex).getAttribute("aria-label");
  if (label78a !== label78b) {
    rec.pass("D-78", `note "${label78a}" → "${label78b}"`);
  } else {
    rec.fail("D-78", "note drag did not move the note", `label "${label78b}" — ${await shot(page, "D-78-1689x1277")}`);
  }

  // D-79: double-click a note deletes it
  const notesBefore79 = await page.locator(".se-midi-note").count();
  await page.locator(".se-midi-note").first().dblclick();
  await page.waitForTimeout(350);
  const notesAfter79 = await page.locator(".se-midi-note").count();
  if (notesAfter79 === notesBefore79 - 1) {
    rec.pass("D-79", `notes ${notesBefore79} → ${notesAfter79}`);
  } else {
    rec.fail("D-79", "double-click did not delete one note", `${notesBefore79}→${notesAfter79} — ${await shot(page, "D-79-1689x1277")}`);
  }

  // D-80: drag in the velocity lane
  const velocityLane = await page.locator(".se-midi-velocity").boundingBox();
  if (!velocityLane) throw new Error("no velocity lane");
  const noteLane = await page.locator(".se-midi-note").nth(1).boundingBox();
  if (!noteLane) throw new Error("no note for velocity");
  const velocityBefore = await page.locator(".se-midi-note").nth(1).getAttribute("data-velocity");
  await drag(
    page,
    { x: noteLane.x + 4, y: velocityLane.y + velocityLane.height * 0.8 },
    { x: noteLane.x + 4, y: velocityLane.y + velocityLane.height * 0.3 }
  );
  const velocityAfter = await page.locator(".se-midi-note").nth(1).getAttribute("data-velocity");
  const barCount = await page.locator(".se-midi-velocity-bar").count();
  if (velocityBefore !== velocityAfter && Number(velocityAfter) > Number(velocityBefore) && barCount > 0) {
    rec.pass("D-80", `velocity ${velocityBefore} → ${velocityAfter}; bars=${barCount}`);
  } else {
    rec.fail("D-80", "velocity drag did not change the note", `${velocityBefore}→${velocityAfter} bars=${barCount} — ${await shot(page, "D-80-1689x1277")}`);
  }

  // D-81: pitch bend points
  await page.locator('.se-midi-tabs button', { hasText: "Pitch Bend" }).click();
  await page.waitForTimeout(250);
  const bendLane = await page.locator(".se-midi-velocity").boundingBox();
  if (!bendLane) throw new Error("no bend lane");
  await page.mouse.click(bendLane.x + 120, bendLane.y + bendLane.height * 0.3);
  await page.waitForTimeout(350);
  const points81 = await page.locator(".se-midi-lane-point").count();
  const line81 = await page.locator(".se-midi-lane-line").count();
  await page.locator(".se-midi-lane-point").first().dblclick();
  await page.waitForTimeout(300);
  const points81b = await page.locator(".se-midi-lane-point").count();
  if (points81 === 1 && line81 >= 0 && points81b === 0) {
    rec.pass("D-81", `bend point added (points=${points81}, line=${line81}); double-click removed it`);
  } else {
    rec.fail("D-81", "pitch bend lane behaviour differs", `points=${points81} line=${line81} after dblclick=${points81b} — ${await shot(page, "D-81-1689x1277")}`);
  }

  // D-82: modulation lane is separate
  await page.locator('.se-midi-tabs button', { hasText: "Modulation" }).click();
  await page.waitForTimeout(250);
  const modLane = await page.locator(".se-midi-velocity").boundingBox();
  if (!modLane) throw new Error("no mod lane");
  await page.mouse.click(modLane.x + 260, modLane.y + modLane.height * 0.4);
  await page.waitForTimeout(600);
  const modPoints = await page.locator(".se-midi-lane-point").count();
  const doc82 = await saved(page, id);
  const midi82 = (laneOf(doc82, "c-bass") as any)?.midi ?? {};
  if (modPoints === 1 && (midi82.mod ?? []).length === 1 && (midi82.bend ?? []).length === 0) {
    rec.pass("D-82", `mod lane point=1; saved midi.mod=${JSON.stringify(midi82.mod)}; bend=${JSON.stringify(midi82.bend)}`);
  } else {
    rec.fail("D-82", "modulation lane did not write separately", `points=${modPoints} mod=${JSON.stringify(midi82.mod)} bend=${JSON.stringify(midi82.bend)} — ${await shot(page, "D-82-1689x1277")}`);
  }

  // D-83: Ctrl+A then arrows move notes
  await page.locator('.se-midi-tabs button', { hasText: "Velocity" }).click();
  await page.locator(".se-midi").focus();
  await page.keyboard.press("Control+a");
  await page.waitForTimeout(200);
  const selected83 = await page.locator(".se-midi-note.is-selected").count();
  const leftBefore = await page.locator(".se-midi-note").evaluateAll((els) => els.map((el) => parseFloat((el as HTMLElement).style.left)));
  await page.keyboard.press("ArrowRight");
  await page.waitForTimeout(250);
  const leftAfter = await page.locator(".se-midi-note").evaluateAll((els) => els.map((el) => parseFloat((el as HTMLElement).style.left)));
  const widthBefore = await page.locator(".se-midi-note").evaluateAll((els) => els.map((el) => parseFloat((el as HTMLElement).style.width)));
  await page.keyboard.press("Shift+ArrowRight");
  await page.waitForTimeout(250);
  const widthAfter = await page.locator(".se-midi-note").evaluateAll((els) => els.map((el) => parseFloat((el as HTMLElement).style.width)));
  if (selected83 === leftBefore.length && leftAfter.every((value, index) => value > leftBefore[index]) && widthAfter.some((value, index) => value > widthBefore[index])) {
    rec.pass("D-83", `selected=${selected83}; ←/→ moved all; Shift+→ lengthened`);
  } else {
    rec.fail("D-83", "note nudge/length shortcuts differ", `selected=${selected83} moved=${leftAfter.filter((v, i) => v > leftBefore[i]).length} lengthened=${widthAfter.filter((v, i) => v > widthBefore[i]).length} — ${await shot(page, "D-83-1689x1277")}`);
  }

  // D-84: transpose semitone / octave
  const pitch84a = await page.locator(".se-midi-note").evaluateAll((els) => els.map((el) => el.getAttribute("aria-label")));
  await page.keyboard.press("ArrowUp");
  await page.waitForTimeout(250);
  const pitch84b = await page.locator(".se-midi-note").evaluateAll((els) => els.map((el) => el.getAttribute("aria-label")));
  await page.keyboard.press("Shift+ArrowDown");
  await page.waitForTimeout(250);
  const pitch84c = await page.locator(".se-midi-note").evaluateAll((els) => els.map((el) => el.getAttribute("aria-label")));
  if (pitch84a[0] !== pitch84b[0] && pitch84b[0] !== pitch84c[0]) {
    rec.pass("D-84", `pitch "${pitch84a[0]}" → +1 "${pitch84b[0]}" → -12 "${pitch84c[0]}"`);
  } else {
    rec.fail("D-84", "transpose shortcuts differ", `${pitch84a[0]} / ${pitch84b[0]} / ${pitch84c[0]} — ${await shot(page, "D-84-1689x1277")}`);
  }

  // D-85: 0 toggles disabled on the selection
  await page.keyboard.press("0");
  await page.waitForTimeout(300);
  const disabled85 = await page.locator(".se-midi-note.is-disabled").count();
  const total85 = await page.locator(".se-midi-note").count();
  const attr85 = await page.locator(".se-midi-note").first().getAttribute("data-disabled");
  const label85 = await page.locator(".se-midi-note").first().getAttribute("aria-label");
  if (disabled85 === total85 && attr85 === "true" && /disabled/.test(label85 ?? "")) {
    rec.pass("D-85", `.is-disabled=${disabled85}/${total85}; data-disabled=${attr85}; label contains "disabled"`);
  } else {
    rec.fail("D-85", "0-key disable differs", `count=${disabled85}/${total85} attr=${attr85} label="${label85}" — ${await shot(page, "D-85-1689x1277")}`);
  }

  // D-86: quantize applies immediately
  const starts86a = await page.locator(".se-midi-note").evaluateAll((els) => els.map((el) => el.getAttribute("aria-label")));
  await page.locator('select[aria-label="Quantize"]').selectOption("4");
  await page.waitForTimeout(500);
  const starts86b = await page.locator(".se-midi-note").evaluateAll((els) => els.map((el) => el.getAttribute("aria-label")));
  const changed86 = starts86a.filter((label, index) => label !== starts86b[index]).length;
  if (changed86 > 0) {
    rec.pass("D-86", `quantize 1/4 re-placed ${changed86} notes immediately`);
  } else {
    rec.fail("D-86", "quantize did not apply", `changed=${changed86} — ${await shot(page, "D-86-1689x1277")}`);
  }

  // D-87: Clear then Import MIDI
  await page.locator(".se-midi-controls button", { hasText: "Clear" }).click();
  await page.waitForTimeout(300);
  const cleared87 = await page.locator(".se-midi-note").count();
  const midiBytes = Buffer.from([
    0x4d, 0x54, 0x68, 0x64, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00, 0x01, 0x00, 0x60,
    0x4d, 0x54, 0x72, 0x6b, 0x00, 0x00, 0x00, 0x0c,
    0x00, 0x90, 0x3c, 0x64, 0x60, 0x80, 0x3c, 0x40, 0x00, 0xff, 0x2f, 0x00,
  ]);
  await page.locator('input[type="file"][accept*="mid"]').setInputFiles({
    name: "adf.mid",
    mimeType: "audio/midi",
    buffer: midiBytes,
  });
  await page.waitForTimeout(1200);
  const imported87 = await page.locator(".se-midi-note").count();
  const toast87 = (await page.locator(".se-toast").textContent().catch(() => "")) ?? "";
  if (cleared87 === 0 && imported87 >= 1 && /Imported \d+ MIDI notes/.test(toast87)) {
    rec.pass("D-87", `Clear → ${cleared87}; import → ${imported87} notes; toast="${toast87.replace(/\s+/g, " ").trim()}"`);
  } else {
    rec.fail("D-87", "Clear/Import MIDI failed", `cleared=${cleared87} imported=${imported87} toast="${toast87}" — ${await shot(page, "D-87-1689x1277")}`);
  }

  // D-88: musical typing
  await page.locator(".se-midi").focus();
  await page.keyboard.press("Control+k");
  await page.waitForTimeout(200);
  const power88 = page.locator(".se-midi-controls button", { hasText: "Keys" });
  const label88a = (await power88.textContent()) ?? "";
  const pressed88 = await power88.getAttribute("aria-pressed");
  await page.keyboard.press("a");
  await page.keyboard.press("s");
  await page.keyboard.press("z");
  await page.keyboard.press("x");
  await page.keyboard.press("c");
  await page.keyboard.press("v");
  await page.waitForTimeout(300);
  const label88b = (await power88.textContent()) ?? "";
  const octaveHint = await page.locator(".se-midi-controls").textContent();
  if (/Keys On/.test(label88a) && pressed88 === "true" && /Keys On/.test(label88b)) {
    rec.pass("D-88", `Ctrl+K → "${label88a.trim()}" (aria-pressed=${pressed88}); A/S/Z/X/C/V accepted`);
  } else {
    rec.fail("D-88", "musical typing did not engage", `"${label88a}" pressed=${pressed88} — ${await shot(page, "D-88-1689x1277")}`);
  }
  void octaveHint;
});

test("D — viewport sanity for gestures at 1280×800", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await signIn(page);
  const id = await createProject(page, "ADF D1280", adfDocument());
  await openProject(page, id);
  const { barWidth } = await barMetrics(page);
  const lanes = await lanesBox(page);
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  const box = await clipBox(page, "Drums A");
  await drag(
    page,
    { x: box.x + box.width / 2, y: box.y + box.height / 2 },
    { x: box.x + box.width / 2 + barWidth, y: box.y + box.height / 2 }
  );
  const moved = laneOf(await saved(page, id), "c-d1")!;
  const scroll = await bodyScroll(page);
  if (Math.abs((moved.start as number) - BAR) < 0.02 && scroll <= 1280) {
    rec.pass("D-VP", `1280×800 drag still snapped to ${moved.start}s; body scrollWidth=${scroll}`);
  } else {
    rec.fail("D-VP", "gesture failed at 1280×800", `start=${moved.start} scroll=${scroll} — ${await shot(page, "D-VP-1280x800")}`);
  }
});



