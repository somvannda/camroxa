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

export function classifyStudioError(message: unknown, fallback = "That edit did not run."): StudioErrorCopy {
  const raw = message instanceof Error ? message.message : String(message ?? "");
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
