import { config } from "./config.js";
import { apiHeaders, resolveJwt } from "./auth.js";
import { Solver } from "@2captcha/captcha-solver";
import { chromium, BrowserContext, Page } from "playwright-core";

const USER_AGENT =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36";

/**
 * Ask Suno whether a captcha is currently required for generation.
 * This is the gate that keeps us from paying for unnecessary solves.
 */
export async function captchaRequired(): Promise<boolean> {
  try {
    const jwt = await resolveJwt();
    const res = await fetch(`${config.apiUrl}/api/c/check`, {
      method: "POST",
      headers: apiHeaders(jwt, config.deviceId, { "content-type": "application/json" }),
      body: JSON.stringify({ ctype: "generation" }),
    });
    if (!res.ok) return true; // assume required on error
    const data = (await res.json()) as { required?: boolean };
    console.error(`[captcha] /api/c/check -> ${res.status} required=${data.required}`);
    return data.required ?? true;
  } catch (e) {
    console.error("[captcha] /api/c/check error:", e);
    return true;
  }
}

/**
 * Solve Suno's hCaptcha via 2Captcha (coordinates method) and return the token.
 * Opens a headless browser, triggers the generate flow, clicks the solved
 * coordinates, then intercepts the page's /api/generate/v2/ request to grab
 * the captcha token (aborting it so no credit is consumed).
 */
export interface CaptchaAccount {
  jwt: string;
  deviceId: string;
  clientCookie?: string;
  twoCaptchaKey?: string;
}

export async function solveCaptchaForAccount(account: CaptchaAccount): Promise<string> {
  const twoCaptchaKey = account.twoCaptchaKey ?? config.twoCaptchaKey;
  if (!twoCaptchaKey) {
    throw new Error("TWOCAPTCHA_KEY is required to solve captcha.");
  }
  const solver = new Solver(twoCaptchaKey);

  console.error("[captcha] launching chrome...");
  const browser = await chromium.launch({
    channel: "chrome",
    headless: true,
    args: [
      "--disable-blink-features=AutomationControlled",
      "--no-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--disable-gpu-compositing",
      "--disable-software-rasterizer",
    ],
  });
  console.error("[captcha] chrome launched");

  try {
    const context = await browser.newContext({
      userAgent: USER_AGENT,
      locale: "en-US",
      viewport: { width: 1280, height: 800 },
    });
    await context.addInitScript(() => {
      Object.defineProperty(navigator, "webdriver", { get: () => undefined });
    });
    await seedCookies(context, account);

    const page = await context.newPage();

    // Capture the captcha token from the request the page fires on success.
    const tokenPromise = new Promise<string>((resolve, reject) => {
      page.route("**/api/generate/v2/**", async (route) => {
        try {
          const body = route.request().postDataJSON() as { token?: string };
          await route.abort();
          if (body?.token) resolve(body.token);
          else reject(new Error("generate request had no token field"));
        } catch (e) {
          reject(e instanceof Error ? e : new Error(String(e)));
        }
      });
    });

    await page.goto("https://suno.com/create", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    console.error("[captcha] navigated to /create");
    await page
      .waitForSelector('textarea[maxlength="3000"]', { timeout: 60_000 })
      .catch(() => {});
    console.error("[captcha] textarea ready");

    const textarea = page.locator('textarea[maxlength="3000"]').first();
    await textarea.fill("Lorem ipsum dolor sit amet");

    const createBtn = page.locator('button[aria-label="Create song"]').first();
    await createBtn.click();
    console.error("[captcha] create clicked, url =", page.url());

    // Diagnostic: list iframes to confirm hCaptcha mount + selector.
    await page.waitForTimeout(3_000);
    const iframes = await page.evaluate(() =>
      Array.from(document.querySelectorAll("iframe")).map((f) => ({
        title: f.title,
        name: f.name,
        src: (f.src || "").slice(0, 120),
      })),
    );
    console.error("[captcha] iframes:", JSON.stringify(iframes, null, 2));

    await solveChallenge(page, solver);

    return await Promise.race([
      tokenPromise,
      new Promise<string>((_, reject) =>
        setTimeout(
          () => reject(new Error("captcha solve timed out after 120s")),
          120_000,
        ),
      ),
    ]);
  } finally {
    await browser.close();
  }
}

async function seedCookies(context: BrowserContext, account: CaptchaAccount): Promise<void> {
  const cookies = [
    { name: "__session", value: account.jwt, domain: ".suno.com", path: "/" },
    {
      name: "ajs_anonymous_id",
      value: account.deviceId,
      domain: ".suno.com",
      path: "/",
    },
    {
      name: "suno_device_id",
      value: account.deviceId,
      domain: ".suno.com",
      path: "/",
    },
  ];
  if (account.clientCookie) {
    cookies.push({
      name: "__client",
      value: account.clientCookie,
      domain: ".suno.com",
      path: "/",
    });
  }
  await context.addCookies(cookies);
}

/** CLI/global convenience wrapper: solve using the default configured account. */
export async function solveCaptcha(): Promise<string> {
  const jwt = await resolveJwt();
  return solveCaptchaForAccount({
    jwt,
    deviceId: config.deviceId,
    clientCookie: config.clientCookie,
    twoCaptchaKey: config.twoCaptchaKey,
  });
}

async function solveChallenge(page: Page, solver: Solver): Promise<void> {
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      const anyFrame = await page.evaluate(() => {
        const frames = Array.from(document.querySelectorAll("iframe"));
        const candidates = frames.filter((f) => {
          const src = f.src || "";
          const title = f.title || "";
          return (
            /hcaptcha/i.test(src + title) ||
            /captcha|verify|check|security|challenge/i.test(title + src)
          );
        });
        return candidates.map((f) => ({
          title: f.title,
          id: f.id,
          name: f.getAttribute("name"),
          src: (f.src || "").slice(0, 200),
          rect: {
            visible:
              (f as HTMLIFrameElement).offsetWidth > 20 &&
              (f as HTMLIFrameElement).offsetHeight > 20,
            w: (f as HTMLIFrameElement).offsetWidth,
            h: (f as HTMLIFrameElement).offsetHeight,
          },
        }));
      });
      console.error(`[captcha] solveChallenge attempt=${attempt} captcha candidate iframes on page:`, JSON.stringify(anyFrame));

      const byName = page.frameLocator('iframe[title*="hCaptcha"]');
      const bySrc = page.frameLocator('iframe[src*="hcaptcha.com"]');
      const byAny = page.frameLocator('iframe[src*="captcha"],iframe[title*="Captcha"],iframe[title*="captcha"]');
      const candidateLocators = [byName, bySrc, byAny];
      const visibleSelectors = [".challenge-container", ".h-captcha", ".captcha-solver", "iframe", "#anchor", ".reset-container", ".button-submit"];
      let foundVisible = false;
      let selectedChallenge = null as any;
      for (const fl of candidateLocators) {
        for (const sel of visibleSelectors) {
          try {
            const target = fl.locator(sel).first();
            await target.waitFor({ state: "visible", timeout: 4000 });
            console.error(`[captcha] found visible captcha element via selector=${sel}`);
            foundVisible = true;
            if (sel === ".challenge-container") selectedChallenge = fl.locator(sel);
            break;
          } catch {}
        }
        if (foundVisible) break;
      }

      if (!foundVisible) {
        const token = await page.evaluate(() => {
          try {
            const w = window as any;
            const hcaptcha = w.hcaptcha || w._hcaptcha;
            if (!hcaptcha) return null;
            try {
              const resp = hcaptcha.getResponse();
              if (resp) return resp;
            } catch {}
            try {
              const widgets = hcaptcha.getWidgets() || [];
              if (widgets && widgets.length) {
                const out: string[] = [];
                for (const id of widgets) {
                  try {
                    const r = hcaptcha.getResponse(id);
                    if (r) out.push(r);
                  } catch {}
                }
                if (out.length) return out[0];
              }
            } catch {}
          } catch {}
          try {
            const ex = document.querySelector('textarea[name="h-captcha-response"]') as HTMLTextAreaElement | null;
            if (ex && ex.value && ex.value.trim().length > 16) return ex.value;
          } catch {}
          return null;
        });
        if (token) {
          console.error(`[captcha] window.hcaptcha.getResponse() already produced a token (len=${token.length}). Skipping solveChallenge body; ensureCaptchaToken will rely on intercepted /api/generate/v2/ route.`);
          await page.evaluate(async (t) => {
            const w = window as any;
            try {
              const btn = document.querySelector('button[aria-label="Create song"]') || document.querySelector('button[type="submit"]');
              if (btn) (btn as HTMLElement).click();
            } catch {}
          }, token);
          await page.waitForTimeout(3000);
          return;
        }

        // Try a fallback: if hcaptcha widget anchor is present, just click it once.
        try {
          await page.evaluate(() => {
            const w = window as any;
            const h = w.hcaptcha || w._hcaptcha;
            if (h && typeof h.execute === "function") {
              try {
                const widgets = h.getWidgets() || [];
                for (const wg of widgets) {
                  try { h.execute(wg, { async: true }); } catch {}
                }
              } catch {}
            }
          });
          await page.waitForTimeout(4000);
        } catch {}

        if (attempt === 4) {
          console.error(`[captcha] all attempts could not find .challenge-container — giving up (will rely on 120s timeout wrapper).`);
        } else {
          console.error(`[captcha] waiting longer for container; trying another round.`);
          await page.waitForTimeout(4000);
          continue;
        }
      }

      // Normal coordinate-solve path:
      const challengeTarget: any = selectedChallenge || byName.locator(".challenge-container");
      await challengeTarget.waitFor({ state: "visible", timeout: 10_000 });
      console.error(`[captcha] challenge visible (attempt ${attempt})`);
      const shot = await challengeTarget.screenshot({ timeout: 10_000 });
      const result = await solver.coordinates({
        body: shot.toString("base64"),
        lang: "en",
      });
      console.error(`[captcha] solver returned result=${JSON.stringify(result)}`);
      const dataRaw = (result as any).data as unknown;
      let points: Array<{ x: string | number; y: string | number }> = [];
      if (typeof dataRaw === "string") {
        points = JSON.parse(dataRaw) as Array<{ x: string | number; y: string | number }>;
      } else if (Array.isArray(dataRaw)) {
        points = dataRaw as Array<{ x: string | number; y: string | number }>;
      } else if (Array.isArray(result)) {
        points = result as unknown as Array<{ x: string | number; y: string | number }>;
      } else if ((result as any).coordinates && Array.isArray((result as any).coordinates)) {
        points = (result as any).coordinates as Array<{ x: string | number; y: string | number }>;
      }
      console.error(`[captcha] got ${points.length} points`);
      for (const p of points) {
        await challengeTarget.click({ position: { x: Number(p.x), y: Number(p.y) } });
      }
      try {
        await byName.locator(".button-submit").click({ timeout: 3000 });
      } catch {
        try {
          await bySrc.locator(".button-submit").click({ timeout: 3000 });
        } catch {}
      }
      await page.waitForTimeout(3_000);
    } catch (e) {
      console.error(
        `[captcha] attempt ${attempt} error:`,
        e instanceof Error ? e.message : e,
      );
    }
  }
}
