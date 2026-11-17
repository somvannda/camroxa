/**
 * Studio error taxonomy (reference §N-13).
 *
 * Provider and platform failures arrive as free-form messages. The editor groups them
 * into the states the reference names — credits, policy/moderation, edit conflicts,
 * timeouts — and keeps the provider's own text for anything else. Pure so the copy can
 * be tested without a network.
 */

export type StudioErrorKind = "credits" | "policy" | "conflict" | "timeout" | "failed";

export type StudioErrorCopy = {
  kind: StudioErrorKind;
  text: string;
};

const CREDITS = /insufficient|not enough credits?|credit balance|out of credits|402|payment required/i;
const POLICY = /copyright|copyrighted|moderat|policy|not allowed|blocked|sensitive|violat/i;
const CONFLICT =
  /cannot be combined|one arrangement at a time|conflict|already in progress|operation in progress/i;
const TIMEOUT = /timed out|timeout|took too long/i;

export function classifyStudioError(message: unknown, fallback = "That edit did not run."): StudioErrorCopy {  const raw = message instanceof Error ? message.message : String(message ?? "");
  const text = raw.trim() || fallback;

  if (CREDITS.test(text)) {
    return { kind: "credits", text: "Not enough credits. Buy more credits or view plans." };
  }
  if (POLICY.test(text)) {
    const lyrics = /lyric|copyrighted material/i.test(text);
    return {
      kind: "policy",
      text: lyrics
        ? "Couldn't generate that. Your lyrics contain copyrighted material. Please change it and try again."
        : "That prompt was refused. Change it and try again.",
    };
  }
  if (CONFLICT.test(text)) {
    return {
      kind: "conflict",
      text: "That edit conflicts with another operation. Wait for it to finish, then try again.",
    };
  }
  if (TIMEOUT.test(text)) {
    return {
      kind: "timeout",
      text: "The provider took too long. Try again with a shorter range.",
    };
  }
  return { kind: "failed", text };
}

/**
 * True when a generate was refused for money rather than for throttling.
 *
 * `POST /web-music/generate` answers 402 for an empty wallet, but the pooled
 * provider path surfaces the same billing stop as a 429 ("Insufficient credits.")
 * — see `platform_api/services/key_pool_service.py`. A 429 without a credit marker
 * is rate limiting and must not open the top-up modal (S61).
 */
export function isCreditsRefusal(error: unknown): boolean {
  if (!error) return false;
  const message = error instanceof Error ? error.message : String(error);
  const carrier = error as { status?: unknown; code?: unknown };
  const status = Number(carrier?.status ?? 0);
  const code = String(carrier?.code ?? "");
  if (status === 402) return true;
  if (/credit|billing|balance/i.test(code)) return true;
  return CREDITS.test(message);
}
