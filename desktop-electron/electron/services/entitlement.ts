import type { BootstrapDestination, UserMe } from "../shared/types";

/**
 * Mirror of `camxora_python/shared/lib/desktop_entitlement.py`.
 *
 * Packs-only billing: `desktop_access` from the API is authoritative when present.
 * Older API builds without the flag fall back to `onboarding_paid` and the paid
 * catalog plan names (Starter, Creator, Studio). Admins always pass.
 */
export const DESKTOP_PLAN_REQUIRED_CODE = "DESKTOP_PLAN_REQUIRED";

export const DESKTOP_PLAN_REQUIRED_MESSAGE =
  "Your account has no active Desktop Studio credits. " +
  "Buy a credit pack on music.camxora.com, then sign in again. " +
  "Pack credits are valid for 30 days.";

const PAID_CATALOG_TIERS = ["starter", "creator", "studio"];

export type EntitlementUser = Pick<
  UserMe,
  "role" | "desktop_access" | "onboarding_paid" | "plan_name"
>;

export function isPaidCatalogPlanName(name: string | null | undefined): boolean {
  const normalized = String(name ?? "")
    .replace(/[_-]+/g, " ")
    .trim()
    .toLowerCase();
  if (!normalized || normalized === "free" || normalized.startsWith("free ")) return false;
  return PAID_CATALOG_TIERS.some((tier) => normalized.includes(tier));
}

export function userCanUseDesktopStudio(me: EntitlementUser): boolean {
  const role = String(me.role ?? "").trim().toLowerCase();
  if (role === "admin") return true;

  if (me.desktop_access !== undefined && me.desktop_access !== null) {
    return me.desktop_access === true;
  }

  if (me.onboarding_paid === true) return true;
  return isPaidCatalogPlanName(me.plan_name);
}

export type AccountRoute =
  | { destination: "login"; code: typeof DESKTOP_PLAN_REQUIRED_CODE }
  | { destination: Exclude<BootstrapDestination, "login"> };

/**
 * Post-auth routing order: paid gate -> email confirmation -> channel profiles.
 * Users who skip onboarding are routed to the shell by the renderer, not here.
 */
export function resolveBootstrapDestination(
  me: EntitlementUser & Pick<UserMe, "email_confirmed" | "channel_profile_count">,
): AccountRoute {
  if (!userCanUseDesktopStudio(me)) {
    return { destination: "login", code: DESKTOP_PLAN_REQUIRED_CODE };
  }
  if (me.email_confirmed === false) {
    return { destination: "confirm_email" };
  }
  if ((me.channel_profile_count ?? 0) === 0) {
    return { destination: "onboarding" };
  }
  return { destination: "app" };
}
