import { randomBytes } from "node:crypto";

/**
 * One side of the invite program reward. `percent` pays a share of the credits
 * in the invitee's first credit-pack purchase; `fixed` pays a flat amount.
 */
export interface InviteRewardRule {
  mode: "percent" | "fixed";
  value: number;
}

/**
 * Operator-managed invite-a-friend program (stored under the `invites` key of
 * `app_settings`). Rewards are only released after the invited user buys their
 * first credit pack, so signups alone can never mint credits.
 */
export interface InviteSettings {
  enabled: boolean;
  inviter: InviteRewardRule;
  invitee: InviteRewardRule;
}

export const DEFAULT_INVITES: InviteSettings = {
  enabled: true,
  inviter: { mode: "percent", value: 15 },
  invitee: { mode: "percent", value: 15 },
};

function clampNumber(value: unknown, fallback: number, min: number, max: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return Math.min(max, Math.max(min, value));
}

/** Normalize a stored/upstream `invites` document with the same defensiveness. */
function coerceInviteRule(value: unknown, fallback: InviteRewardRule): InviteRewardRule {
  const o = (value ?? {}) as Record<string, unknown>;
  return {
    mode: o.mode === "fixed" ? "fixed" : o.mode === "percent" ? "percent" : fallback.mode,
    value: clampNumber(o.value, fallback.value, 0, o.mode === "percent" ? 100 : 1_000_000),
  };
}

export function coerceInvites(value: unknown): InviteSettings {
  const o = (value ?? {}) as Record<string, unknown>;
  return {
    enabled: typeof o.enabled === "boolean" ? o.enabled : DEFAULT_INVITES.enabled,
    inviter: coerceInviteRule(o.inviter, DEFAULT_INVITES.inviter),
    invitee: coerceInviteRule(o.invitee, DEFAULT_INVITES.invitee),
  };
}

/** Merge an admin-supplied `invites` patch onto the current values, validating types. */
export function mergeInvites(
  current: InviteSettings,
  patch: unknown,
): { ok: true; value: InviteSettings } | { ok: false; error: string } {
  if (typeof patch !== "object" || patch === null) return { ok: false, error: "invites must be an object." };
  const o = patch as Record<string, unknown>;
  const next: InviteSettings = {
    ...current,
    inviter: { ...current.inviter },
    invitee: { ...current.invitee },
  };
  if (o.enabled !== undefined) {
    if (typeof o.enabled !== "boolean") return { ok: false, error: "invites.enabled must be a boolean." };
    next.enabled = o.enabled;
  }
  for (const side of ["inviter", "invitee"] as const) {
    const patchSide = o[side];
    if (patchSide === undefined) continue;
    if (typeof patchSide !== "object" || patchSide === null) {
      return { ok: false, error: `invites.${side} must be an object.` };
    }
    const r = patchSide as Record<string, unknown>;
    if (r.mode !== undefined) {
      if (r.mode !== "percent" && r.mode !== "fixed") {
        return { ok: false, error: `invites.${side}.mode must be "percent" or "fixed".` };
      }
      next[side].mode = r.mode;
    }
    if (r.value !== undefined) {
      if (typeof r.value !== "number" || !Number.isFinite(r.value) || r.value < 0) {
        return { ok: false, error: `invites.${side}.value must be a non-negative number.` };
      }
      const max = next[side].mode === "percent" ? 100 : 1_000_000;
      if (r.value > max) {
        return {
          ok: false,
          error:
            next[side].mode === "percent"
              ? `invites.${side}.value must be at most 100 percent.`
              : `invites.${side}.value must be at most ${max} credits.`,
        };
      }
      next[side].value = r.value;
    }
    // Percentages must stay within 0–100 even if the mode changed in this patch.
    if (next[side].mode === "percent" && next[side].value > 100) {
      return { ok: false, error: `invites.${side}.value must be at most 100 percent.` };
    }
  }
  return { ok: true, value: next };
}

/**
 * Credits owed for one side of an invite reward. Percent rules round down so the
 * platform never pays more than the configured share; a non-zero share still
 * pays at least one credit on a non-zero purchase.
 */
export function inviteRewardCredits(rule: InviteRewardRule, purchasedCredits: number): number {
  if (rule.value <= 0 || purchasedCredits <= 0) return 0;
  if (rule.mode === "fixed") return Math.max(0, Math.round(rule.value));
  const percent = Math.min(100, rule.value);
  return Math.max(1, Math.floor((purchasedCredits * percent) / 100));
}

/**
 * Unambiguous base-32 alphabet (no 0/O/1/I) so codes survive being read aloud
 * or retyped from a screenshot.
 */
const INVITE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

export function generateInviteCode(length = 8): string {
  const bytes = randomBytes(length);
  let code = "";
  for (let i = 0; i < length; i++) code += INVITE_CODE_ALPHABET[bytes[i] % INVITE_CODE_ALPHABET.length];
  return code;
}

/** Normalize a user-supplied invite code; null when it cannot be valid. */
export function normalizeInviteCode(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const code = value.trim().toUpperCase().replace(/[^A-Z0-9]/g, "");
  return code.length >= 4 && code.length <= 32 ? code : null;
}

/** `jane@example.com` → `j***@example.com` for user-facing referral lists. */
export function maskEmail(email: string): string {
  const at = email.indexOf("@");
  if (at <= 0) return "***";
  const local = email.slice(0, at);
  return `${local[0]}${"*".repeat(Math.max(1, local.length - 1))}${email.slice(at)}`;
}
