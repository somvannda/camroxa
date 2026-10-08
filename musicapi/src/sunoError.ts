/**
 * Structured classification of upstream (Suno) HTTP failures.
 *
 * The cross-account retry loop must decide whether a failed submit is worth
 * retrying on a *different* pooled account. Classifying purely on the
 * human-readable error message is brittle: a wording change in Suno's body can
 * silently turn a retryable failure (402 "not enough credits", 429 "too many
 * requests") back into a terminal one — which is exactly the class of bug that
 * had to be patched in issue #369. So where the failure comes from an HTTP
 * response we carry the status code and Suno's `error_type` on a typed error and
 * classify on those; the legacy message regex stays as a fallback for plain
 * `Error`s thrown by other code paths.
 */

/** An upstream HTTP failure carrying the fields the retry loop classifies on. */
export class SunoHttpError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly errorType?: string,
  ) {
    super(message);
    this.name = "SunoHttpError";
  }
}

/**
 * Build a {@link SunoHttpError} from a non-ok `Response`, reading the body once
 * and parsing Suno's JSON `error_type` when present. The rendered message keeps
 * the historical `"<label> failed (<status>): <body>"` shape so `jobs.error`,
 * logs and the admin "top causes" stay unchanged.
 */
export async function sunoHttpError(label: string, res: Response): Promise<SunoHttpError> {
  const body = await res.text().catch(() => "");
  let errorType: string | undefined;
  try {
    const parsed = JSON.parse(body) as { error_type?: unknown };
    if (parsed && typeof parsed.error_type === "string") errorType = parsed.error_type;
  } catch {
    /* non-JSON body (HTML error page, empty) — fall back to the status code */
  }
  return new SunoHttpError(`${label} failed (${res.status}): ${body}`, res.status, errorType);
}

/**
 * Fallback classifier for errors that carry no structured fields. Kept in sync
 * with the historical `RETRYABLE_ERROR` (issue #367).
 */
const RETRYABLE_MESSAGE =
  /captcha|timeout|timed out|rate[_ ]limits?|too many requests|not enough credits|insufficient credits|\((?:402|429)\)|5\d{2}|no healthy/i;

/**
 * Whether a failed submit should be retried on a different pooled account.
 *
 * Prefers the structured `status`/`errorType` on a {@link SunoHttpError}; falls
 * back to the message regex otherwise (so behaviour is unchanged for plain
 * `Error`s and for statuses we intentionally leave to the text, e.g. captcha).
 */
export function isRetryableSunoError(err: unknown): boolean {
  if (err instanceof SunoHttpError) {
    if (err.errorType && /rate[_ ]limit|too[_ ]many[_ ]requests/i.test(err.errorType)) return true;
    if (err.status === 402 || err.status === 429) return true;
    if (err.status >= 500 && err.status < 600) return true;
    // Other statuses (400/422/…) fall through to the message check below.
  }
  const msg = err instanceof Error ? err.message : String(err);
  return RETRYABLE_MESSAGE.test(msg);
}

/**
 * Whether a failed submit was rejected because the account is out of credits
 * (Suno 402). Distinct from "retryable on another account": callers use this to
 * also mark the account drained so it stops being selected until its credit
 * reading refreshes.
 */
export function isInsufficientCreditsError(err: unknown): boolean {
  if (err instanceof SunoHttpError) {
    if (err.status === 402) return true;
    if (err.errorType && /not[_ ]enough[_ ]credits|insufficient[_ ]credits/i.test(err.errorType)) {
      return true;
    }
  }
  const msg = err instanceof Error ? err.message : String(err);
  return /not enough credits|insufficient credits|\(402\)/i.test(msg);
}

/**
 * Whether a failed submit was rate-limited by Suno (429). Callers use this to
 * put the account on a short cooldown so retries and other jobs don't re-hit the
 * throttled account immediately.
 */
export function isRateLimitedSunoError(err: unknown): boolean {
  if (err instanceof SunoHttpError) {
    if (err.status === 429) return true;
    if (err.errorType && /rate[_ ]limit|too[_ ]many[_ ]requests/i.test(err.errorType)) {
      return true;
    }
  }
  const msg = err instanceof Error ? err.message : String(err);
  return /too many requests|rate[_ ]limits?|\(429\)/i.test(msg);
}
