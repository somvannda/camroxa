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
 * in `challenges.cloudflare.com/cdn-cgi/challenge-platform/...` asset URLs,
 * so it is pinned in config and passed to 2Captcha's Turnstile endpoint (which
 * returns a token directly - no screenshotting or clicking required).
 */
export interface CaptchaAccount {
  twoCaptchaKey?: string;
}

/**
 * Raised when 2Captcha cannot accept a solve right now
 * (`ERROR_NO_SLOT_AVAILABLE`: our account's solve queue is full).
 *
 * This is transient infrastructure pressure, not a bad generation request, so
 * callers must back off and retry later instead of settling the song as failed
 * (which refunds the charge and forces the client to resubmit from scratch).
 */
export class CaptchaUnavailableError extends Error {
  constructor(
    message: string,
    readonly cause?: unknown,
  ) {
    super(message);
    this.name = "CaptchaUnavailableError";
  }
}

/** True for a {@link CaptchaUnavailableError} that crossed a module boundary. */
export function isCaptchaUnavailableError(err: unknown): boolean {
  return err instanceof Error && err.name === "CaptchaUnavailableError";
}

/**
 * Whether a 2Captcha failure means "no free slot, try again later".
 *
 * The client library throws `APIError` with the raw code on `err` and a numeric
 * `code`; plain errors are matched on the message so the check still works if
 * the library changes shape.
 */
export function isNoSlotAvailableError(err: unknown): boolean {
  const candidate = err as { err?: unknown; code?: unknown; message?: unknown } | null;
  if (candidate?.err === "ERROR_NO_SLOT_AVAILABLE" || candidate?.code === 11) return true;
  const message = String(candidate?.message ?? (err instanceof Error ? err.message : err) ?? "");
  return /ERROR_NO_SLOT_AVAILABLE|maximum capacity|no slot available/i.test(message);
}

/**
 * Bounded gate around 2Captcha calls.
 *
 * Every generation needs its own Turnstile token, so a batch retry fans out
 * many solves at once. 2Captcha rejects the overflow with
 * `ERROR_NO_SLOT_AVAILABLE`, which used to fail the whole song. Holding at most
 * `config.captcha.maxConcurrent` solves keeps the burst inside the account's
 * queue instead of losing the requests.
 */
export class SolveSemaphore {
  private active = 0;
  private readonly waiters: Array<() => void> = [];

  constructor(private readonly max: number) {
    if (!Number.isFinite(max) || max < 1) throw new Error("SolveSemaphore max must be >= 1");
  }

  async acquire(): Promise<void> {
    if (this.active < this.max) {
      this.active += 1;
      return;
    }
    await new Promise<void>((resolve) => this.waiters.push(resolve));
  }

  release(): void {
    const next = this.waiters.shift();
    if (next) {
      // Hand the slot straight to the next waiter; `active` is unchanged.
      next();
      return;
    }
    this.active -= 1;
  }

  async run<T>(fn: () => Promise<T>): Promise<T> {
    await this.acquire();
    try {
      return await fn();
    } finally {
      this.release();
    }
  }

  get stats(): { active: number; waiting: number; max: number } {
    return { active: this.active, waiting: this.waiters.length, max: this.max };
  }
}

const solveGate = new SolveSemaphore(config.captcha.maxConcurrent);

/** Snapshot of the 2Captcha solve gate, for health/log diagnostics. */
export function captchaGateStats(): { active: number; waiting: number; max: number } {
  return solveGate.stats;
}

/** Minimal shape of the 2Captcha client used here (kept narrow for tests). */
export interface TurnstileSolver {
  cloudflareTurnstile(options: { sitekey: string; pageurl: string }): Promise<{ data?: unknown }>;
}

export interface SolveDeps {
  /** Inject a solver in tests; production builds one from the API key. */
  solver?: TurnstileSolver;
  /** Pause between a no-slot rejection and the single retry. */
  sleep?: (ms: number) => Promise<void>;
  /** Override the configured pause (tests pass 0). */
  noSlotRetryDelayMs?: number;
}

const defaultSleep = (ms: number): Promise<void> =>
  ms > 0 ? new Promise((resolve) => setTimeout(resolve, ms)) : Promise.resolve();

/** One gated solve; validates that 2Captcha actually returned a token. */
async function solveOnce(solver: TurnstileSolver): Promise<string> {
  const res = await solveGate.run(() =>
    solver.cloudflareTurnstile({
      sitekey: config.turnstileSitekey,
      pageurl: config.turnstilePageUrl,
    }),
  );
  const token = res?.data;
  if (!token || typeof token !== "string") {
    throw new Error(`2Captcha turnstile solve returned no token: ${JSON.stringify(res).slice(0, 200)}`);
  }
  return token;
}

/**
 * Solve the generation gate's Cloudflare Turnstile via 2Captcha and return the
 * token to send as `token` on `POST /api/generate/v2/`.
 *
 * Concurrency is capped by {@link solveGate}. A no-slot rejection is retried
 * once after a short pause; if the queue is still full the error surfaces as
 * {@link CaptchaUnavailableError} so the caller can defer instead of failing.
 */
export async function solveCaptchaForAccount(
  account: CaptchaAccount = {},
  deps: SolveDeps = {},
): Promise<string> {
  const twoCaptchaKey = account.twoCaptchaKey ?? config.twoCaptchaKey;
  if (!twoCaptchaKey) {
    throw new Error("TWOCAPTCHA_KEY is required to solve captcha.");
  }
  const solver = deps.solver ?? new Solver(twoCaptchaKey);
  const sleep = deps.sleep ?? defaultSleep;
  const retryDelayMs = deps.noSlotRetryDelayMs ?? config.captcha.noSlotRetryDelayMs;

  console.error(`[captcha] solving turnstile for sitekey ${config.turnstileSitekey}`);
  const t0 = Date.now();
  try {
    const token = await solveOnce(solver);
    console.error(
      `[captcha] turnstile solved in ${((Date.now() - t0) / 1000).toFixed(1)}s (token len=${token.length})`,
    );
    return token;
  } catch (e) {
    if (!isNoSlotAvailableError(e)) throw e;
    if (retryDelayMs <= 0) {
      throw new CaptchaUnavailableError(
        "captcha unavailable: 2Captcha has no free solve slot (ERROR_NO_SLOT_AVAILABLE)",
        e,
      );
    }
    console.warn(
      `[captcha] 2Captcha has no free slot; retrying in ${retryDelayMs}ms before deferring`,
    );
    await sleep(retryDelayMs);
    try {
      const token = await solveOnce(solver);
      console.error(
        `[captcha] turnstile solved after no-slot retry in ${((Date.now() - t0) / 1000).toFixed(1)}s (token len=${token.length})`,
      );
      return token;
    } catch (retryError) {
      if (isNoSlotAvailableError(retryError)) {
        throw new CaptchaUnavailableError(
          "captcha unavailable: 2Captcha queue is full (ERROR_NO_SLOT_AVAILABLE); retry later",
          retryError,
        );
      }
      throw retryError;
    }
  }
}

/** CLI/global convenience wrapper: solve using the default configured key. */
export async function solveCaptcha(): Promise<string> {
  return solveCaptchaForAccount({ twoCaptchaKey: config.twoCaptchaKey });
}
