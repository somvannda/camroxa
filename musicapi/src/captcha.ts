import { config } from "./config.js";
import { apiHeaders, resolveJwt } from "./auth.js";
import { Solver } from "@2captcha/captcha-solver";

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
      signal: AbortSignal.timeout(15_000),
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
 * Suno gates generation behind a Cloudflare Turnstile widget mounted at
 * `#generation-turnstile-container` on suno.com/create. The widget advertises
 * no `data-sitekey` attribute in its DOM, but the sitekey is stable and visible
 * in the `challenges.cloudflare.com/cdn-cgi/challenge-platform/...` asset URLs,
 * so it is pinned in config and passed to 2Captcha's Turnstile endpoint (which
 * returns a token directly — no screenshotting or clicking required).
 */
export interface CaptchaAccount {
  twoCaptchaKey?: string;
}

/**
 * Solve the generation gate's Cloudflare Turnstile via 2Captcha and return the
 * token to send as `token` on `POST /api/generate/v2/`.
 */
export async function solveCaptchaForAccount(account: CaptchaAccount = {}): Promise<string> {
  const twoCaptchaKey = account.twoCaptchaKey ?? config.twoCaptchaKey;
  if (!twoCaptchaKey) {
    throw new Error("TWOCAPTCHA_KEY is required to solve captcha.");
  }
  const solver = new Solver(twoCaptchaKey);

  console.error(`[captcha] solving turnstile for sitekey ${config.turnstileSitekey}`);
  const t0 = Date.now();
  const res = await solver.cloudflareTurnstile({
    sitekey: config.turnstileSitekey,
    pageurl: config.turnstilePageUrl,
  });
  const token = (res as { data?: unknown })?.data;
  if (!token || typeof token !== "string") {
    throw new Error(`2Captcha turnstile solve returned no token: ${JSON.stringify(res).slice(0, 200)}`);
  }
  console.error(
    `[captcha] turnstile solved in ${((Date.now() - t0) / 1000).toFixed(1)}s (token len=${token.length})`,
  );
  return token;
}

/** CLI/global convenience wrapper: solve using the default configured key. */
export async function solveCaptcha(): Promise<string> {
  return solveCaptchaForAccount({ twoCaptchaKey: config.twoCaptchaKey });
}
