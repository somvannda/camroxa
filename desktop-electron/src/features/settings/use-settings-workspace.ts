import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { errorMessage } from "../../lib/api";
import { toast } from "../../components/toast";
import type { ChannelProfile } from "../dashboard/account-types";
import { openExternal } from "../auth/portal";
import {
  createMyPrompt as createMyPromptApi,
  createPlaylist as createPlaylistApi,
  createProfile as createProfileApi,
  deleteMyPrompt as deleteMyPromptApi,
  deleteProfile as deleteProfileApi,
  disconnectYoutube as disconnectYoutubeApi,
  fetchYoutubeConnections,
  patchSettings,
  selectYoutubeChannel as selectYoutubeChannelApi,
  startYoutubeConnection,
  updateMyPrompt as updateMyPromptApi,
  updateProfile as updateProfileApi,
  type SettingsMap,
  type YouTubeConnection,
} from "./settings-api";
import {
  SETTINGS_TABS,
  buildPreferencesDraft,
  buildPreferencesPatch,
  buildProfileDraft,
  buildProfilePayload,
  buildPromptDefaultsDraft,
  buildPromptDefaultsPatch,
  buildPromptEditorDraft,
  buildPublicationDraft,
  buildPublicationPayload,
  buildSunoSettingsDraft,
  buildSunoSettingsPatch,
  buildUserPromptPayload,
  clampPoolOffset,
  countDirtyTabs,
  defaultPreferencesDraft,
  emptyProfileDraft,
  emptyPromptDefaultsDraft,
  emptyPromptEditorDraft,
  emptyPublicationDraft,
  filterProfiles,
  imagePromptLibraryOnly,
  preferencesDraftDirty,
  profileDraftDirty,
  promptDefaultsDirtyFor,
  promptEditorDraftDirty,
  promptKindInfo,
  publicationDraftDirty,
  recordOf,
  removeUserPrompt,
  settingsTabLabel,
  slugifyProfileFolder,
  sunoSettingsDirty,
  upsertUserPrompt,
  validatePreferencesDraft,
  validateProfileDraft,
  validatePromptEditorDraft,
  validatePublicationDraft,
  validateSunoSettingsDraft,
  type FfmpegStatus,
  type PoolKind,
  type PreferencesDraft,
  type ProfileDraft,
  type ProfileField,
  type PromptDefaultsDraft,
  type PromptEditorDraft,
  type PromptEditorField,
  type PromptKind,
  type PublicationDraft,
  type PublicationField,
  type SettingsTab,
  type SunoField,
  type SunoSettingsDraft,
  type UserPromptEntry,
} from "./settings-types";
import {
  settingsKeys,
  useDevicePreferencesQuery,
  useMeQuery,
  useMyPromptsQuery,
  usePlaylistsQuery,
  usePoolItemsQuery,
  usePoolStatsQuery,
  useProfilesQuery,
  usePromptWorkspaceQuery,
  useSettingsAccountId,
  useSettingsQuery,
  useVideoTemplatesQuery,
  useYoutubeConnectionsQuery,
} from "./use-settings-data";

export type PendingConfirm =
  | { kind: "switch-profile"; profile: ChannelProfile }
  | { kind: "new-profile" }
  | { kind: "switch-publication"; profileId: string }
  | { kind: "discard-all" }
  | { kind: "delete-profile"; profile: ChannelProfile }
  | { kind: "disconnect-youtube"; profile: ChannelProfile }
  | { kind: "delete-prompt"; promptKind: PromptKind; entry: UserPromptEntry }
  | { kind: "switch-prompt"; promptKind: PromptKind; entry: UserPromptEntry }
  | { kind: "new-prompt"; promptKind: PromptKind };

export interface SavingState {
  tabs: SettingsTab[];
  current: SettingsTab | null;
}

const PROMPT_DEFAULT_FIELDS: Array<[keyof PromptDefaultsDraft, string]> = [
  ["descriptionId", "defaultDescriptionId"],
  ["structureId", "defaultStructureId"],
  ["moodId", "defaultMoodId"],
];

/** Which account settings key belongs to which catalog tab. */
const PROMPT_DEFAULT_KEYS_BY_KIND: Record<PromptKind, string[]> = {
  descriptions: ["defaultDescriptionId"],
  structures: ["defaultStructureId"],
  moods: ["defaultMoodId"],
};

function resetAllPromptEditors(): Record<PromptKind, PromptEditorDraft> {
  return {
    descriptions: emptyPromptEditorDraft(),
    structures: emptyPromptEditorDraft(),
    moods: emptyPromptEditorDraft(),
  };
}

function upsertProfile(list: ChannelProfile[] | undefined, profile: ChannelProfile): ChannelProfile[] {
  const current = Array.isArray(list) ? list : [];
  const found = current.some((item) => item.id === profile.id);
  return found ? current.map((item) => (item.id === profile.id ? profile : item)) : [...current, profile];
}

export function useSettingsWorkspace() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const accountId = useSettingsAccountId();
  const keys = useMemo(() => settingsKeys(accountId), [accountId]);
  const profilesQuery = useProfilesQuery();
  const meQuery = useMeQuery();
  const settingsQuery = useSettingsQuery();
  const deviceQuery = useDevicePreferencesQuery();
  const connectionsQuery = useYoutubeConnectionsQuery();
  const videoTemplatesQuery = useVideoTemplatesQuery();
  const descriptionWorkspaceQuery = usePromptWorkspaceQuery("descriptions");
  const structureWorkspaceQuery = usePromptWorkspaceQuery("structures");
  const moodWorkspaceQuery = usePromptWorkspaceQuery("moods");
  const descriptionPromptsQuery = useMyPromptsQuery("descriptions");
  const structurePromptsQuery = useMyPromptsQuery("structures");
  const moodPromptsQuery = useMyPromptsQuery("moods");
  const poolStatsQuery = usePoolStatsQuery();
  const [poolKind, setPoolKindState] = useState<PoolKind>("openings");
  const [poolOffset, setPoolOffset] = useState(0);
  const poolItemsQuery = usePoolItemsQuery(poolKind, poolOffset);
  const poolStats = poolStatsQuery.data ?? null;
  const requestedProfileId = searchParams.get("profile");

  const profiles = useMemo(
    () => (Array.isArray(profilesQuery.data) ? profilesQuery.data : []),
    [profilesQuery.data],
  );
  const settings = settingsQuery.data ?? null;
  const connections = useMemo(
    () => (Array.isArray(connectionsQuery.data) ? connectionsQuery.data : []),
    [connectionsQuery.data],
  );

  const [activeTab, setActiveTab] = useState<SettingsTab>("profiles");
  const [profileSearch, setProfileSearchState] = useState("");
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [isNewProfile, setIsNewProfile] = useState(false);
  const [profileDraft, setProfileDraft] = useState<ProfileDraft>(emptyProfileDraft);
  const [profileBaseline, setProfileBaseline] = useState<ProfileDraft>(emptyProfileDraft);
  const [profileErrors, setProfileErrors] = useState<Partial<Record<ProfileField, string>>>({});
  const folderTouchedRef = useRef(false);

  const [publicationProfileId, setPublicationProfileId] = useState<string | null>(null);
  const [publicationDraft, setPublicationDraft] = useState<PublicationDraft>(emptyPublicationDraft);
  const [publicationBaseline, setPublicationBaseline] = useState<PublicationDraft>(emptyPublicationDraft);
  const [publicationErrors, setPublicationErrors] = useState<Partial<Record<PublicationField, string>>>({});

  const [preferencesDraft, setPreferencesDraft] = useState<PreferencesDraft>(defaultPreferencesDraft);
  const [preferencesBaseline, setPreferencesBaseline] = useState<PreferencesDraft>(defaultPreferencesDraft);
  const [preferencesErrors, setPreferencesErrors] = useState<Partial<Record<keyof PreferencesDraft, string>>>({});
  const [preferencesWarnings, setPreferencesWarnings] = useState<string[]>([]);
  const [ffmpegStatus, setFfmpegStatus] = useState<FfmpegStatus>({
    state: "idle",
    message: "Not checked yet.",
  });

  // Prompt catalogs: the workspace defaults live in account settings, while
  // the editor drafts are user-owned prompt writes with their own Save action.
  const [promptDefaults, setPromptDefaults] = useState<PromptDefaultsDraft>(emptyPromptDefaultsDraft);
  const [promptDefaultsBaseline, setPromptDefaultsBaseline] =
    useState<PromptDefaultsDraft>(emptyPromptDefaultsDraft);
  const [promptDrafts, setPromptDrafts] = useState<Record<PromptKind, PromptEditorDraft>>(() => ({
    descriptions: emptyPromptEditorDraft(),
    structures: emptyPromptEditorDraft(),
    moods: emptyPromptEditorDraft(),
  }));
  const [promptBaselines, setPromptBaselines] = useState<Record<PromptKind, PromptEditorDraft>>(() => ({
    descriptions: emptyPromptEditorDraft(),
    structures: emptyPromptEditorDraft(),
    moods: emptyPromptEditorDraft(),
  }));
  const [promptFieldErrors, setPromptFieldErrors] = useState<
    Record<PromptKind, Partial<Record<PromptEditorField, string>>>
  >(() => ({ descriptions: {}, structures: {}, moods: {} }));
  const [promptBusy, setPromptBusy] = useState<PromptKind | null>(null);

  const [sunoDraft, setSunoDraft] = useState<SunoSettingsDraft>(() => buildSunoSettingsDraft(null));
  const [sunoBaseline, setSunoBaseline] = useState<SunoSettingsDraft>(() => buildSunoSettingsDraft(null));
  const [sunoErrors, setSunoErrors] = useState<Partial<Record<SunoField, string>>>({});

  const [tabErrors, setTabErrors] = useState<Partial<Record<SettingsTab, string>>>({});
  const [saving, setSaving] = useState<SavingState | null>(null);
  const [lastSavedAt, setLastSavedAt] = useState<number | null>(null);

  const [youtubeBusy, setYoutubeBusy] = useState<"connect" | "disconnect" | "select" | null>(null);
  const [pollingProfileId, setPollingProfileId] = useState<string | null>(null);
  const [playlistBusy, setPlaylistBusy] = useState(false);

  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm | null>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);

  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.id === selectedProfileId) ?? null,
    [profiles, selectedProfileId],
  );
  const publicationProfile = useMemo(
    () => profiles.find((profile) => profile.id === publicationProfileId) ?? null,
    [profiles, publicationProfileId],
  );
  const youtubeConnection = useCallback(
    (profileId: string | null | undefined): YouTubeConnection | null =>
      profileId ? connections.find((connection) => connection.profile_id === profileId) ?? null : null,
    [connections],
  );
  const publicationConnection = youtubeConnection(publicationProfileId);
  const publicationConnected = publicationConnection?.status === "connected";
  const playlistsQuery = usePlaylistsQuery(publicationProfileId, publicationConnected);
  const playlists = useMemo(
    () => (Array.isArray(playlistsQuery.data) ? playlistsQuery.data : []),
    [playlistsQuery.data],
  );

  const filteredProfiles = useMemo(() => filterProfiles(profiles, profileSearch), [profiles, profileSearch]);

  const promptWorkspace = useMemo(
    () => ({
      descriptions: descriptionWorkspaceQuery.data ?? [],
      structures: structureWorkspaceQuery.data ?? [],
      moods: moodWorkspaceQuery.data ?? [],
    }),
    [descriptionWorkspaceQuery.data, moodWorkspaceQuery.data, structureWorkspaceQuery.data],
  );
  const promptWorkspaceLoading: Record<PromptKind, boolean> = {
    descriptions: descriptionWorkspaceQuery.isLoading,
    structures: structureWorkspaceQuery.isLoading,
    moods: moodWorkspaceQuery.isLoading,
  };
  const promptWorkspaceError: Record<PromptKind, string | null> = {
    descriptions: descriptionWorkspaceQuery.isError ? errorMessage(descriptionWorkspaceQuery.error) : null,
    structures: structureWorkspaceQuery.isError ? errorMessage(structureWorkspaceQuery.error) : null,
    moods: moodWorkspaceQuery.isError ? errorMessage(moodWorkspaceQuery.error) : null,
  };
  const userPrompts = useMemo(
    () => ({
      descriptions: descriptionPromptsQuery.data ?? [],
      structures: structurePromptsQuery.data ?? [],
      moods: moodPromptsQuery.data ?? [],
    }),
    [descriptionPromptsQuery.data, moodPromptsQuery.data, structurePromptsQuery.data],
  );
  const userPromptsLoading: Record<PromptKind, boolean> = {
    descriptions: descriptionPromptsQuery.isLoading,
    structures: structurePromptsQuery.isLoading,
    moods: moodPromptsQuery.isLoading,
  };
  const userPromptsError: Record<PromptKind, string | null> = {
    descriptions: descriptionPromptsQuery.isError ? errorMessage(descriptionPromptsQuery.error) : null,
    structures: structurePromptsQuery.isError ? errorMessage(structurePromptsQuery.error) : null,
    moods: moodPromptsQuery.isError ? errorMessage(moodPromptsQuery.error) : null,
  };

  const profileDirty = profileDraftDirty(profileDraft, profileBaseline);
  const publicationDirty = publicationDraftDirty(publicationDraft, publicationBaseline);
  const preferencesDirty = preferencesDraftDirty(preferencesDraft, preferencesBaseline);
  const promptEditorDirty: Record<PromptKind, boolean> = useMemo(
    () => ({
      descriptions: promptEditorDraftDirty(promptDrafts.descriptions, promptBaselines.descriptions),
      structures: promptEditorDraftDirty(promptDrafts.structures, promptBaselines.structures),
      moods: promptEditorDraftDirty(promptDrafts.moods, promptBaselines.moods),
    }),
    [promptBaselines, promptDrafts],
  );
  const promptDefaultsDirty: Record<PromptKind, boolean> = {
    descriptions: promptDefaultsDirtyFor("descriptions", promptDefaults, promptDefaultsBaseline),
    structures: promptDefaultsDirtyFor("structures", promptDefaults, promptDefaultsBaseline),
    moods: promptDefaultsDirtyFor("moods", promptDefaults, promptDefaultsBaseline),
  };
  const promptTabDirty: Record<PromptKind, boolean> = {
    descriptions: promptEditorDirty.descriptions || promptDefaultsDirty.descriptions,
    structures: promptEditorDirty.structures || promptDefaultsDirty.structures,
    moods: promptEditorDirty.moods || promptDefaultsDirty.moods,
  };
  const sunoDirty = sunoSettingsDirty(sunoDraft, sunoBaseline);

  const dirtyFlags = useMemo(
    () => ({
      profiles: profileDirty,
      publication: publicationDirty,
      preferences: preferencesDirty,
      descriptions: promptTabDirty.descriptions,
      structures: promptTabDirty.structures,
      moods: promptTabDirty.moods,
      pools: false,
      suno: sunoDirty,
    }),
    [
      preferencesDirty,
      profileDirty,
      promptTabDirty.descriptions,
      promptTabDirty.moods,
      promptTabDirty.structures,
      publicationDirty,
      sunoDirty,
    ],
  );
  const dirtyTabs = useMemo(
    () => SETTINGS_TABS.filter((tab) => dirtyFlags[tab.id]).map((tab) => tab.id),
    [dirtyFlags],
  );
  const dirtyCount = countDirtyTabs(dirtyFlags);

  const allowanceValue =
    meQuery.data?.effective_profile_allowance ?? meQuery.data?.profile_allowance ?? null;
  const profileLimitReached = allowanceValue !== null && profiles.length >= allowanceValue;
  const profileAllowanceText = allowanceValue === null ? `${profiles.length}` : `${profiles.length} / ${allowanceValue}`;
  const promptLibraryOnly = imagePromptLibraryOnly(settings);

  const clearTabError = useCallback((tab: SettingsTab) => {
    setTabErrors((prev) => {
      if (!prev[tab]) return prev;
      const next = { ...prev };
      delete next[tab];
      return next;
    });
  }, []);

  const setTabError = useCallback((tab: SettingsTab, message: string) => {
    setTabErrors((prev) => ({ ...prev, [tab]: message }));
  }, []);

  const applyProfile = useCallback((profile: ChannelProfile) => {
    const draft = buildProfileDraft(profile);
    setSelectedProfileId(profile.id);
    setIsNewProfile(false);
    setProfileDraft(draft);
    setProfileBaseline(draft);
    setProfileErrors({});
    folderTouchedRef.current = Boolean(profile.folder_name);
    setTabErrors((prev) => {
      if (!prev.profiles) return prev;
      const next = { ...prev };
      delete next.profiles;
      return next;
    });
  }, []);

  const applyPublicationProfile = useCallback(
    (profileId: string | null) => {
      setPublicationProfileId(profileId);
      const profile = profiles.find((item) => item.id === profileId) ?? null;
      const draft = buildPublicationDraft(profile);
      setPublicationDraft(draft);
      setPublicationBaseline(draft);
      setPublicationErrors({});
    },
    [profiles],
  );

  const resetEditor = useCallback(() => {
    const draft = emptyProfileDraft();
    setSelectedProfileId(null);
    setIsNewProfile(false);
    setProfileDraft(draft);
    setProfileBaseline(draft);
    setProfileErrors({});
    folderTouchedRef.current = false;
  }, []);

  const initializedRef = useRef(false);
  const handledParamRef = useRef<string | null>(null);

  // First successful profile load selects the requested profile (from
  // `/settings?profile=<id>`) or the first one by name.
  useEffect(() => {
    if (initializedRef.current) return;
    if (profilesQuery.isLoading || profilesQuery.isError) return;
    initializedRef.current = true;
    handledParamRef.current = requestedProfileId;
    const requested = requestedProfileId
      ? profiles.find((profile) => profile.id === requestedProfileId) ?? null
      : null;
    const target = requested ?? filterProfiles(profiles, "")[0] ?? null;
    if (target) {
      applyProfile(target);
      applyPublicationProfile(target.id);
    } else {
      resetEditor();
      setPublicationProfileId(null);
      const draft = emptyPublicationDraft();
      setPublicationDraft(draft);
      setPublicationBaseline(draft);
    }
  }, [
    applyProfile,
    applyPublicationProfile,
    profiles,
    profilesQuery.isError,
    profilesQuery.isLoading,
    requestedProfileId,
    resetEditor,
  ]);

  // Later navigations to `/settings?profile=<id>` select that profile, with the
  // same dirty guard as clicking it in the list.
  useEffect(() => {
    if (!initializedRef.current) return;
    if (!requestedProfileId || handledParamRef.current === requestedProfileId) return;
    handledParamRef.current = requestedProfileId;
    const target = profiles.find((profile) => profile.id === requestedProfileId);
    if (!target || target.id === selectedProfileId) return;
    if (profileDirty) setPendingConfirm({ kind: "switch-profile", profile: target });
    else applyProfile(target);
  }, [applyProfile, profileDirty, profiles, requestedProfileId, selectedProfileId]);

  const settingsInitializedRef = useRef(false);
  const devicePreferences = deviceQuery.data ?? { ffmpegPath: "", sunoOutputDir: "" };
  useEffect(() => {
    if (settingsInitializedRef.current || !settingsQuery.data || !deviceQuery.isFetched) return;
    settingsInitializedRef.current = true;
    const fromAccount = buildPreferencesDraft(settingsQuery.data);
    const draft: PreferencesDraft = {
      ...fromAccount,
      ffmpegPath: devicePreferences.ffmpegPath || fromAccount.ffmpegPath,
      sunoOutputDir: devicePreferences.sunoOutputDir || fromAccount.sunoOutputDir,
    };
    setPreferencesDraft(draft);
    setPreferencesBaseline(draft);
    if (
      (!devicePreferences.ffmpegPath && fromAccount.ffmpegPath) ||
      (!devicePreferences.sunoOutputDir && fromAccount.sunoOutputDir)
    ) {
      void window.camxora?.preferences
        ?.setDevice({ ffmpegPath: draft.ffmpegPath, sunoOutputDir: draft.sunoOutputDir })
        .then((result) => {
          if (result.ok) queryClient.setQueryData(keys.device, result.data);
        });
    }
  }, [
    devicePreferences.ffmpegPath,
    devicePreferences.sunoOutputDir,
    deviceQuery.isFetched,
    keys.device,
    queryClient,
    settingsQuery.data,
  ]);

  const promptSettingsInitializedRef = useRef(false);
  useEffect(() => {
    if (promptSettingsInitializedRef.current || !settingsQuery.data) return;
    promptSettingsInitializedRef.current = true;
    const defaults = buildPromptDefaultsDraft(settingsQuery.data);
    setPromptDefaults(defaults);
    setPromptDefaultsBaseline(defaults);
    const suno = buildSunoSettingsDraft(settingsQuery.data);
    setSunoDraft(suno);
    setSunoBaseline(suno);
  }, [settingsQuery.data]);

  const checkFfmpeg = useCallback(async () => {
    if (!window.camxora?.ffmpeg) {
      setFfmpegStatus({ state: "unavailable", message: "FFmpeg checks run in the desktop app." });
      return;
    }
    setFfmpegStatus({ state: "checking", message: "Checking FFmpeg…" });
    try {
      const result = await window.camxora.ffmpeg.available();
      if (result.ok && result.data.available) {
        setFfmpegStatus({ state: "available", message: "FFmpeg is available on this machine." });
      } else {
        setFfmpegStatus({
          state: "missing",
          message: "FFmpeg was not found. Set a path below or use Download FFmpeg.",
        });
      }
    } catch {
      setFfmpegStatus({ state: "missing", message: "FFmpeg could not be checked." });
    }
  }, []);

  useEffect(() => {
    void checkFfmpeg();
  }, [checkFfmpeg]);

  // -------------------------------------------------------------------------
  // Profile actions
  // -------------------------------------------------------------------------

  const updateProfileDraft = useCallback((patch: Partial<ProfileDraft>) => {
    setProfileDraft((prev) => {
      const next = { ...prev, ...patch };
      if (patch.name !== undefined && !folderTouchedRef.current) {
        next.folderName = patch.name.trim() ? slugifyProfileFolder(patch.name) : "";
      }
      return next;
    });
    setProfileErrors((prev) => {
      if (!Object.keys(prev).length) return prev;
      const next = { ...prev };
      if (patch.name !== undefined) delete next.name;
      if (patch.folderName !== undefined) delete next.folderName;
      if (patch.runPrefix !== undefined) delete next.runPrefix;
      return next;
    });
  }, []);

  const updateProfileFolder = useCallback((value: string) => {
    folderTouchedRef.current = true;
    setProfileDraft((prev) => ({ ...prev, folderName: value }));
    setProfileErrors((prev) => {
      if (!prev.folderName) return prev;
      const next = { ...prev };
      delete next.folderName;
      return next;
    });
  }, []);

  const beginNewProfile = useCallback(() => {
    const draft = emptyProfileDraft();
    setSelectedProfileId(null);
    setIsNewProfile(true);
    setProfileDraft(draft);
    setProfileBaseline(draft);
    setProfileErrors({});
    folderTouchedRef.current = false;
    clearTabError("profiles");
  }, [clearTabError]);

  const requestNewProfile = useCallback(() => {
    if (profileLimitReached) {
      setTabError(
        "profiles",
        `Profile limit reached (${profileAllowanceText}). Delete a profile or raise the allowance in the account portal.`,
      );
      return;
    }
    if (profileDirty) {
      setPendingConfirm({ kind: "new-profile" });
      return;
    }
    beginNewProfile();
  }, [beginNewProfile, profileAllowanceText, profileDirty, profileLimitReached, setTabError]);

  const requestSelectProfile = useCallback(
    (profile: ChannelProfile) => {
      if (profile.id === selectedProfileId && !isNewProfile) return;
      if (profileDirty) {
        setPendingConfirm({ kind: "switch-profile", profile });
        return;
      }
      applyProfile(profile);
    },
    [applyProfile, isNewProfile, profileDirty, selectedProfileId],
  );

  const saveProfilesInternal = useCallback(async (): Promise<boolean> => {
    const errors = validateProfileDraft(
      profileDraft,
      profiles,
      isNewProfile ? null : selectedProfileId,
    );
    setProfileErrors(errors);
    if (Object.keys(errors).length > 0) {
      setTabError("profiles", "Fix the highlighted fields before saving.");
      return false;
    }
    const payload = buildProfilePayload(profileDraft);
    try {
      const saved =
        isNewProfile || !selectedProfileId
          ? await createProfileApi(payload)
          : await updateProfileApi(selectedProfileId, payload);
      queryClient.setQueryData<ChannelProfile[]>(keys.profiles, (current) =>
        upsertProfile(current, saved),
      );
      const draft = buildProfileDraft(saved);
      setSelectedProfileId(saved.id);
      setIsNewProfile(false);
      setProfileDraft(draft);
      setProfileBaseline(draft);
      folderTouchedRef.current = Boolean(saved.folder_name);
      setProfileErrors({});
      clearTabError("profiles");
      toast(isNewProfile ? `Created profile ${saved.name}.` : "Profiles saved.", "success");
      void queryClient.invalidateQueries({ queryKey: keys.me });
      return true;
    } catch (error) {
      const message = `Could not save the profile. ${errorMessage(error)}`;
      setTabError("profiles", message);
      toast(message, "danger");
      return false;
    }
  }, [
    clearTabError,
    isNewProfile,
    keys,
    profileDraft,
    profiles,
    queryClient,
    selectedProfileId,
    setTabError,
  ]);

  const deleteProfileNow = useCallback(
    async (profile: ChannelProfile) => {
      setConfirmBusy(true);
      try {
        await deleteProfileApi(profile.id);
        const remaining = profiles.filter((item) => item.id !== profile.id);
        const nextProfile = filterProfiles(remaining, "")[0] ?? null;
        queryClient.setQueryData<ChannelProfile[]>(keys.profiles, (current) =>
          Array.isArray(current) ? current.filter((item) => item.id !== profile.id) : [],
        );
        if (selectedProfileId === profile.id) {
          if (nextProfile) applyProfile(nextProfile);
          else resetEditor();
        }
        if (publicationProfileId === profile.id) {
          applyPublicationProfile(nextProfile?.id ?? null);
        }
        toast(`Deleted profile ${profile.name}.`, "success");
        void queryClient.invalidateQueries({ queryKey: keys.me });
      } catch (error) {
        const message = `Could not delete ${profile.name}. ${errorMessage(error)}`;
        setTabError("profiles", message);
        toast(message, "danger");
      } finally {
        setConfirmBusy(false);
        setPendingConfirm(null);
      }
    },
    [
      applyProfile,
      applyPublicationProfile,
      keys,
      profiles,
      publicationProfileId,
      queryClient,
      resetEditor,
      selectedProfileId,
      setTabError,
    ],
  );

  const discardProfiles = useCallback(() => {
    if (isNewProfile) {
      if (profiles.length > 0) applyProfile(filterProfiles(profiles, "")[0]);
      else resetEditor();
      return;
    }
    setProfileDraft(profileBaseline);
    setProfileErrors({});
    setTabErrors((prev) => {
      if (!prev.profiles) return prev;
      const next = { ...prev };
      delete next.profiles;
      return next;
    });
  }, [applyProfile, isNewProfile, profileBaseline, profiles, resetEditor]);

  // -------------------------------------------------------------------------
  // Publication actions
  // -------------------------------------------------------------------------

  const updatePublicationDraft = useCallback((patch: Partial<PublicationDraft>) => {
    setPublicationDraft((prev) => ({ ...prev, ...patch }));
    setPublicationErrors((prev) => {
      if (!Object.keys(prev).length) return prev;
      const next = { ...prev };
      for (const key of Object.keys(patch) as PublicationField[]) delete next[key];
      return next;
    });
  }, []);

  const requestPublicationProfile = useCallback(
    (profileId: string) => {
      if (profileId === publicationProfileId) return;
      if (publicationDirty) {
        setPendingConfirm({ kind: "switch-publication", profileId });
        return;
      }
      applyPublicationProfile(profileId);
    },
    [applyPublicationProfile, publicationDirty, publicationProfileId],
  );

  const savePublicationInternal = useCallback(async (): Promise<boolean> => {
    if (!publicationProfileId || !publicationProfile) {
      setTabError("publication", "Select a profile before saving publication settings.");
      return false;
    }
    const errors = validatePublicationDraft(publicationDraft, {
      connected: publicationConnected,
      playlistsLoaded: playlistsQuery.isSuccess,
      playlists,
    });
    setPublicationErrors(errors);
    if (Object.keys(errors).length > 0) {
      setTabError("publication", "Fix the highlighted fields before saving.");
      return false;
    }
    const payload = buildPublicationPayload(
      publicationDraft,
      recordOf(publicationProfile.youtube_config),
    );
    try {
      const saved = await updateProfileApi(publicationProfile.id, {
        youtube_config: payload,
        ...(publicationDraft.videoTemplateId.trim()
          ? { video_template_id: publicationDraft.videoTemplateId.trim() }
          : {}),
        ...(publicationDraft.reelTemplateId.trim()
          ? { reel_template_id: publicationDraft.reelTemplateId.trim() }
          : {}),
      });
      queryClient.setQueryData<ChannelProfile[]>(keys.profiles, (current) =>
        upsertProfile(current, saved),
      );
      const draft = buildPublicationDraft(saved);
      setPublicationDraft(draft);
      setPublicationBaseline(draft);
      setPublicationErrors({});
      clearTabError("publication");
      toast("Publication saved.", "success");
      return true;
    } catch (error) {
      const message = `Could not save publication settings. ${errorMessage(error)}`;
      setTabError("publication", message);
      toast(message, "danger");
      return false;
    }
  }, [
    clearTabError,
    keys,
    playlists,
    playlistsQuery.isSuccess,
    publicationConnected,
    publicationDraft,
    publicationProfile,
    publicationProfileId,
    queryClient,
    setTabError,
  ]);

  const discardPublication = useCallback(() => {
    setPublicationDraft(publicationBaseline);
    setPublicationErrors({});
    setTabErrors((prev) => {
      if (!prev.publication) return prev;
      const next = { ...prev };
      delete next.publication;
      return next;
    });
  }, [publicationBaseline]);

  const addPlaylist = useCallback(
    async (title: string) => {
      const trimmed = title.trim();
      if (!publicationProfileId || !trimmed) return;
      setPlaylistBusy(true);
      try {
        const created = await createPlaylistApi(publicationProfileId, trimmed);
        await queryClient.invalidateQueries({
          queryKey: keys.playlists(publicationProfileId),
        });
        if (created) {
          setPublicationDraft((prev) => ({ ...prev, playlist: created.id }));
          toast(`Created playlist ${created.title}.`, "success");
        } else {
          toast("The playlist was created but the response could not be read.", "warning");
        }
      } catch (error) {
        const message = `Could not create the playlist. ${errorMessage(error)}`;
        setTabError("publication", message);
      } finally {
        setPlaylistBusy(false);
      }
    },
    [keys, publicationProfileId, queryClient, setTabError],
  );

  // -------------------------------------------------------------------------
  // Preferences actions
  // -------------------------------------------------------------------------

  const updatePreferences = useCallback((patch: Partial<PreferencesDraft>) => {
    setPreferencesDraft((prev) => ({ ...prev, ...patch }));
    setPreferencesErrors((prev) => {
      if (!Object.keys(prev).length) return prev;
      const next = { ...prev };
      for (const key of Object.keys(patch) as Array<keyof PreferencesDraft>) delete next[key];
      return next;
    });
    setPreferencesWarnings([]);
  }, []);

  const savePreferencesInternal = useCallback(async (): Promise<boolean> => {
    const errors = validatePreferencesDraft(preferencesDraft);
    setPreferencesErrors(errors);
    if (Object.keys(errors).length > 0) {
      setTabError("preferences", "Fix the highlighted fields before saving.");
      return false;
    }
    const patch = buildPreferencesPatch(preferencesDraft, preferencesBaseline);
    if (Object.keys(patch).length === 0) {
      clearTabError("preferences");
      return true;
    }
    const warnings: string[] = [];
    const sunoDir = preferencesDraft.sunoOutputDir.trim();
    if (sunoDir && window.camxora?.files) {
      try {
        const result = await window.camxora.files.ensureDir(sunoDir);
        if (!result.ok) {
          warnings.push(
            `The Suno output folder could not be created (${result.error.message}). The path was still saved.`,
          );
        }
      } catch {
        warnings.push("The Suno output folder could not be checked. The path was still saved.");
      }
    }
    if (window.camxora?.preferences) {
      try {
        const device = await window.camxora.preferences.setDevice({
          ffmpegPath: preferencesDraft.ffmpegPath.trim(),
          sunoOutputDir: sunoDir,
        });
        if (device.ok) {
          queryClient.setQueryData(keys.device, device.data);
        } else {
          warnings.push(`The device paths were not saved (${device.error.message}).`);
        }
      } catch {
        warnings.push("The device paths were not saved locally.");
      }
    }
    try {
      const merged: SettingsMap = await patchSettings(patch);
      queryClient.setQueryData(keys.values, merged);
      const draft = buildPreferencesDraft(merged);
      setPreferencesDraft(draft);
      setPreferencesBaseline(draft);
      setPreferencesErrors({});
      setPreferencesWarnings(warnings);
      clearTabError("preferences");
      toast("Preferences saved.", "success");
      void checkFfmpeg();
      return true;
    } catch (error) {
      const message = `Could not save preferences. ${errorMessage(error)}`;
      setTabError("preferences", message);
      toast(message, "danger");
      return false;
    }
  }, [
    checkFfmpeg,
    clearTabError,
    keys,
    preferencesBaseline,
    preferencesDraft,
    queryClient,
    setTabError,
  ]);

  const discardPreferences = useCallback(() => {
    setPreferencesDraft(preferencesBaseline);
    setPreferencesErrors({});
    setPreferencesWarnings([]);
    setTabErrors((prev) => {
      if (!prev.preferences) return prev;
      const next = { ...prev };
      delete next.preferences;
      return next;
    });
  }, [preferencesBaseline]);

  // -------------------------------------------------------------------------
  // Prompt catalog actions
  // -------------------------------------------------------------------------

  const updatePromptDefault = useCallback(
    (field: keyof PromptDefaultsDraft, value: string) => {
      setPromptDefaults((prev) => ({ ...prev, [field]: value }));
      clearTabError(field === "moodId" ? "moods" : "descriptions");
      if (field === "structureId") clearTabError("structures");
    },
    [clearTabError],
  );

  const updatePromptDraft = useCallback((kind: PromptKind, patch: Partial<PromptEditorDraft>) => {
    setPromptDrafts((prev) => ({ ...prev, [kind]: { ...prev[kind], ...patch } }));
    setPromptFieldErrors((prev) => {
      const current = prev[kind];
      if (!Object.keys(current).length) return prev;
      const next = { ...current };
      for (const key of Object.keys(patch) as PromptEditorField[]) delete next[key];
      return { ...prev, [kind]: next };
    });
  }, []);

  const savePromptEditorInternal = useCallback(
    async (kind: PromptKind): Promise<boolean> => {
      const draft = promptDrafts[kind];
      const errors = validatePromptEditorDraft(draft, userPrompts[kind] ?? []);
      setPromptFieldErrors((prev) => ({ ...prev, [kind]: errors }));
      if (Object.keys(errors).length > 0) {
        setTabError(kind, "Fix the highlighted fields before saving.");
        return false;
      }
      const payload = buildUserPromptPayload(draft);
      setPromptBusy(kind);
      try {
        const saved = draft.id
          ? await updateMyPromptApi(kind, draft.id, payload)
          : await createMyPromptApi(kind, payload);
        queryClient.setQueryData<UserPromptEntry[]>(keys.myPrompts(kind), (current) =>
          upsertUserPrompt(Array.isArray(current) ? current : [], saved),
        );
        void queryClient.invalidateQueries({ queryKey: keys.promptWorkspace(kind) });
        const next = buildPromptEditorDraft(saved);
        setPromptDrafts((prev) => ({ ...prev, [kind]: next }));
        setPromptBaselines((prev) => ({ ...prev, [kind]: next }));
        setPromptFieldErrors((prev) => ({ ...prev, [kind]: {} }));
        clearTabError(kind);
        toast(draft.id ? `Saved ${saved.name}.` : `Created ${saved.name}.`, "success");
        return true;
      } catch (error) {
        const message = `Could not save the ${promptKindInfo(kind).singular}. ${errorMessage(error)}`;
        setTabError(kind, message);
        toast(message, "danger");
        return false;
      } finally {
        setPromptBusy(null);
      }
    },
    [clearTabError, keys, promptDrafts, queryClient, setTabError, userPrompts],
  );

  const resetPromptFromBaseline = useCallback((kind: PromptKind) => {
    setPromptDrafts((prev) => ({ ...prev, [kind]: promptBaselines[kind] }));
    setPromptFieldErrors((prev) => ({ ...prev, [kind]: {} }));
    setTabErrors((prev) => {
      if (!prev[kind]) return prev;
      const next = { ...prev };
      delete next[kind];
      return next;
    });
  }, [promptBaselines]);

  const discardAllPrompts = useCallback(() => {
    setPromptDrafts(resetAllPromptEditors());
    setPromptBaselines(resetAllPromptEditors());
    setPromptFieldErrors({ descriptions: {}, structures: {}, moods: {} });
    setPromptDefaults(promptDefaultsBaseline);
  }, [promptDefaultsBaseline]);

  const loadPromptEntry = useCallback((kind: PromptKind, entry: UserPromptEntry) => {
    const draft = buildPromptEditorDraft(entry);
    setPromptDrafts((prev) => ({ ...prev, [kind]: draft }));
    setPromptBaselines((prev) => ({ ...prev, [kind]: draft }));
    setPromptFieldErrors((prev) => ({ ...prev, [kind]: {} }));
  }, []);

  const beginNewPrompt = useCallback((kind: PromptKind) => {
    const draft = emptyPromptEditorDraft();
    setPromptDrafts((prev) => ({ ...prev, [kind]: draft }));
    setPromptBaselines((prev) => ({ ...prev, [kind]: draft }));
    setPromptFieldErrors((prev) => ({ ...prev, [kind]: {} }));
    setTabErrors((prev) => {
      if (!prev[kind]) return prev;
      const next = { ...prev };
      delete next[kind];
      return next;
    });
  }, []);

  const requestSelectPrompt = useCallback(
    (kind: PromptKind, entry: UserPromptEntry) => {
      if (promptDrafts[kind].id === entry.id && !promptEditorDirty[kind]) return;
      if (promptEditorDirty[kind]) {
        setPendingConfirm({ kind: "switch-prompt", promptKind: kind, entry });
        return;
      }
      loadPromptEntry(kind, entry);
    },
    [loadPromptEntry, promptDrafts, promptEditorDirty],
  );

  const requestNewPrompt = useCallback(
    (kind: PromptKind) => {
      if (promptEditorDirty[kind]) {
        setPendingConfirm({ kind: "new-prompt", promptKind: kind });
        return;
      }
      beginNewPrompt(kind);
    },
    [beginNewPrompt, promptEditorDirty],
  );

  const requestDeletePrompt = useCallback((kind: PromptKind, entry: UserPromptEntry) => {
    setPendingConfirm({ kind: "delete-prompt", promptKind: kind, entry });
  }, []);

  const deletePromptNow = useCallback(
    async (kind: PromptKind, entry: UserPromptEntry) => {
      setConfirmBusy(true);
      try {
        await deleteMyPromptApi(kind, entry.id);
        queryClient.setQueryData<UserPromptEntry[]>(keys.myPrompts(kind), (current) =>
          removeUserPrompt(Array.isArray(current) ? current : [], entry.id),
        );
        void queryClient.invalidateQueries({ queryKey: keys.promptWorkspace(kind) });
        if (promptDrafts[kind].id === entry.id) {
          const draft = emptyPromptEditorDraft();
          setPromptDrafts((prev) => ({ ...prev, [kind]: draft }));
          setPromptBaselines((prev) => ({ ...prev, [kind]: draft }));
        }
        // A removed entry can no longer be a Music default. Clearing the draft
        // marks the tab dirty so the next Save all persists the change.
        setPromptDefaults((prev) => ({
          ...prev,
          ...(prev.descriptionId === entry.id ? { descriptionId: "" } : {}),
          ...(prev.structureId === entry.id ? { structureId: "" } : {}),
          ...(prev.moodId === entry.id ? { moodId: "" } : {}),
        }));
        clearTabError(kind);
        toast(`Deleted ${entry.name}.`, "success");
      } catch (error) {
        const message = `Could not delete ${entry.name}. ${errorMessage(error)}`;
        setTabError(kind, message);
        toast(message, "danger");
      } finally {
        setConfirmBusy(false);
        setPendingConfirm(null);
      }
    },
    [clearTabError, keys, promptDrafts, queryClient, setTabError],
  );

  const savePromptTabInternal = useCallback(
    async (kind: PromptKind): Promise<boolean> => {
      if (promptEditorDirty[kind]) {
        const saved = await savePromptEditorInternal(kind);
        if (!saved) return false;
      }
      const allowed = PROMPT_DEFAULT_KEYS_BY_KIND[kind];
      const fullPatch = buildPromptDefaultsPatch(promptDefaults, promptDefaultsBaseline);
      const patch: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(fullPatch)) {
        if (allowed.includes(key)) patch[key] = value;
      }
      if (Object.keys(patch).length === 0) {
        clearTabError(kind);
        return true;
      }
      try {
        const merged: SettingsMap = await patchSettings(patch);
        queryClient.setQueryData(keys.values, merged);
        setPromptDefaults((prev) => {
          const next = { ...prev };
          for (const [field, key] of PROMPT_DEFAULT_FIELDS) {
            if (key in patch) next[field] = String(patch[key] ?? "");
          }
          return next;
        });
        setPromptDefaultsBaseline((prev) => {
          const next = { ...prev };
          for (const [field, key] of PROMPT_DEFAULT_FIELDS) {
            if (key in patch) next[field] = String(patch[key] ?? "");
          }
          return next;
        });
        clearTabError(kind);
        toast(`${promptKindInfo(kind).label} default saved.`, "success");
        return true;
      } catch (error) {
        const message = `Could not save the ${promptKindInfo(kind).singular} default. ${errorMessage(error)}`;
        setTabError(kind, message);
        toast(message, "danger");
        return false;
      }
    },
    [
      clearTabError,
      keys,
      promptDefaults,
      promptDefaultsBaseline,
      promptEditorDirty,
      queryClient,
      savePromptEditorInternal,
      setTabError,
    ],
  );

  // -------------------------------------------------------------------------
  // Pools actions (read-only)
  // -------------------------------------------------------------------------

  const selectPoolKind = useCallback((kind: PoolKind) => {
    setPoolKindState(kind);
    setPoolOffset(0);
  }, []);

  const nextPoolPage = useCallback(() => {
    setPoolOffset((offset) => {
      const total = poolItemsQuery.data?.total ?? 0;
      return offset + 50 < total ? offset + 50 : offset;
    });
  }, [poolItemsQuery.data?.total]);

  const previousPoolPage = useCallback(() => {
    setPoolOffset((offset) => Math.max(0, offset - 50));
  }, []);

  const refreshPools = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: keys.poolStats });
    void queryClient.invalidateQueries({ queryKey: keys.poolItems(poolKind, poolOffset) });
  }, [keys, poolKind, poolOffset, queryClient]);

  // A shorter pool (or a kind switch) must not strand the pager on an empty
  // page beyond the last one.
  useEffect(() => {
    const total = poolItemsQuery.data?.total;
    if (total === undefined) return;
    const clamped = clampPoolOffset(poolOffset, total);
    if (clamped !== poolOffset) setPoolOffset(clamped);
  }, [poolItemsQuery.data?.total, poolOffset]);

  // -------------------------------------------------------------------------
  // Suno actions
  // -------------------------------------------------------------------------

  const updateSuno = useCallback(
    (patch: Partial<SunoSettingsDraft>) => {
      setSunoDraft((prev) => ({ ...prev, ...patch }));
      setSunoErrors((prev) => {
        if (!Object.keys(prev).length) return prev;
        const next = { ...prev };
        for (const key of Object.keys(patch) as SunoField[]) delete next[key];
        return next;
      });
      clearTabError("suno");
    },
    [clearTabError],
  );

  const saveSunoInternal = useCallback(async (): Promise<boolean> => {
    const errors = validateSunoSettingsDraft(sunoDraft);
    setSunoErrors(errors);
    if (Object.keys(errors).length > 0) {
      setTabError("suno", "Fix the highlighted fields before saving.");
      return false;
    }
    const patch = buildSunoSettingsPatch(sunoDraft, settingsQuery.data);
    if (Object.keys(patch).length === 0) {
      clearTabError("suno");
      return true;
    }
    try {
      const merged: SettingsMap = await patchSettings(patch);
      queryClient.setQueryData(keys.values, merged);
      const next = buildSunoSettingsDraft(merged);
      setSunoDraft(next);
      setSunoBaseline(next);
      setSunoErrors({});
      clearTabError("suno");
      toast("Suno defaults saved.", "success");
      return true;
    } catch (error) {
      const message = `Could not save Suno defaults. ${errorMessage(error)}`;
      setTabError("suno", message);
      toast(message, "danger");
      return false;
    }
  }, [
    clearTabError,
    keys,
    queryClient,
    setTabError,
    settingsQuery.data,
    sunoDraft,
  ]);

  const discardSuno = useCallback(() => {
    setSunoDraft(sunoBaseline);
    setSunoErrors({});
    setTabErrors((prev) => {
      if (!prev.suno) return prev;
      const next = { ...prev };
      delete next.suno;
      return next;
    });
  }, [sunoBaseline]);

  // -------------------------------------------------------------------------
  // YouTube actions
  // -------------------------------------------------------------------------

  const refreshConnections = useCallback(async () => {
    try {
      await queryClient.invalidateQueries({ queryKey: keys.youtube });
    } catch {
      // The card keeps the last loaded status.
    }
  }, [keys, queryClient]);

  const connectYoutube = useCallback(
    async (profileId: string) => {
      setYoutubeBusy("connect");
      clearTabError("profiles");
      try {
        const started = await startYoutubeConnection(profileId);
        if (started.auth_url) {
          const failure = await openExternal(started.auth_url);
          if (failure) throw new Error(failure);
        } else {
          throw new Error("The server did not return a sign-in URL.");
        }
        setPollingProfileId(profileId);
        toast("Finish Google sign-in in your browser.", "info");
      } catch (error) {
        const message = `Could not start YouTube sign-in. ${errorMessage(error)}`;
        setTabError("profiles", message);
        toast(message, "danger");
      } finally {
        setYoutubeBusy(null);
      }
    },
    [clearTabError, setTabError],
  );

  const disconnectYoutubeNow = useCallback(
    async (profile: ChannelProfile) => {
      setConfirmBusy(true);
      setYoutubeBusy("disconnect");
      try {
        await disconnectYoutubeApi(profile.id);
        await refreshConnections();
        toast(`Disconnected YouTube from ${profile.name}.`, "success");
      } catch (error) {
        const message = `Could not disconnect the channel. ${errorMessage(error)}`;
        setTabError("profiles", message);
        toast(message, "danger");
      } finally {
        setYoutubeBusy(null);
        setConfirmBusy(false);
        setPendingConfirm(null);
      }
    },
    [refreshConnections, setTabError],
  );

  const selectYoutubeChannel = useCallback(
    async (profileId: string, channelId: string) => {
      const connection = youtubeConnection(profileId);
      if (!connection?.session_id) {
        setTabError("profiles", "The YouTube session expired. Use Connect channel to start again.");
        return;
      }
      setYoutubeBusy("select");
      try {
        const updated = await selectYoutubeChannelApi(connection.session_id, channelId);
        if (updated?.status === "connected") {
          toast(`Connected ${updated.channel_title ?? "channel"}.`, "success");
        }
        await refreshConnections();
      } catch (error) {
        const message = `Could not select the channel. ${errorMessage(error)}`;
        setTabError("profiles", message);
        toast(message, "danger");
      } finally {
        setYoutubeBusy(null);
      }
    },
    [refreshConnections, setTabError, youtubeConnection],
  );

  // Poll while the browser sign-in is open. The provider records the account
  // when the user finishes the Google step, which can take longer than one
  // refresh cycle.
  useEffect(() => {
    if (!pollingProfileId) return;
    let cancelled = false;
    let attempts = 0;
    const tick = async () => {
      attempts += 1;
      try {
        const list = await queryClient.fetchQuery({
          queryKey: keys.youtube,
          queryFn: fetchYoutubeConnections,
          staleTime: 0,
        });
        if (cancelled) return;
        const connection = list.find((item) => item.profile_id === pollingProfileId);
        if (connection?.status === "connected") {
          setPollingProfileId(null);
          toast(`Connected ${connection.channel_title ?? "channel"}.`, "success");
          return;
        }
        if (connection?.status === "awaiting_channel_selection") {
          setPollingProfileId(null);
          return;
        }
      } catch {
        // Keep polling; a transient failure is not a failed sign-in.
      }
      if (attempts >= 30 && !cancelled) {
        setPollingProfileId(null);
        setTabError(
          "profiles",
          "The YouTube sign-in did not finish. Use Connect channel to start a new flow.",
        );
      }
    };
    void tick();
    const timer = setInterval(() => void tick(), 3000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [keys, pollingProfileId, queryClient, setTabError]);

  // -------------------------------------------------------------------------
  // Global save / discard
  // -------------------------------------------------------------------------

  const saveTab = useCallback(
    async (tab: SettingsTab): Promise<boolean> => {
      if (tab === "profiles") return saveProfilesInternal();
      if (tab === "publication") return savePublicationInternal();
      if (tab === "preferences") return savePreferencesInternal();
      if (tab === "descriptions") return savePromptTabInternal("descriptions");
      if (tab === "structures") return savePromptTabInternal("structures");
      if (tab === "moods") return savePromptTabInternal("moods");
      if (tab === "suno") return saveSunoInternal();
      // Pools are read-only and never dirty.
      return true;
    },
    [
      savePreferencesInternal,
      saveProfilesInternal,
      savePromptTabInternal,
      savePublicationInternal,
      saveSunoInternal,
    ],
  );

  const saveOne = useCallback(
    async (tab: SettingsTab) => {
      if (saving) return;
      setSaving({ tabs: [tab], current: tab });
      try {
        const ok = await saveTab(tab);
        if (ok) setLastSavedAt(Date.now());
      } finally {
        setSaving(null);
      }
    },
    [saveTab, saving],
  );

  const saveAll = useCallback(async () => {
    if (saving) return;
    const tabs = dirtyTabs;
    if (tabs.length === 0) {
      toast("No changes to save.", "info");
      return;
    }
    setSaving({ tabs, current: tabs[0] });
    const failed: SettingsTab[] = [];
    for (const tab of tabs) {
      setSaving({ tabs, current: tab });
      const ok = await saveTab(tab);
      if (!ok) failed.push(tab);
    }
    setSaving(null);
    setLastSavedAt(Date.now());
    if (failed.length === 0) {
      toast("Saved all changes.", "success");
    } else {
      const labels = failed.map((tab) => settingsTabLabel(tab)).join(", ");
      toast(`Some tabs were not saved: ${labels}.`, "danger");
    }
  }, [dirtyTabs, saveTab, saving]);

  const requestDiscardAll = useCallback(() => {
    if (dirtyTabs.length === 0) return;
    setPendingConfirm({ kind: "discard-all" });
  }, [dirtyTabs.length]);

  const cancelConfirm = useCallback(() => {
    if (confirmBusy) return;
    setPendingConfirm(null);
  }, [confirmBusy]);

  const resolveConfirm = useCallback(async () => {
    const pending = pendingConfirm;
    if (!pending) return;
    if (pending.kind === "delete-profile") {
      await deleteProfileNow(pending.profile);
      return;
    }
    if (pending.kind === "disconnect-youtube") {
      await disconnectYoutubeNow(pending.profile);
      return;
    }
    if (pending.kind === "delete-prompt") {
      await deletePromptNow(pending.promptKind, pending.entry);
      return;
    }
    setPendingConfirm(null);
    if (pending.kind === "switch-profile") {
      applyProfile(pending.profile);
      return;
    }
    if (pending.kind === "new-profile") {
      beginNewProfile();
      return;
    }
    if (pending.kind === "switch-publication") {
      applyPublicationProfile(pending.profileId);
      return;
    }
    if (pending.kind === "switch-prompt") {
      loadPromptEntry(pending.promptKind, pending.entry);
      return;
    }
    if (pending.kind === "new-prompt") {
      beginNewPrompt(pending.promptKind);
      return;
    }
    discardProfiles();
    discardPublication();
    discardPreferences();
    discardAllPrompts();
    discardSuno();
  }, [
    applyProfile,
    applyPublicationProfile,
    beginNewProfile,
    beginNewPrompt,
    deleteProfileNow,
    deletePromptNow,
    discardAllPrompts,
    discardPreferences,
    discardProfiles,
    discardPublication,
    discardSuno,
    disconnectYoutubeNow,
    loadPromptEntry,
    pendingConfirm,
  ]);

  const requestDeleteProfile = useCallback((profile: ChannelProfile) => {
    setPendingConfirm({ kind: "delete-profile", profile });
  }, []);

  const requestDisconnectYoutube = useCallback((profile: ChannelProfile) => {
    setPendingConfirm({ kind: "disconnect-youtube", profile });
  }, []);

  const setProfileSearch = useCallback((value: string) => {
    setProfileSearchState(value);
  }, []);

  return {
    // tabs
    activeTab,
    setActiveTab,
    // data state
    profiles,
    profilesLoading: profilesQuery.isLoading,
    profilesError: profilesQuery.isError ? errorMessage(profilesQuery.error) : null,
    retryProfiles: () => void profilesQuery.refetch(),
    me: meQuery.data ?? null,
    settings,
    settingsLoading: settingsQuery.isLoading,
    settingsError: settingsQuery.isError ? errorMessage(settingsQuery.error) : null,
    retrySettings: () => void settingsQuery.refetch(),
    // profiles
    profileSearch,
    setProfileSearch,
    filteredProfiles,
    selectedProfile,
    selectedProfileId,
    isNewProfile,
    profileDraft,
    profileDirty,
    profileErrors,
    updateProfileDraft,
    updateProfileFolder,
    requestNewProfile,
    requestSelectProfile,
    saveProfiles: () => saveOne("profiles"),
    discardProfiles,
    requestDeleteProfile,
    profileAllowanceText,
    profileLimitReached,
    // publication
    publicationProfileId,
    publicationProfile,
    publicationDraft,
    publicationDirty,
    publicationErrors,
    publicationConnection,
    publicationConnected,
    updatePublicationDraft,
    requestPublicationProfile,
    savePublication: () => saveOne("publication"),
    discardPublication,
    playlists,
    playlistsLoading: playlistsQuery.isLoading,
    playlistsError: playlistsQuery.isError ? errorMessage(playlistsQuery.error) : null,
    retryPlaylists: () => void playlistsQuery.refetch(),
    createPlaylist: addPlaylist,
    playlistBusy,
    videoTemplates: videoTemplatesQuery.data ?? [],
    videoTemplatesLoading: videoTemplatesQuery.isLoading,
    retryVideoTemplates: () => void videoTemplatesQuery.refetch(),
    // preferences
    preferencesDraft,
    preferencesDirty,
    preferencesErrors,
    preferencesWarnings,
    updatePreferences,
    savePreferences: () => saveOne("preferences"),
    discardPreferences,
    ffmpegStatus,
    checkFfmpeg: () => void checkFfmpeg(),
    promptLibraryOnly,
    // prompt catalogs
    promptWorkspace,
    promptWorkspaceLoading,
    promptWorkspaceError,
    userPrompts,
    userPromptsLoading,
    userPromptsError,
    retryPromptWorkspace: (kind: PromptKind) => {
      const query =
        kind === "descriptions"
          ? descriptionWorkspaceQuery
          : kind === "structures"
            ? structureWorkspaceQuery
            : moodWorkspaceQuery;
      void query.refetch();
    },
    retryUserPrompts: (kind: PromptKind) => {
      const query =
        kind === "descriptions"
          ? descriptionPromptsQuery
          : kind === "structures"
            ? structurePromptsQuery
            : moodPromptsQuery;
      void query.refetch();
    },
    promptDefaults,
    promptDefaultsDirty,
    promptDrafts,
    promptEditorDirty,
    promptFieldErrors,
    promptBusy,
    updatePromptDefault,
    updatePromptDraft,
    requestSelectPrompt,
    requestNewPrompt,
    savePromptEditor: (kind: PromptKind) => savePromptEditorInternal(kind),
    requestDeletePrompt,
    savePromptTab: (kind: PromptKind) => saveOne(kind),
    resetPromptEditor: resetPromptFromBaseline,
    discardAllPrompts,
    // content pools (read-only)
    poolKind,
    selectPoolKind,
    poolOffset,
    poolTotal: poolItemsQuery.data?.total ?? poolStats?.[poolKind]?.total ?? 0,
    poolItems: poolItemsQuery.data?.items ?? [],
    poolStats,
    poolStatsLoading: poolStatsQuery.isLoading,
    poolStatsError: poolStatsQuery.isError ? errorMessage(poolStatsQuery.error) : null,
    poolItemsLoading: poolItemsQuery.isLoading,
    poolItemsFetching: poolItemsQuery.isFetching,
    poolItemsError: poolItemsQuery.isError ? errorMessage(poolItemsQuery.error) : null,
    retryPools: refreshPools,
    refreshPools,
    nextPoolPage,
    previousPoolPage,
    // suno
    sunoDraft,
    sunoDirty,
    sunoErrors,
    updateSuno,
    saveSuno: () => saveOne("suno"),
    discardSuno,
    // youtube
    youtubeConnection,
    youtubeBusy,
    connectYoutube: (profileId: string) => void connectYoutube(profileId),
    requestDisconnectYoutube,
    selectYoutubeChannel: (profileId: string, channelId: string) =>
      void selectYoutubeChannel(profileId, channelId),
    pollingProfileId,
    refreshConnections: () => void refreshConnections(),
    connectionsLoading: connectionsQuery.isLoading,
    connectionsError: connectionsQuery.isError ? errorMessage(connectionsQuery.error) : null,
    // global
    tabErrors,
    clearTabError,
    saving,
    saveAll: () => void saveAll(),
    requestDiscardAll,
    dirtyTabs,
    dirtyCount,
    lastSavedAt,
    pendingConfirm,
    confirmBusy,
    resolveConfirm: () => void resolveConfirm(),
    cancelConfirm,
  };
}

export type SettingsWorkspace = ReturnType<typeof useSettingsWorkspace>;
