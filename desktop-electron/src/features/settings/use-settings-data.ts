import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { DevicePreferences, VideoTemplateInfo } from "../../../electron/shared/types";
import { useSessionStore } from "../../store/session";
import type { ChannelProfile, UserMe } from "../dashboard/account-types";
import {
  fetchContentPoolItems,
  fetchContentPoolStats,
  fetchMe,
  fetchMyPrompts,
  fetchPlaylists,
  fetchProfiles,
  fetchPromptWorkspace,
  fetchSettings,
  fetchYoutubeConnections,
  type SettingsMap,
  type YouTubeConnection,
  type YouTubePlaylist,
} from "./settings-api";
import type { PoolItem, PoolKind, PoolStats, PromptKind, PromptOption, UserPromptEntry } from "./settings-types";

/**
 * Account scope for every settings query.
 *
 * Settings are cached with `staleTime: Infinity`, so the cache key must carry
 * the signed-in account. Without it a second account would paint the previous
 * account's profiles, prompts and defaults until a manual refetch.
 */
export function useSettingsAccountId(): string | null {
  return useSessionStore((state) => state.session?.userId ?? null);
}

export function settingsKeys(accountId: string | null) {
  const scope = accountId ?? "anonymous";
  return {
    profiles: ["settings", scope, "profiles"] as const,
    me: ["settings", scope, "me"] as const,
    values: ["settings", scope, "values"] as const,
    youtube: ["settings", scope, "youtube-connections"] as const,
    playlists: (profileId: string | null) => ["settings", scope, "playlists", profileId] as const,
    promptWorkspace: (kind: PromptKind) => ["settings", scope, "prompt-workspace", kind] as const,
    myPrompts: (kind: PromptKind) => ["settings", scope, "my-prompts", kind] as const,
    poolStats: ["settings", scope, "pool-stats"] as const,
    poolItems: (kind: PoolKind, offset: number) => ["settings", scope, "pool-items", kind, offset] as const,
    // Device paths and local Vizzy templates belong to this computer, not the account.
    device: ["settings", "device"] as const,
    videoTemplates: ["settings", "video-templates"] as const,
  };
}

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
  const accountId = useSettingsAccountId();
  return useQuery<ChannelProfile[]>({
    queryKey: settingsKeys(accountId).profiles,
    queryFn: fetchProfiles,
    ...baseOptions,
  });
}

export function useMeQuery() {
  const accountId = useSettingsAccountId();
  return useQuery<UserMe>({
    queryKey: settingsKeys(accountId).me,
    queryFn: fetchMe,
    ...baseOptions,
  });
}

export function useSettingsQuery() {
  const accountId = useSettingsAccountId();
  return useQuery<SettingsMap>({
    queryKey: settingsKeys(accountId).values,
    queryFn: fetchSettings,
    ...baseOptions,
  });
}

export function useYoutubeConnectionsQuery() {
  const accountId = useSettingsAccountId();
  return useQuery<YouTubeConnection[]>({
    queryKey: settingsKeys(accountId).youtube,
    queryFn: fetchYoutubeConnections,
    ...baseOptions,
  });
}

export function usePlaylistsQuery(profileId: string | null, enabled: boolean) {
  const accountId = useSettingsAccountId();
  return useQuery<YouTubePlaylist[]>({
    queryKey: settingsKeys(accountId).playlists(profileId),
    queryFn: () => fetchPlaylists(profileId as string),
    enabled: Boolean(profileId) && enabled,
    ...baseOptions,
  });
}

export function usePromptWorkspaceQuery(kind: PromptKind) {
  const accountId = useSettingsAccountId();
  return useQuery<PromptOption[]>({
    queryKey: settingsKeys(accountId).promptWorkspace(kind),
    queryFn: () => fetchPromptWorkspace(kind),
    ...baseOptions,
  });
}

export function useMyPromptsQuery(kind: PromptKind) {
  const accountId = useSettingsAccountId();
  return useQuery<UserPromptEntry[]>({
    queryKey: settingsKeys(accountId).myPrompts(kind),
    queryFn: () => fetchMyPrompts(kind),
    ...baseOptions,
  });
}

export function usePoolStatsQuery() {
  const accountId = useSettingsAccountId();
  return useQuery<PoolStats>({
    queryKey: settingsKeys(accountId).poolStats,
    queryFn: fetchContentPoolStats,
    ...baseOptions,
  });
}

export interface ContentPoolPage {
  items: PoolItem[];
  total: number;
  limit: number;
  offset: number;
}

export function usePoolItemsQuery(kind: PoolKind, offset: number) {
  const accountId = useSettingsAccountId();
  return useQuery<ContentPoolPage>({
    queryKey: settingsKeys(accountId).poolItems(kind, offset),
    queryFn: () => fetchContentPoolItems(kind, 50, offset),
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
    queryKey: settingsKeys(null).device,
    queryFn: fetchDevicePreferences,
    ...baseOptions,
  });
}

async function fetchVideoTemplates(): Promise<VideoTemplateInfo[]> {
  if (!window.camxora?.videoTemplates) return [];
  try {
    const result = await window.camxora.videoTemplates.list();
    return result.ok ? result.data : [];
  } catch {
    return [];
  }
}

export function useVideoTemplatesQuery() {
  const queryClient = useQueryClient();
  useEffect(() => {
    const subscribe = window.camxora?.videoTemplates?.onChange;
    if (!subscribe) return;
    return subscribe(() => {
      void queryClient.invalidateQueries({ queryKey: settingsKeys(null).videoTemplates });
    });
  }, [queryClient]);

  return useQuery<VideoTemplateInfo[]>({
    queryKey: settingsKeys(null).videoTemplates,
    queryFn: fetchVideoTemplates,
    staleTime: 30_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });
}
