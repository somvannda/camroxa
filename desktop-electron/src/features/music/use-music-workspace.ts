import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../lib/api";
import type {
  ChannelProfile,
  MusicHistoryResponse,
  MusicUser,
  MusicWorkspaceData,
  OperationCost,
  PromptOption,
  SettingsRecord,
} from "./music-types";

export const MUSIC_LOAD_ERROR_COPY =
  "Unable to load the music workspace from the current backend contracts.";

function asArray<T>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === "object") {
    const items = (value as { items?: unknown }).items;
    if (Array.isArray(items)) return items as T[];
  }
  return [];
}

function asSettings(value: unknown): SettingsRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as SettingsRecord)
    : {};
}

function asHistory(value: unknown): MusicHistoryResponse {
  const record = value && typeof value === "object" ? (value as MusicHistoryResponse) : {};
  return {
    batches: Array.isArray(record.batches) ? record.batches : [],
    summary: typeof record.summary === "string" ? record.summary : "",
    updated_at: typeof record.updated_at === "string" ? record.updated_at : "",
  };
}

/**
 * One parallel bootstrap for the seven Music calls.
 *
 * `/users/me`, `/profiles`, `/settings` and the two public prompt catalogues
 * are required. History and operation costs are optional: a failure there
 * leaves an honest empty value instead of failing the whole page.
 */
export async function fetchMusicWorkspace(): Promise<MusicWorkspaceData> {
  const [me, profiles, settings, descriptions, structures, history, costs] =
    await Promise.all([
      apiRequest<MusicUser>({ method: "GET", path: "/users/me" }),
      apiRequest<unknown>({ method: "GET", path: "/profiles" }),
      apiRequest<unknown>({ method: "GET", path: "/settings" }),
      apiRequest<unknown>({ method: "GET", path: "/prompts/descriptions/public" }),
      apiRequest<unknown>({ method: "GET", path: "/prompts/structures/public" }),
      apiRequest<unknown>({
        method: "GET",
        path: "/music/history",
        query: { limit: 8 },
      }).catch(() => ({ batches: [], summary: "", updated_at: "" })),
      apiRequest<unknown>({ method: "GET", path: "/credits/operation-costs" }).catch(
        () => [] as OperationCost[],
      ),
    ]);

  return {
    me: me && typeof me === "object" ? me : null,
    profiles: asArray<ChannelProfile>(profiles),
    settings: asSettings(settings),
    descriptions: asArray<PromptOption>(descriptions),
    structures: asArray<PromptOption>(structures),
    history: asHistory(history),
    costs: asArray<OperationCost>(costs),
  };
}

export function useMusicWorkspace() {
  return useQuery<MusicWorkspaceData>({
    queryKey: ["music-workspace"],
    queryFn: fetchMusicWorkspace,
    retry: 0,
    staleTime: 0,
    refetchInterval: false,
    refetchOnWindowFocus: false,
  });
}

export async function fetchMusicHistory(limit: number): Promise<MusicHistoryResponse> {
  const data = await apiRequest<unknown>({
    method: "GET",
    path: "/music/history",
    query: { limit },
  });
  return asHistory(data);
}
