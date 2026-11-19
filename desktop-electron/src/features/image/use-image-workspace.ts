import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../lib/api";
import { deriveBatchesFromJobs } from "./image-model";
import type {
  ChannelProfile,
  ImageJobListItem,
  ImageSettings,
  ImageWorkspaceData,
  MusicHistoryResponse,
} from "./image-types";

/**
 * Six parallel calls, mirroring the Image page bootstrap.
 *
 * `/image-jobs` is required: without the queue the page has nothing to show.
 * Everything else degrades: batch metadata falls back to job dates, settings
 * fall back to an empty object so the prompt editor still opens, and the
 * account/progress calls are context parity only (never rendered).
 */
export async function fetchImageWorkspace(): Promise<ImageWorkspaceData> {
  const [jobs, history, settings, profiles] = await Promise.allSettled([
    apiRequest<{ items?: ImageJobListItem[] }>({
      method: "GET",
      path: "/image-jobs",
      query: { limit: 200 },
    }),
    apiRequest<MusicHistoryResponse>({
      method: "GET",
      path: "/music/history",
      query: { limit: 25 },
    }),
    apiRequest<ImageSettings>({ method: "GET", path: "/settings" }),
    apiRequest<ChannelProfile[]>({ method: "GET", path: "/profiles" }),
    // Context parity with the desktop bootstrap; the result is not rendered.
    apiRequest<unknown>({
      method: "GET",
      path: "/progress",
      query: { limit: 25, active_only: false },
    }).catch(() => null),
    apiRequest<unknown>({ method: "GET", path: "/users/me" }).catch(() => null),
  ]);

  if (jobs.status === "rejected") throw jobs.reason;
  const imageJobs = Array.isArray(jobs.value?.items) ? jobs.value.items : [];

  const batchesUnavailable = history.status === "rejected";
  const batches =
    history.status === "fulfilled"
      ? (Array.isArray(history.value?.batches) ? history.value.batches ?? [] : [])
      : deriveBatchesFromJobs(imageJobs);

  const settingsUnavailable = settings.status === "rejected";
  const imageSettings =
    settings.status === "fulfilled" && settings.value && typeof settings.value === "object"
      ? settings.value
      : {};

  const channelProfiles =
    profiles.status === "fulfilled" && Array.isArray(profiles.value) ? profiles.value : [];

  return {
    imageJobs,
    batches,
    profiles: channelProfiles,
    settings: imageSettings,
    batchesUnavailable,
    settingsUnavailable,
  };
}

function documentVisible(): boolean {
  return typeof document === "undefined" ? true : !document.hidden;
}

export function useImageWorkspace(active: boolean) {
  return useQuery<ImageWorkspaceData>({
    queryKey: ["image-workspace"],
    queryFn: fetchImageWorkspace,
    retry: 0,
    staleTime: 0,
    refetchOnWindowFocus: false,
    // 4 s while the page is open and the window is visible; stopped otherwise.
    refetchInterval: active && documentVisible() ? 4_000 : false,
  });
}
