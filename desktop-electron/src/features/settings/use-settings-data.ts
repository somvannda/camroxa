import { useQuery } from "@tanstack/react-query";
import type { DevicePreferences } from "../../../electron/shared/types";
import type { ChannelProfile, UserMe } from "../dashboard/account-types";
import {
  fetchMe,
  fetchPlaylists,
  fetchProfiles,
  fetchSettings,
  fetchYoutubeConnections,
  type SettingsMap,
  type YouTubeConnection,
  type YouTubePlaylist,
} from "./settings-api";

export const settingsKeys = {
  profiles: ["settings", "profiles"] as const,
  me: ["settings", "me"] as const,
  values: ["settings", "values"] as const,
  youtube: ["settings", "youtube-connections"] as const,
  device: ["settings", "device"] as const,
  playlists: (profileId: string | null) => ["settings", "playlists", profileId] as const,
};

/**
 * Settings loads once and is invalidated explicitly after a save, so a
 * background refetch can never overwrite a draft while the operator is typing.
 */
const baseOptions = {
  staleTime: Infinity,
  retry: 0,
  refetchInterval: false as const,
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
};

export function useProfilesQuery() {
  return useQuery<ChannelProfile[]>({
    queryKey: settingsKeys.profiles,
    queryFn: fetchProfiles,
    ...baseOptions,
  });
}

export function useMeQuery() {
  return useQuery<UserMe>({
    queryKey: settingsKeys.me,
    queryFn: fetchMe,
    ...baseOptions,
  });
}

export function useSettingsQuery() {
  return useQuery<SettingsMap>({
    queryKey: settingsKeys.values,
    queryFn: fetchSettings,
    ...baseOptions,
  });
}

export function useYoutubeConnectionsQuery() {
  return useQuery<YouTubeConnection[]>({
    queryKey: settingsKeys.youtube,
    queryFn: fetchYoutubeConnections,
    ...baseOptions,
  });
}

export function usePlaylistsQuery(profileId: string | null, enabled: boolean) {
  return useQuery<YouTubePlaylist[]>({
    queryKey: settingsKeys.playlists(profileId),
    queryFn: () => fetchPlaylists(profileId as string),
    enabled: Boolean(profileId) && enabled,
    ...baseOptions,
  });
}

const emptyDevicePreferences: DevicePreferences = { ffmpegPath: "", sunoOutputDir: "" };

async function fetchDevicePreferences(): Promise<DevicePreferences> {
  if (!window.camxora?.preferences) return emptyDevicePreferences;
  try {
    const result = await window.camxora.preferences.getDevice();
    return result.ok ? result.data : emptyDevicePreferences;
  } catch {
    return emptyDevicePreferences;
  }
}

export function useDevicePreferencesQuery() {
  return useQuery<DevicePreferences>({
    queryKey: settingsKeys.device,
    queryFn: fetchDevicePreferences,
    ...baseOptions,
  });
}
