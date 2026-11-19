import type { components } from "../../lib/api-schema";

export type UserMe = components["schemas"]["UserProfileResponse"];
export type DashboardStats = components["schemas"]["DashboardStatsResponse"];
export type DailyUsage = components["schemas"]["DailyUsage"];
export type RecentActivity = components["schemas"]["RecentActivity"];
export type ChannelProfile = components["schemas"]["ProfileResponse"];

/**
 * Shape of GET /licenses/validate as consumed by the desktop client.
 *
 * The endpoint is optional: a missing licence (404) or an older backend that no
 * longer serves the route resolves to `null` and the account pages fall back to
 * the values on `/users/me` and `/stats/dashboard`.
 */
export interface LicenseInfo {
  plan_type?: string | null;
  profile_allowance?: number | null;
  effective_profile_allowance?: number | null;
  monthly_song_quota?: number | null;
  songs_remaining?: number | null;
  monthly_image_quota?: number | null;
  images_remaining?: number | null;
  wallet_balance?: number | null;
  expiration_date?: string | null;
}

export interface AccountOverview {
  me: UserMe;
  stats: DashboardStats;
  profiles: ChannelProfile[];
  license: LicenseInfo | null;
}
