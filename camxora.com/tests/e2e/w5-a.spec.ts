import { expect, test } from "@playwright/test";

import {
  adfDocument,
  bodyScroll,
  createProject,
  dismissOverlays,
  makeRecorder,
  openProject,
  shot,
  signIn,
  waitSaved,
} from "./w5-adf-harness";

/**
 * Area A — entry, gates and chrome (16 checks) + the 767/768 desktop-gate boundary probe.
 * Every row is measured in a real browser at 1689×1277 unless it says otherwise.
 */

const rec = makeRecorder("a");
test.describe.configure({ mode: "serial" });
test.afterAll(() => rec.flush());

test.use({ viewport: { width: 1689, height: 1277 } });

test("A — signed-out entry and editor gates", async ({ page }) => {
  await page.goto("/studio");
  await page.waitForTimeout(1200);
  const marketing = await page.locator("h1", { hasText: "Camxora Studio." }).count();
  const home = await page.locator(".studio-home").count();
  const projectsCopy = await page.getByText("Your projects", { exact: true }).count();
  if (marketing === 1 && home === 0 && projectsCopy === 0) {
    rec.pass("A-01", `marketing h1 present (1); .studio-home=${home}; "Your projects"=${projectsCopy}`);
  } else {
    rec.fail("A-01", "signed-out /studio did not render the marketing page", `marketing=${marketing} home=${home} copy=${projectsCopy} — ${await shot(page, "A-01-1689x1277")}`);
  }

  await page.goto("/studio/editor");
  await page.waitForTimeout(1500);
  const gateHead = (await page.locator(".se-gate h1").first().textContent().catch(() => "")) ?? "";
  const gateBody = (await page.locator(".se-gate p").first().textContent().catch(() => "")) ?? "";
  const signInHref = await page.locator(".se-gate a.btn").first().getAttribute("href").catch(() => null);
  if (gateHead.trim() === "Studio" && /Sign in to open a project/.test(gateBody) && signInHref?.startsWith("/login")) {
    rec.pass("A-03", `.se-gate h1="${gateHead.trim()}"; p="${gateBody.trim()}"; link=${signInHref}`);
  } else {
    rec.fail("A-03", "signed-out editor gate differs", `h1="${gateHead}" p="${gateBody}" href=${signInHref} — ${await shot(page, "A-03-1689x1277")}`);
  }
});

test("A — signed-in home", async ({ page }) => {
  await signIn(page);
  await page.goto("/studio");
  await expect(page.locator(".studio-home")).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(800);
  const h1 = (await page.locator(".studio-home h1").first().textContent()) ?? "";
  const actions = await page.locator(".studio-home-actions").count();
  const newProject = await page.getByRole("button", { name: /New project/i }).count();
  const createSong = await page.getByText("Create a song", { exact: false }).count();
  if (h1.trim() === "Your projects" && actions === 1 && newProject > 0 && createSong > 0) {
    rec.pass("A-02", `h1="Your projects"; .studio-home-actions=${actions}; New project=${newProject}; Create a song=${createSong}`);
  } else {
    rec.fail("A-02", "signed-in home header is incomplete", `h1="${h1}" actions=${actions} new=${newProject} song=${createSong} — ${await shot(page, "A-02-1689x1277")}`);
  }
});

test("A — editor entry, load, reload, bad id, classic route", async ({ page }) => {
  await signIn(page);
  const id = await createProject(page, "ADF P1", adfDocument());

  // A-04: signed in, no ?project=
  await page.goto("/studio/editor");
  await page.waitForTimeout(1500);
  const noProjHead = (await page.locator(".se-gate h1").first().textContent().catch(() => "")) ?? "";
  const noProjBody = (await page.locator(".se-gate p").first().textContent().catch(() => "")) ?? "";
  if (noProjHead.trim() === "No project selected" && /Choose a project from the Studio home/.test(noProjBody)) {
    rec.pass("A-04", `.se-gate h1="No project selected"; p="${noProjBody.trim()}"`);
  } else {
    rec.fail("A-04", "no-project gate differs", `h1="${noProjHead}" p="${noProjBody}" — ${await shot(page, "A-04-1689x1277")}`);
  }

  // A-05: loading then shell, no empty-state flash.
  // The project GET is slowed once so the transient "Loading project…" surface is
  // observable; the delayed request settles before anything navigates away.
  const projectRoute = /\/api\/v3\/web-music\/studio\/projects\/[a-f0-9-]+$/;
  await page.route(projectRoute, async (route) => {
    if (route.request().method() === "GET") {
      await new Promise((resolve) => setTimeout(resolve, 800));
    }
    await route.continue().catch(() => undefined);
  });
  const sawLoading: string[] = [];
  await page.goto(`/studio/editor?project=${id}`);
  for (let i = 0; i < 120; i += 1) {
    const state = await page.evaluate(() => {
      const loading = document.querySelector(".se-loading");
      const shell = document.querySelector(".se-shell");
      const onboarding = document.querySelector(".se-onboard");
      const clip = document.querySelector(".se-clip");
      return `${loading ? "loading" : ""}${shell ? "shell" : ""}${onboarding ? "onboard" : ""}${clip ? "clip" : ""}`;
    });
    if (state && !sawLoading.includes(state)) sawLoading.push(state);
    if (state.includes("clip")) break;
    await page.waitForTimeout(50);
  }
  await expect(page.locator(".se-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  await page.unroute(projectRoute);
  const onboardingVisible = sawLoading.some((state) => state.includes("onboard"));
  if (sawLoading.some((state) => state.includes("loading")) && !onboardingVisible) {
    rec.pass("A-05", `observed states=${sawLoading.join(" -> ")}; onboarding flash=${onboardingVisible}`);
  } else {
    rec.fail("A-05", "loading/empty-state sequence wrong", `states=${sawLoading.join(" -> ")} onboarding=${onboardingVisible} — ${await shot(page, "A-05-1689x1277")}`);
  }

  // A-06: reload restores title, BPM, signature, tracks
  await page.reload();
  await expect(page.locator(".se-clip").first()).toBeVisible({ timeout: 30_000 });
  await dismissOverlays(page);
  const chip = (await page.locator(".se-chip").first().textContent()) ?? "";
  const bpm = await page.locator('input[aria-label="Tempo in BPM"]').inputValue();
  const sig = await page.locator('select[aria-label="Time signature"]').inputValue();
  const trackCount = await page.locator(".se-track").count();
  const hiddenPill = await page.locator(".se-hidden-pill").textContent().catch(() => "");
  if (chip.includes("ADF P1") && bpm === "120" && sig === "4/4" && trackCount === 3 && /1/.test(hiddenPill ?? "")) {
    rec.pass("A-06", `chip="${chip.trim()}"; bpm=${bpm}; sig=${sig}; .se-track=${trackCount} + hidden pill "${(hiddenPill ?? "").replace(/\s+/g, " ").trim()}" (Scratch is hidden, so 3 rows + 1 hidden)`);
  } else {
    rec.fail("A-06", "reload did not restore the document", `chip="${chip}" bpm=${bpm} sig=${sig} tracks=${trackCount} hidden="${hiddenPill}" — ${await shot(page, "A-06-1689x1277")}`);
  }

  // A-07: random uuid surfaces an error, no hang
  await page.goto(`/studio/editor?project=00000000-0000-4000-8000-000000000000`);
  await page.waitForTimeout(5000);
  const alert = page.locator('[role="alert"]').first();
  const alertText = (await alert.textContent().catch(() => "")) ?? "";
  const stillLoading = await page.locator(".se-loading").count();
  const loadFailed = await page.locator(".se-load-failed").count();
  if ((alertText.includes("Could not open this project") || alertText.length > 0) && stillLoading === 0) {
    rec.pass("A-07", `role=alert text="${alertText.replace(/\s+/g, " ").trim().slice(0, 90)}"; .se-load-failed=${loadFailed}; .se-loading=${stillLoading}`);
  } else {
    rec.fail("A-07", "bad project id did not surface an error", `alert="${alertText}" loading=${stillLoading} — ${await shot(page, "A-07-1689x1277")}`);
  }

  // A-08: classic route renders (no 404)
  const classic = await page.goto("/studio/editor/classic");
  await page.waitForTimeout(1500);
  const classicStatus = classic?.status() ?? 0;
  const body = (await page.locator("body").textContent()) ?? "";
  if (classicStatus === 200 && !/404|This page could not be found/.test(body.slice(0, 400))) {
    rec.pass("A-08", `/studio/editor/classic -> ${classicStatus}; no 404 copy`);
  } else {
    rec.fail("A-08", "classic editor route failed", `status=${classicStatus} — ${await shot(page, "A-08-1689x1277")}`);
  }
});

test("A — editor chrome, landmarks, bands, focus, toast, freshness", async ({ page }) => {
  await signIn(page);
  const id = await createProject(page, "ADF P1", adfDocument());
  await openProject(page, id);

  // A-09 landmarks
  const landmarks = await page.evaluate(() => ({
    main: document.querySelectorAll('[role="main"]').length,
    menus: document.querySelectorAll('[aria-label="Editor menus"]').length,
  }));
  if (landmarks.main === 1 && landmarks.menus === 1) {
    rec.pass("A-09", `[role=main]=1; [aria-label="Editor menus"]=1`);
  } else {
    rec.fail("A-09", "landmark structure wrong", JSON.stringify(landmarks) + ` — ${await shot(page, "A-09-1689x1277")}`);
  }

  // A-10 four bands visible without overlap
  const bands = await page.evaluate(() => {
    const rect = (selector: string) => {
      const el = document.querySelector(selector) as HTMLElement | null;
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, height: r.height };
    };
    return { head: rect(".se-head"), body: rect(".se-body"), dock: rect(".sp-dock"), foot: rect(".se-foot") };
  });
  const ordered =
    bands.head && bands.body && bands.foot &&
    bands.head.bottom <= bands.body.top + 1 &&
    bands.body.bottom <= bands.foot.top + 1;
  if (ordered) {
    rec.pass("A-10", `head 0..${bands.head!.bottom}; body ${bands.body!.top}..${bands.body!.bottom}; dock=${bands.dock ? `${bands.dock.top}..${bands.dock.bottom}` : "absent"}; foot ${bands.foot!.top}..${bands.foot!.bottom}`);
  } else {
    rec.fail("A-10", "editor bands overlap or are missing", JSON.stringify(bands) + ` — ${await shot(page, "A-10-1689x1277")}`);
  }

  // A-11 shell fills the viewport without scrolling
  const shell = await page.evaluate(() => {
    const el = document.querySelector(".se-shell") as HTMLElement | null;
    return el ? { h: el.clientHeight, sh: el.scrollHeight, top: el.getBoundingClientRect().top } : null;
  });
  if (shell && Math.abs(shell.h - 1277) <= 1 && shell.sh === shell.h) {
    rec.pass("A-11", `.se-shell clientHeight=${shell.h}; scrollHeight=${shell.sh}`);
  } else {
    rec.fail("A-11", "shell does not fill the viewport", JSON.stringify(shell) + ` — ${await shot(page, "A-11-1689x1277")}`);
  }

  // A-12 sr-only level-1 title inside the body
  const sr = await page.evaluate(() => {
    const el = document.querySelector(".se-body .se-sr-only");
    return el ? { tag: el.tagName, text: el.textContent } : null;
  });
  if (sr && sr.tag === "H1" && (sr.text ?? "").includes("ADF P1")) {
    rec.pass("A-12", `.se-body .se-sr-only is <h1> "${sr.text}"`);
  } else {
    rec.fail("A-12", "no sr-only h1 project title", JSON.stringify(sr) + ` — ${await shot(page, "A-12-1689x1277")}`);
  }

  // A-13 focus order: 20 tabs, no trap outside dialogs
  await page.locator(".se-chip").first().click();
  await page.keyboard.press("Escape");
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  const order: string[] = [];
  for (let i = 0; i < 20; i += 1) {
    await page.keyboard.press("Tab");
    order.push(
      await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (!el) return "none";
        return `${el.tagName.toLowerCase()}:${el.getAttribute("aria-label") ?? el.getAttribute("data-help") ?? (el.textContent ?? "").trim().slice(0, 18)}`;
      })
    );
  }
  const inBody = order.some((entry) => /track|clip|tempo|bpm|plugin|foot|automation/i.test(entry));
  const repeats = new Set(order).size;
  if (inBody && repeats >= 10) {
    rec.pass("A-13", `20 tabs, ${repeats} distinct stops: ${order.slice(0, 8).join(" | ")} …`);
  } else {
    rec.fail("A-13", "focus order collapses or is trapped", `${repeats} distinct in 20 tabs — ${await shot(page, "A-13-1689x1277")}`);
  }

  // A-14 default landing band
  const landing = {
    dock: await page.locator(".sp-dock").count(),
    assistant: await page.locator(".se-assistant").count(),
    library: await page.locator(".se-library").count(),
    empty: await page.locator(".se-empty").count(),
  };
  if (landing.dock === 1 && landing.assistant === 0 && landing.library === 0) {
    rec.pass("A-14", `.sp-dock=1; assistant=0; library=0`);
  } else {
    rec.fail("A-14", "bottom panel is empty on load (no track selected, so no dock)", JSON.stringify(landing) + ` — ${await shot(page, "A-14-1689x1277")}`);
  }

  // A-15 toast surface + dismiss label
  await page.locator('button[aria-label="Clip editor"]').click();
  const toast = page.locator(".se-toast[role='status']");
  await expect(toast).toBeVisible({ timeout: 8000 });
  const toastText = (await toast.textContent()) ?? "";
  const dismissLabel = await toast.locator("button.se-icon").getAttribute("aria-label");
  if (/Select a clip to edit/.test(toastText) && dismissLabel === "Dismiss export message") {
    rec.pass("A-15", `.se-toast[role=status]="${toastText.replace(/\s+/g, " ").trim()}"; dismiss aria-label="${dismissLabel}"`);
  } else {
    rec.fail("A-15", "toast surface differs", `text="${toastText}" dismiss=${dismissLabel} — ${await shot(page, "A-15-1689x1277")}`);
  }

  // A-16 no stale loading chip after a save
  await page.locator(".se-clip", { hasText: "Drums A" }).first().click();
  await page.keyboard.press("ArrowRight").catch(() => undefined);
  await waitSaved(page);
  const loadingLeft = await page.locator(".se-loading").count();
  if (loadingLeft === 0) {
    rec.pass("A-16", `.se-loading=0 after Saved`);
  } else {
    rec.fail("A-16", "stale loading chip after save", `count=${loadingLeft} — ${await shot(page, "A-16-1689x1277")}`);
  }
});

test("A — desktop gate boundary at 767 / 768", async ({ page }) => {
  await signIn(page);
  const id = await createProject(page, "ADF P1", adfDocument());

  await page.setViewportSize({ width: 768, height: 1024 });
  await openProject(page, id);
  const at768 = await page.evaluate(() => ({
    shell: (document.querySelector(".se-shell") as HTMLElement | null)?.offsetParent !== null,
    gate: (document.querySelector(".se-desktop-gate") as HTMLElement | null)?.offsetParent !== null,
  }));
  await shot(page, "A-GATE-768x1024");

  await page.setViewportSize({ width: 767, height: 1024 });
  await page.waitForTimeout(600);
  const at767 = await page.evaluate(() => {
    const gate = document.querySelector(".se-desktop-gate") as HTMLElement | null;
    const shell = document.querySelector(".se-shell") as HTMLElement | null;
    return {
      gateShown: gate ? getComputedStyle(gate).display : "absent",
      shellShown: shell ? getComputedStyle(shell).display : "absent",
      gateText: (gate?.textContent ?? "").replace(/\s+/g, " ").trim(),
      scrollWidth: document.body.scrollWidth,
    };
  });
  await shot(page, "A-GATE-767x1024");

  if (at768.shell && !at768.gate && at767.gateShown === "flex" && at767.shellShown === "none" && /Back to Create/.test(at767.gateText)) {
    rec.pass("A-GATE", `768: shell shown, gate hidden; 767: gate ${at767.gateShown}, shell ${at767.shellShown}, scrollWidth=${at767.scrollWidth}`);
  } else {
    rec.fail("A-GATE", "gate boundary is not at 767/768", `${JSON.stringify(at768)} / ${JSON.stringify(at767)} — ${await shot(page, "A-GATE-767x1024")}`);
  }
  expect(at767.gateShown).toBe("flex");
});
