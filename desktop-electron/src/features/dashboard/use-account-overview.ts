import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../lib/api";
import type {
  AccountOverview,
  ChannelProfile,
  DashboardStats,
  LicenseInfo,
  UserMe,
} from "./account-types";

/**
 * Single aggregated account load shared by Dashboard and Profile.
 *
 * `/users/me` and `/stats/dashboard` are required; a failure there rejects the
 * whole load. `/profiles` and `/licenses/validate` are optional and fall back
 * to `[]` / `null` so the page still renders.
 *
 * All four requests start together. There is no timer and no manual refresh:
 * the query refetches when a page mounts again because `staleTime` is 0.
 */
export async function fetchAccountOverview(): Promise<AccountOverview> {
  const [me, stats, profiles, license] = await Promise.all([
    apiRequest<UserMe>({ method: "GET", path: "/users/me" }),
    apiRequest<DashboardStats>({ method: "GET", path: "/stats/dashboard" }),
    apiRequest<ChannelProfile[]>({ method: "GET", path: "/profiles" }).catch(
      () => [] as ChannelProfile[],
    ),
    apiRequest<LicenseInfo>({ method: "GET", path: "/licenses/validate" }).catch(
      () => null,
    ),
  ]);

  return {
    me,
    stats,
    profiles: Array.isArray(profiles) ? profiles : [],
    license,
  };
}

export function useAccountOverview() {
  return useQuery<AccountOverview>({
    queryKey: ["account-overview"],
    queryFn: fetchAccountOverview,
    retry: 0,
    staleTime: 0,
    refetchInterval: false,
    refetchOnWindowFocus: false,
  });
}
