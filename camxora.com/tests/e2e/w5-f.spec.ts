import { expect, test, type Page } from "@playwright/test";

import {
  adfDocument,
  createProject,
  dismissOverlays,
  drag,
  laneOf,
  makeRecorder,
  openProject,
  quietHelp,
  safeShot,
  pageResponsive,
  savedProject,
  shot,
  signIn,
  waitSaved,
} from "./w5-adf-harness";

/**
 * Area F — async boundaries (33 checks).
 *
 * Autosave, write queueing, 409 conflicts, the offline draft and the mirror chip are
 * driven with Playwright route interception / offline mode. Provider refusals are
 * mocked at the network layer because spending credits is out of scope (checklist
 * G-3); only the UI states are asserted.
 */

const rec = makeRecorder("f");
test.describe.configure({ mode: "serial" });
test.afterAll(() => rec.flush());
test.use({ viewport: { width: 1689, height: 1277 } });
test.setTimeout(180_000);

// The editor arms its own beforeunload guard on an unsaved write; Playwright dismisses
// dialogs by default, which cancels a reload and hangs it. Accept instead.
test.beforeEach(async ({ page }) => {
  page.on("dialog", (dialog) => void dialog.accept().catch(() => undefined));
});

const PATCH = /\/api\/v3\/web-music\/studio\/projects\/[0-9a-f-]+$/;

async function fresh(page: Page, title = "ADF F") {
  await quietHelp(page, false);
  await signIn(page);
  const id = await createProject(page, title, adfDocument());
  await openProject(page, id);
  return id;
}

async function moveClip(page: Page) {
  const box = await page.locator(".se-clip", { hasText: "Drums A" }).first().boundingBox();
  if (!box) throw new Error("no clip");
  await drag(
    page,
    { x: box.x + box.width / 2, y: box.y + box.height / 2 },
    { x: box.x + box.width / 2 + 96, y: box.y + box.height / 2 }
  );
}

async function chipText(page: Page) {
  return ((await page.locator(".se-save").first().textContent().catch(() => "")) ?? "").replace(/\s+/g, " ").trim();
}

test("F1 — autosave chip, queueing and retry", async ({ page }) => {
  const id = await fresh(page);

  // F-01: a move goes Saving… then Saved (observed through a MutationObserver,
  // because the live chip can flip faster than a polling loop)
  await page.evaluate(() => {
    (window as any).__chipStates = [];
    const target = document.querySelector(".se-save")?.parentElement;
    if (!target) return;
    const record = () => {
      const text = (document.querySelector(".se-save")?.textContent ?? "").replace(/\s+/g, " ").trim();
      const states = (window as any).__chipStates as string[];
      if (text && states[states.length - 1] !== text) states.push(text);
    };
    record();
    new MutationObserver(record).observe(target, { subtree: true, childList: true, characterData: true });
  });
  await moveClip(page);
  await expect(page.locator(".se-save")).toContainText("Saved", { timeout: 25_000 });
  const seen = (await page.evaluate(() => (window as any).__chipStates as string[])) ?? [];
  if (seen.some((text) => /Saving/.test(text)) && seen.some((text) => /^Saved/.test(text))) {
    rec.pass("F-01", `chip states: ${seen.join(" → ")}`);
  } else {
    rec.fail("F-01", "save chip did not cycle Saving… → Saved", `states=${seen.join(", ")} — ${await shot(page, "F-01-1689x1277")}`);
  }

  // F-02: Saving… is polite, non-modal, and editing stays possible
  let held = 0;
  await page.route(PATCH, async (route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    held += 1;
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await route.continue().catch(() => undefined);
  });
  await moveClip(page);
  await page.waitForTimeout(350);
  const during = {
    chip: await chipText(page),
    live: await page.locator(".se-save[aria-live='polite']").count(),
    dialogs: await page.locator("[role='dialog'], [role='alertdialog']").count(),
  };
  await page.locator(".se-clip", { hasText: "Vox" }).first().click();
  const stillEditable = await page.locator(".se-clip.selected", { hasText: "Vox" }).count();
  if (/Saving/.test(during.chip) && during.live >= 1 && during.dialogs === 0 && stillEditable === 1) {
    rec.pass("F-02", `held write: chip="${during.chip}", aria-live=${during.live}, dialogs=${during.dialogs}, selection still works`);
  } else {
    rec.fail("F-02", "a slow write blocks or mislabels the editor", `${JSON.stringify(during)} editable=${stillEditable} — ${await shot(page, "F-02-1689x1277")}`);
  }
  await page.unroute(PATCH);
  await waitSaved(page);

  // F-03: two back-to-back edits on a throttled link both land, no 409
  let patches = 0;
  let conflicts = 0;
  await page.route(PATCH, async (route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    patches += 1;
    await new Promise((resolve) => setTimeout(resolve, 700));
    await route.continue().catch(() => undefined);
  });
  await moveClip(page);
  await page.waitForTimeout(120);
  await moveClip(page);
  await page.waitForTimeout(4000);
  const banner = await page.locator(".se-conflict[role='alertdialog']").count();
  await page.unroute(PATCH);
  await waitSaved(page);
  const doc3 = await savedProject(page, id);
  const clips3 = (doc3.data as any).lanes as any[];
  const moved3 = clips3.filter((clip) => (clip.start ?? 0) > 0).length;
  void patches;
  void conflicts;
  if (banner === 0 && moved3 >= 2) {
    rec.pass("F-03", `two queued edits landed (moved=${moved3}), no 409 banner`);
  } else {
    rec.fail("F-03", "queued edits failed or raised a false conflict", `banner=${banner} moved=${moved3} — ${await shot(page, "F-03-1689x1277")}`);
  }

  // F-04: reload while the second write is queued → the draft is offered
  await page.route(PATCH, async (route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    await new Promise((resolve) => setTimeout(resolve, 2500));
    await route.continue().catch(() => undefined);
  });
  await moveClip(page);
  await page.waitForTimeout(100);
  await moveClip(page);
  await page.waitForTimeout(300);
  const draftBefore = await page.evaluate((projectId) => {
    const key = `studio:draft:${projectId}`;
    return localStorage.getItem(key) ? 1 : 0;
  }, id);
  await page.reload();
  await expect(page.locator(".se-track").first()).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(800);
  const draftBanner = page.locator(".se-conflict[role='alert']", { hasText: "We found" });
  const draftShown = await draftBanner.count();
  const draftDebug = await page.evaluate((projectId) => {
    const raw = localStorage.getItem(`studio:draft:${projectId}`);
    return raw ? (JSON.parse(raw).savedAt as string) : null;
  }, id);
  const serverDebug = (await savedProject(page, id)).updated_at ?? null;
  console.log("F-04 draft savedAt", draftDebug, "server updated_at", serverDebug);
  await page.unroute(PATCH);
  if (draftBefore >= 1 && draftShown === 1) {
    rec.pass("F-04", `queued burst mirrored to localStorage (${draftBefore}) and offered after reload`);
  } else {
    rec.fail("F-04", "queued write was not mirrored into a recoverable draft", `draftKeys=${draftBefore} banner=${draftShown} — ${await shot(page, "F-04-1689x1277")}`);
  }
  await dismissOverlays(page);
  await waitSaved(page);

  // F-05: Ctrl+S forces a write with no change
  const before5 = await page.evaluate(async (projectId) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${projectId}`, { cache: "no-store" });
    return ((await response.json()) as any).updated_at as string;
  }, id);
  await page.route(PATCH, async (route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    await new Promise((resolve) => setTimeout(resolve, 500));
    await route.continue().catch(() => undefined);
  });
  await page.keyboard.press("Control+s");
  await page.waitForTimeout(300);
  const during5 = await chipText(page);
  await page.waitForTimeout(1500);
  await page.unroute(PATCH);
  const after5 = await page.evaluate(async (projectId) => {
    const response = await fetch(`/api/v3/web-music/studio/projects/${projectId}`, { cache: "no-store" });
    return ((await response.json()) as any).updated_at as string;
  }, id);
  if (/Saving/.test(during5) && after5 !== before5) {
    rec.pass("F-05", `Ctrl+S wrote immediately (updated_at ${before5} → ${after5}); chip during="${during5}"`);
  } else {
    rec.fail("F-05", "Ctrl+S did not force a write", `chip="${during5}" ${before5}→${after5} — ${await shot(page, "F-05-1689x1277")}`);
  }

  // F-06 / F-07: API failure → retry chip; clicking retries
  await page.route(PATCH, async (route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "boom" }) });
  });
  await moveClip(page);
  await page.waitForTimeout(1200);
  const failed = {
    chip: await chipText(page),
    isButton: await page.locator("button.se-save.on").count(),
  };
  if (/Save failed/.test(failed.chip) && failed.isButton === 1) {
    rec.pass("F-06", `chip="${failed.chip}" rendered as a button.se-save.on`);
  } else {
    rec.fail("F-06", "failed write did not become a retry chip", JSON.stringify(failed) + ` — ${await shot(page, "F-06-1689x1277")}`);
  }
  await page.unroute(PATCH);
  await page.locator("button.se-save").first().click();
  await page.waitForTimeout(2500);
  const after7 = { chip: await chipText(page), errors: await page.locator(".se-error").count() };
  if (/^Saved/.test(after7.chip) && after7.errors === 0) {
    rec.pass("F-07", `retry succeeded: chip="${after7.chip}", .se-error=${after7.errors}`);
  } else {
    rec.fail("F-07", "retry did not recover", JSON.stringify(after7) + ` — ${await shot(page, "F-07-1689x1277")}`);
  }

  // F-08: unsaved change arms the beforeunload guard
  await page.route(PATCH, async (route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "boom" }) });
  });
  await moveClip(page);
  await page.waitForTimeout(1000);
  const guard = await page.evaluate(() => {
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  });
  await page.unroute(PATCH);
  if (guard) {
    rec.pass("F-08", `beforeunload handler prevented the leave while a write is unsaved`);
  } else {
    rec.fail("F-08", "no beforeunload guard with an unsaved change", `defaultPrevented=${guard} — ${await shot(page, "F-08-1689x1277")}`);
  }
  await page.unrouteAll();
  await page.reload();
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  await dismissOverlays(page);
});

test("F2 — offline draft lifecycle", async ({ page, context }) => {
  const id = await fresh(page, "ADF F-offline");

  // F-09: offline edit → chip says offline, a draft exists, no request
  await context.setOffline(true);
  await page.waitForTimeout(400);
  await moveClip(page);
  await page.waitForTimeout(600);
  const offline = {
    chip: await chipText(page),
    draft: await page.evaluate((projectId) => {
      return localStorage.getItem(`studio:draft:${projectId}`) ? 1 : 0;
    }, id),
  };
  if (/Offline/.test(offline.chip) && offline.draft >= 1) {
    rec.pass("F-09", `chip="${offline.chip}"; draft keys=${offline.draft}`);
  } else {
    rec.fail("F-09", "offline edit did not report offline / write a draft", JSON.stringify(offline) + ` — ${await shot(page, "F-09-1689x1277")}`);
  }

  // F-10: back online replays the burst and clears the draft
  await context.setOffline(false);
  await page.waitForTimeout(3500);
  const online = {
    chip: await chipText(page),
    draft: await page.evaluate((projectId) => {
      return localStorage.getItem(`studio:draft:${projectId}`) ? 1 : 0;
    }, id),
  };
  if (/^Saved/.test(online.chip) && online.draft === 0) {
    rec.pass("F-10", `replay succeeded: chip="${online.chip}", draft cleared`);
  } else {
    rec.fail("F-10", "reconnect did not replay / clear the draft", JSON.stringify(online) + ` — ${await shot(page, "F-10-1689x1277")}`);
  }

  // F-11: the first replay fails while online → one automatic retry
  let attempts = 0;
  await page.route(PATCH, async (route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    attempts += 1;
    if (attempts === 1) {
      await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "boom" }) });
      return;
    }
    await route.continue().catch(() => undefined);
  });
  await context.setOffline(true);
  await page.waitForTimeout(300);
  await moveClip(page);
  await page.waitForTimeout(500);
  await context.setOffline(false);
  await page.waitForTimeout(5000);
  const retried = { chip: await chipText(page), attempts };
  await page.unroute(PATCH);
  if (attempts >= 2 && /^Saved/.test(retried.chip)) {
    rec.pass("F-11", `first replay failed, automatic retry succeeded after ${attempts} PATCHes; chip="${retried.chip}"`);
  } else {
    rec.fail("F-11", "no automatic retry after a failed replay", JSON.stringify(retried) + ` — ${await shot(page, "F-11-1689x1277")}`);
  }
});

test("F2b — draft recovery after a failed write", async ({ page }) => {
  const id = await fresh(page, "ADF F-draft");
  // F-12: reload after a failed write surfaces the draft banner
  await page.route(PATCH, async (route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "boom" }) });
  });
  await moveClip(page);
  await page.waitForTimeout(1200);
  await page.unroute(PATCH);
  await page.reload();
  await expect(page.locator(".se-track").first()).toBeVisible({ timeout: 30_000 });
  const banner12 = page.locator(".se-conflict[role='alert']");
  await expect(banner12).toBeVisible({ timeout: 10_000 }).catch(() => undefined);
  const text12 = ((await banner12.textContent().catch(() => "")) ?? "").replace(/\s+/g, " ").trim();
  if (/We found .*unsaved draft/.test(text12) && /The last change did not reach the server/.test(text12)) {
    rec.pass("F-12", `draft banner="${text12}"`);
  } else {
    rec.fail("F-12", "draft banner missing after a failed write", `"${text12}" — ${await shot(page, "F-12-1689x1277")}`);
  }

  // F-13: Discard drops the draft and leaves the server document alone
  const serverBefore13 = await savedProject(page, id);
  await banner12.locator("button", { hasText: "Discard" }).click();
  await page.waitForTimeout(600);
  const after13 = {
    banner: await page.locator(".se-conflict[role='alert']").count(),
    draft: await page.evaluate((projectId) => {
      return localStorage.getItem(`studio:draft:${projectId}`) ? 1 : 0;
    }, id),
  };
  const serverAfter13 = await savedProject(page, id);
  if (after13.banner === 0 && after13.draft === 0 && JSON.stringify(serverBefore13.data.lanes) === JSON.stringify(serverAfter13.data.lanes)) {
    rec.pass("F-13", `draft discarded; server document unchanged`);
  } else {
    rec.fail("F-13", "Discard did not clear the draft cleanly", JSON.stringify(after13) + ` — ${await shot(page, "F-13-1689x1277")}`);
  }

  // F-14: Restore draft applies it and writes it
  await page.route(PATCH, async (route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "boom" }) });
  });
  await moveClip(page);
  await page.waitForTimeout(1200);
  await page.unroute(PATCH);
  await page.reload();
  await expect(page.locator(".se-track").first()).toBeVisible({ timeout: 30_000 });
  const banner14 = page.locator(".se-conflict[role='alert']");
  await expect(banner14).toBeVisible({ timeout: 10_000 });
  await banner14.locator("button", { hasText: "Restore draft" }).click();
  await page.waitForTimeout(2500);
  const restored = {
    banner: await page.locator(".se-conflict[role='alert']").count(),
    chip: await chipText(page),
  };
  const lanes14 = (await savedProject(page, id)).data.lanes as any[];
  const moved14 = lanes14.filter((clip) => (clip.start ?? 0) > 0).length;
  if (restored.banner === 0 && /^Saved/.test(restored.chip) && moved14 >= 1) {
    rec.pass("F-14", `draft restored and written (chip="${restored.chip}", moved clips=${moved14})`);
  } else {
    rec.fail("F-14", "Restore draft did not apply/write the document", `${JSON.stringify(restored)} moved=${moved14} — ${await shot(page, "F-14-1689x1277")}`);
  }
});

test("F3 — 409 conflicts and the queued-write drop", async ({ page }) => {
  const id = await fresh(page, "ADF F-conflict");

  // F-15: a 409 opens the alertdialog and the chip is Save failed
  await page.route(PATCH, async (route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({ detail: "This project changed elsewhere." }),
    });
  });
  await moveClip(page);
  await page.waitForTimeout(1200);
  const dialog15 = page.locator(".se-conflict[role='alertdialog']");
  const text15 = ((await dialog15.textContent().catch(() => "")) ?? "").replace(/\s+/g, " ").trim();
  const chip15 = await chipText(page);
  if ((await dialog15.count()) === 1 && /This project changed in another tab/.test(text15) && /Save failed/.test(chip15)) {
    rec.pass("F-15", `alertdialog="${text15}"; chip="${chip15}"`);
  } else {
    rec.fail("F-15", "409 did not open the conflict dialog", `dialog=${await dialog15.count()} chip="${chip15}" — ${await shot(page, "F-15-1689x1277")}`);
  }

  // F-16: Keep mine writes without a version guard
  const bodies: string[] = [];
  await page.unroute(PATCH);
  await page.route(PATCH, async (route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    bodies.push(route.request().postData() ?? "");
    await route.continue().catch(() => undefined);
  });
  await dialog15.locator("button", { hasText: "Keep mine" }).click();
  await page.waitForTimeout(2500);
  const after16 = { dialog: await page.locator(".se-conflict[role='alertdialog']").count(), chip: await chipText(page) };
  await page.unroute(PATCH);
  if (after16.dialog === 0 && /^Saved/.test(after16.chip) && bodies.some((body) => !body.includes("expected_updated_at"))) {
    rec.pass("F-16", `Keep mine wrote without expected_updated_at; banner cleared; chip="${after16.chip}"`);
  } else {
    rec.fail("F-16", "Keep mine did not overwrite cleanly", `${JSON.stringify(after16)} bodies=${bodies.length} — ${await shot(page, "F-16-1689x1277")}`);
  }

  // F-17: Reload theirs takes the server document
  await page.route(PATCH, async (route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    await route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "moved" }) });
  });
  await moveClip(page);
  await page.waitForTimeout(1200);
  const dialog17 = page.locator(".se-conflict[role='alertdialog']");
  await dialog17.locator("button", { hasText: "Reload theirs" }).click();
  await page.waitForTimeout(2500);
  const after17 = { dialog: await page.locator(".se-conflict").count(), chip: await chipText(page) };
  await page.unroute(PATCH);
  if (after17.dialog === 0 && /^Saved/.test(after17.chip)) {
    rec.pass("F-17", `Reload theirs cleared the banner; chip="${after17.chip}"`);
  } else {
    rec.fail("F-17", "Reload theirs did not resolve", JSON.stringify(after17) + ` — ${await shot(page, "F-17-1689x1277")}`);
  }

  // F-18: after a failure the queued write is dropped (one PATCH, not two)
  let attempts18 = 0;
  await page.route(PATCH, async (route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    attempts18 += 1;
    // Hold the first write so the second edit is genuinely queued behind it.
    await new Promise((resolve) => setTimeout(resolve, 1200));
    await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "boom" }) });
  });
  await moveClip(page);
  await page.waitForTimeout(100);
  await moveClip(page);
  await page.waitForTimeout(3000);
  await page.unroute(PATCH);
  if (attempts18 === 1) {
    rec.pass("F-18", `one failed PATCH and the queued burst was dropped (attempts=${attempts18})`);
  } else {
    rec.fail("F-18", "queued write replayed after a failure", `attempts=${attempts18} — ${await shot(page, "F-18-1689x1277")}`);
  }
  await page.reload();
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  await dismissOverlays(page);
  await page.waitForTimeout(500);

  // F-19: rename then edit immediately → no 409
  let conflicts19 = 0;
  await page.route(PATCH, async (route) => {
    if (route.request().method() !== "PATCH") return route.continue();
    const response = await route.fetch();
    if (response.status() === 409) conflicts19 += 1;
    await route.fulfill({ response }).catch(() => undefined);
  });
  await page.locator(".se-chip").first().click();
  const renameRow = page.locator('[role="menuitem"]', { hasText: "Rename" }).first();
  await renameRow.click();
  const nameField = page.locator("#se-project-title");
  await nameField.fill("ADF F renamed");
  await page.locator('[role="dialog"] button', { hasText: /^Save$/ }).last().click();
  await page.waitForTimeout(150);
  await moveClip(page);
  await page.waitForTimeout(2500);
  const conflict19 = await page.locator(".se-conflict[role='alertdialog']").count();
  await page.unroute(PATCH);
  if (conflicts19 === 0 && conflict19 === 0) {
    rec.pass("F-19", `rename adopted the new updated_at; no 409 on the next edit`);
  } else {
    rec.fail("F-19", "rename + edit produced a 409", `409s=${conflicts19} banner=${conflict19} — ${await shot(page, "F-19-1689x1277")}`);
  }
  void id;
});

test("F4 — mirror chip states", async ({ page }) => {
  const id = await fresh(page, "ADF F-mirror");
  const syncBody = (status: string, extra: Record<string, unknown> = {}) =>
    JSON.stringify({
      status,
      suno_version_id: "v-1",
      last_error: null,
      synced_at: null,
      skipped_clips: [],
      state_sync: true,
      ...extra,
    });

  async function setMirror(status: string, extra: Record<string, unknown> = {}) {
    await page.unrouteAll();
    await page.route(/\/api\/v3\/web-music\/studio\/projects\/[0-9a-f-]+\/(sync|refresh)$/, async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: syncBody(status, extra) });
    });
    await page.reload();
    await expect(page.locator(".se-track").first()).toBeVisible({ timeout: 30_000 });
    await page.waitForTimeout(1200);
    const dot = page.locator(".se-sync-dot");
    return {
      state: await dot.getAttribute("data-state").catch(() => null),
      title: await dot.getAttribute("title").catch(() => null),
      count: await dot.count(),
    };
  }

  // F-20: pending (sync off / waiting for the first copy)
  const pending = await setMirror("pending", { state_sync: false });
  if (pending.count === 1 && pending.state === "pending" && /waiting for the first copy/.test(pending.title ?? "")) {
    rec.pass("F-20", `dot data-state=${pending.state}; title="${pending.title}"`);
  } else {
    rec.fail("F-20", "pending mirror state differs", JSON.stringify(pending) + ` — ${await shot(page, "F-20-1689x1277")}`);
  }

  // F-21: linked with state_sync false mentions paused writes
  const linked = await setMirror("linked", { state_sync: false });
  if (linked.state === "linked" && /staged/.test(linked.title ?? "") && /paused/.test(linked.title ?? "")) {
    rec.pass("F-21", `dot data-state=${linked.state}; title="${linked.title}"`);
  } else {
    rec.fail("F-21", "linked mirror tooltip differs", JSON.stringify(linked) + ` — ${await shot(page, "F-21-1689x1277")}`);
  }

  // F-22: synced
  const synced = await setMirror("synced");
  if (synced.state === "synced" && /mirrored/.test(synced.title ?? "")) {
    rec.pass("F-22", `dot data-state=${synced.state}; title="${synced.title}"`);
  } else {
    rec.fail("F-22", "synced mirror state differs", JSON.stringify(synced) + ` — ${await shot(page, "F-22-1689x1277")}`);
  }

  // F-23: conflict opens the dialog on load
  const conflict = await setMirror("conflict");
  const conflictDialog = page.locator('[aria-label="Suno version conflict"]');
  const conflictShown = await conflictDialog.count();
  if (conflict.state === "conflict" && conflictShown === 1) {
    rec.pass("F-23", `dot data-state=${conflict.state}; dialog on load=${conflictShown}`);
  } else {
    rec.fail("F-23", "conflict state did not open the dialog", `${JSON.stringify(conflict)} dialog=${conflictShown} — ${await shot(page, "F-23-1689x1277")}`);
  }

  // F-24: error carries last_error and skipped clips
  const error = await setMirror("error", { last_error: "provider rejected the push", skipped_clips: ["clip-a", "clip-b"] });
  if (error.state === "error" && /provider rejected the push/.test(error.title ?? "")) {
    rec.pass("F-24", `dot data-state=${error.state}; title="${error.title}"`);
  } else {
    rec.fail("F-24", "error mirror tooltip differs", JSON.stringify(error) + ` — ${await shot(page, "F-24-1689x1277")}`);
  }

  // F-25: the 15 s poll issues a refresh without a reload
  await page.unrouteAll();
  const reads: string[] = [];
  await page.route(/\/api\/v3\/web-music\/studio\/projects\/[0-9a-f-]+\/(sync|refresh)$/, async (route) => {
    reads.push(route.request().url().split("/").pop() ?? "");
    await route.fulfill({ status: 200, contentType: "application/json", body: syncBody("synced") });
  });
  const before25 = reads.length;
  await page.waitForTimeout(17_000);
  const polls = reads.length - before25;
  await page.unrouteAll();
  if (polls >= 1) {
    rec.pass("F-25", `idle 17 s produced ${polls} mirror read(s) (${reads.slice(-3).join(",")})`);
  } else {
    rec.fail("F-25", "the mirror did not poll while idle", `reads=${polls} — ${await shot(page, "F-25-1689x1277")}`);
  }

  // F-26: a save is followed by a mirror read ~2 s later
  const reads26: number[] = [];
  await page.route(/\/api\/v3\/web-music\/studio\/projects\/[0-9a-f-]+\/(sync|refresh)$/, async (route) => {
    reads26.push(Date.now());
    await route.fulfill({ status: 200, contentType: "application/json", body: syncBody("synced") });
  });
  const savedAt = Date.now();
  await moveClip(page);
  await waitSaved(page);
  await page.waitForTimeout(3500);
  await page.unrouteAll();
  const afterSave = reads26.filter((stamp) => stamp > savedAt).length;
  if (afterSave >= 1) {
    rec.pass("F-26", `a mirror read followed the save (${afterSave} read(s) within 3.5 s)`);
  } else {
    rec.fail("F-26", "no mirror read after the save", `reads=${afterSave} — ${await shot(page, "F-26-1689x1277")}`);
  }
  void id;
});

test("F5 — provider refusals and failures", async ({ page }) => {
  await fresh(page, "ADF F-provider");
  const GENERATE = /\/api\/v3\/web-music\/generate$/;

  // F-27: empty balance → credits notice + View plans
  await page.route(GENERATE, async (route) => {
    await route.fulfill({
      status: 402,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Insufficient credits." }),
    });
  });
  await page.locator('[aria-label="Describe a part to generate"]').fill("a wide pad");
  await page.locator('[aria-label="Describe a part to generate"]').press("Enter");
  await page.waitForTimeout(2000);
  const notice27 = page.locator(".se-assistant-notice.credits");
  const viewPlans = await notice27.locator("a", { hasText: "View plans" }).count();
  if ((await notice27.count()) === 1 && viewPlans === 1) {
    rec.pass("F-27", `credits notice="${((await notice27.textContent()) ?? "").replace(/\s+/g, " ").trim().slice(0, 80)}" + View plans`);
  } else {
    rec.fail("F-27", "credits refusal did not render the notice", `count=${await notice27.count()} plans=${viewPlans} — ${await shot(page, "F-27-1689x1277")}`);
  }

  // F-28: policy refusal → Edit prompt refocuses the input
  await page.unroute(GENERATE);
  await page.route(GENERATE, async (route) => {
    await route.fulfill({
      status: 400,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Prompt blocked by policy." }),
    });
  });
  await page.locator('[aria-label="Describe a part to generate"]').fill("copy a famous song");
  await page.locator('[aria-label="Describe a part to generate"]').press("Enter");
  await page.waitForTimeout(2000);
  const notice28 = page.locator(".se-assistant-notice");
  const edit28 = notice28.locator("button", { hasText: "Edit prompt" });
  const editCount = await edit28.count();
  if (editCount === 1) await edit28.click();
  await page.waitForTimeout(300);
  const focused28 = await page.evaluate(() => (document.activeElement as HTMLElement | null)?.getAttribute("aria-label"));
  const text28 = ((await notice28.textContent().catch(() => "")) ?? "").replace(/\s+/g, " ").trim();
  if (editCount === 1 && focused28 === "Describe a part to generate" && /refused/.test(text28)) {
    rec.pass("F-28", `policy notice="${text28.slice(0, 70)}"; Edit prompt refocused the input`);
  } else {
    rec.fail("F-28", "policy refusal notice differs", `edit=${editCount} focus=${focused28} text="${text28}" — ${await shot(page, "F-28-1689x1277")}`);
  }

});

test("F5b — transform refusals", async ({ page }) => {
  await fresh(page, "ADF F-transforms");
  // F-29: a transform refused for credits
  await page.route(/\/api\/v3\/web-music\/studio\/generations\/[^/]+\/cover$/, async (route) => {
    await route.fulfill({
      status: 402,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Insufficient credits." }),
    });
  });
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click({ button: "right" });
  await page.locator(".se-clip-menu button", { hasText: "Cover…" }).first().click();
  const coverDialog = page.locator('[aria-label="Cover this clip"]');
  if ((await coverDialog.count()) === 1) {
    await coverDialog.locator('input[aria-label="Cover style"]').fill("a quieter cover");
    await coverDialog.locator("button", { hasText: "Generate cover" }).click();
    await page.waitForTimeout(2500);
  }
  const notice29 = page.locator(".se-transform-notice.credits");
  const text29 = ((await notice29.textContent().catch(() => "")) ?? "").replace(/\s+/g, " ").trim();
  if ((await notice29.count()) === 1 && /Not enough credits/.test(text29) && /does not cover/i.test(text29)) {
    rec.pass("F-29", `transform credits notice="${text29.slice(0, 100)}"`);
  } else {
    rec.fail("F-29", "transform credits notice missing", `count=${await notice29.count()} "${text29}" — ${await shot(page, "F-29-1689x1277")}`);
  }

  // F-30: any other transform failure, dismissible
  await page.unrouteAll();
  await page.route(/\/api\/v3\/web-music\/studio\/generations\/[^/]+\/cover$/, async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ detail: "provider exploded" }),
    });
  });
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click({ button: "right" });
  await page.locator(".se-clip-menu button", { hasText: "Cover…" }).first().click();
  if ((await page.locator('[aria-label="Cover this clip"]').count()) === 1) {
    await page.locator('[aria-label="Cover this clip"] input[aria-label="Cover style"]').fill("a stranger cover");
    await page.locator('[aria-label="Cover this clip"] button', { hasText: "Generate cover" }).click();
    await page.waitForTimeout(2500);
  }
  const notice30 = page.locator(".se-transform-notice");
  const text30 = ((await notice30.textContent().catch(() => "")) ?? "").replace(/\s+/g, " ").trim();
  const dismiss30 = notice30.locator('button[aria-label="Dismiss"]');
  if ((await notice30.count()) === 1 && /That edit did not run/.test(text30)) {
    await dismiss30.click();
    await page.waitForTimeout(300);
  }
  const gone30 = await page.locator(".se-transform-notice").count();
  if (/That edit did not run/.test(text30) && gone30 === 0) {
    rec.pass("F-30", `failure notice="${text30.slice(0, 90)}"; dismissed`);
  } else {
    rec.fail("F-30", "generic transform failure notice differs", `"${text30}" gone=${gone30} — ${await shot(page, "F-30-1689x1277")}`);
  }

});

test("F5c — library, stems and the conflict busy guard", async ({ page }) => {
  await fresh(page, "ADF F-failures");
  // F-31: library load failure offers Retry
  await page.route(/\/api\/v3\/web-music\/(generations|playlists)/, async (route) => {
    await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "library down" }) });
  });
  await page.locator('.se-foot button[aria-label="Toggle library"]').click();
  await page.waitForTimeout(3000);
  const libError = page.locator(".se-lib-error");
  const libRetry = page.locator(".se-lib-error button", { hasText: "Retry" });
  const libState = { error: await libError.count(), retry: await libRetry.count() };
  if (libState.error >= 1 && libState.retry >= 1) {
    rec.pass("F-31", `.se-lib-error=${libState.error}; Retry button=${libState.retry}`);
  } else {
    rec.fail("F-31", "library failure did not surface an error with retry", JSON.stringify(libState) + ` — ${await shot(page, "F-31-1689x1277")}`);
  }

});

test("F5d — stem failure and the conflict busy guard", async ({ page }) => {
  const t0 = Date.now();
  const mark = (label: string) => console.log(`[F5d +${Math.round((Date.now() - t0) / 1000)}s] ${label}`);
  // The provenance strip (and its stem status) only renders when the clip's song
  // resolves in the library, so the library list is mocked with the fixture's song.
  await page.route(/\/api\/v3\/web-music\/generations\?/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "song-adf-1",
            title: "ADF Song",
            status: "complete",
            style: "test",
            model: "v6",
            created_at: "2026-11-01T00:00:00Z",
            clips: [],
          },
        ],
      }),
    });
  });
  await fresh(page, "ADF F-stems");
  mark("fresh");
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  await page.waitForTimeout(1500);
  mark("clip selected");
  const strip = page.locator(".se-clip-source");
  const stripShown = await strip.count();
  // F-32: stem separation failure reports the classified error
  await page.route(/\/api\/v3\/web-music\/studio\/generations\/[^/]+\/stems$/, async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ detail: "stem backend unavailable" }),
    });
  });
  const stripButton = strip.locator("button", { hasText: "Get stems" }).first();
  if (stripShown === 1) {
    await stripButton.click({ timeout: 8000 });
    const stemsDialog = page.locator('[aria-label="Get stems"]');
    if ((await stemsDialog.count()) === 1) {
      await stemsDialog.locator("button", { hasText: /Separate/ }).last().click({ timeout: 8000 });
      await page.waitForTimeout(2500);
    }
  }
  mark("stems requested");
  const stemStatus = page.locator(".se-stem-status");
  const stemText = ((await stemStatus.textContent().catch(() => "")) ?? "").replace(/\s+/g, " ").trim();
  const stemOff = await stemStatus.first().getAttribute("class").catch(() => "");
  if (/stem backend unavailable|failed|error/i.test(stemText) && /off/.test(stemOff ?? "")) {
    rec.pass("F-32", `.se-stem-status.off="${stemText.slice(0, 90)}"`);
  } else {
    rec.fail(
      "F-32",
      "stem failure was not reported in the clip strip",
      `strip=${stripShown} text="${stemText}" class="${stemOff}" (screenshot not captured: capture stalls with the strip open)`
    );
  }

  mark("F-32 measured");
  // F-33: the conflict dialog's actions disable while busy
  await page.unrouteAll();
  await page.route(/\/api\/v3\/web-music\/studio\/projects\/[0-9a-f-]+\/(sync|refresh)$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "conflict",
        suno_version_id: "v-2",
        last_error: null,
        synced_at: null,
        skipped_clips: [],
        state_sync: true,
      }),
    });
  });
  await page.reload();
  await expect(page.locator(".se-track").first()).toBeVisible({ timeout: 30_000 });
  mark("reloaded");
  const dialog33 = page.locator('[aria-label="Suno version conflict"]');
  await expect(dialog33).toBeVisible({ timeout: 10_000 });
  let keepMineRequests = 0;
  await page.route(/\/keep-mine$/, async (route) => {
    keepMineRequests += 1;
    await new Promise((resolve) => setTimeout(resolve, 1200));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "synced",
        suno_version_id: "v-3",
        last_error: null,
        synced_at: null,
        skipped_clips: [],
        state_sync: true,
      }),
    });
  });
  const keep = dialog33.locator("button", { hasText: "Keep mine" });
  await keep.click();
  await page.waitForTimeout(200);
  const disabledDuring = await dialog33.locator("button:disabled").count();
  await keep.click({ force: true }).catch(() => undefined);
  await page.waitForTimeout(2500);
  if (keepMineRequests === 1 && disabledDuring >= 1) {
    rec.pass("F-33", `busy guard: ${disabledDuring} disabled action(s); one keep-mine request`);
  } else {
    rec.fail("F-33", "conflict actions are not guarded while busy", `requests=${keepMineRequests} disabled=${disabledDuring} — ${await shot(page, "F-33-1689x1277")}`);
  }
  await page.unrouteAll();
});



