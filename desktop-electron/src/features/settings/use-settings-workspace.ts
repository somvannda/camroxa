import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { errorMessage } from "../../lib/api";
import { toast } from "../../components/toast";
import type { ChannelProfile } from "../dashboard/account-types";
import { openExternal } from "../auth/portal";
import {
  createPlaylist as createPlaylistApi,
  createProfile as createProfileApi,
  deleteProfile as deleteProfileApi,
  disconnectYoutube as disconnectYoutubeApi,
  fetchYoutubeConnections,
  patchSettings,
  selectYoutubeChannel as selectYoutubeChannelApi,
  startYoutubeConnection,
  updateProfile as updateProfileApi,
  type SettingsMap,
  type YouTubeConnection,
} from "./settings-api";
import {
  buildPreferencesDraft,
  buildPreferencesPatch,
  buildProfileDraft,
  buildProfilePayload,
  buildPublicationDraft,
  buildPublicationPayload,
  countDirtyTabs,
  defaultPreferencesDraft,
  emptyProfileDraft,
  emptyPublicationDraft,
  filterProfiles,
  imagePromptLibraryOnly,
  preferencesDraftDirty,
  profileDraftDirty,
  publicationDraftDirty,
  recordOf,
  slugifyProfileFolder,
  validatePreferencesDraft,
  validateProfileDraft,
  validatePublicationDraft,
  type FfmpegStatus,
  type PreferencesDraft,
  type ProfileDraft,
  type ProfileField,
  type PublicationDraft,
  type PublicationField,
  type SettingsTab,
} from "./settings-types";
import {
  settingsKeys,
  useDevicePreferencesQuery,
  useMeQuery,
  usePlaylistsQuery,
  useProfilesQuery,
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
  | { kind: "disconnect-youtube"; profile: ChannelProfile };

export interface SavingState {
  tabs: SettingsTab[];
  current: SettingsTab | null;
}

function upsertProfile(list: ChannelProfile[] | undefined, profile: ChannelProfile): ChannelProfile[] {
  const current = Array.isArray(list) ? list : [];
  const found = current.some((item) => item.id === profile.id);
  return found ? current.map((item) => (item.id === profile.id ? profile : item)) : [...current, profile];
}

export function useSettingsWorkspace() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const profilesQuery = useProfilesQuery();
  const meQuery = useMeQuery();
  const settingsQuery = useSettingsQuery();
  const deviceQuery = useDevicePreferencesQuery();
  const connectionsQuery = useYoutubeConnectionsQuery();
  const videoTemplatesQuery = useVideoTemplatesQuery();
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

  const profileDirty = profileDraftDirty(profileDraft, profileBaseline);
  const publicationDirty = publicationDraftDirty(publicationDraft, publicationBaseline);
  const preferencesDirty = preferencesDraftDirty(preferencesDraft, preferencesBaseline);

  const dirtyTabs = useMemo(() => {
    const tabs: SettingsTab[] = [];
    if (profileDirty) tabs.push("profiles");
    if (publicationDirty) tabs.push("publication");
    if (preferencesDirty) tabs.push("preferences");
    return tabs;
  }, [preferencesDirty, profileDirty, publicationDirty]);
  const dirtyCount = countDirtyTabs({
    profiles: profileDirty,
    publication: publicationDirty,
    preferences: preferencesDirty,
  });

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
          if (result.ok) queryClient.setQueryData(settingsKeys.device, result.data);
        });
    }
  }, [
    devicePreferences.ffmpegPath,
    devicePreferences.sunoOutputDir,
    deviceQuery.isFetched,
    queryClient,
    settingsQuery.data,
  ]);

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
      queryClient.setQueryData<ChannelProfile[]>(settingsKeys.profiles, (current) =>
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
      void queryClient.invalidateQueries({ queryKey: settingsKeys.me });
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
        queryClient.setQueryData<ChannelProfile[]>(settingsKeys.profiles, (current) =>
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
        void queryClient.invalidateQueries({ queryKey: settingsKeys.me });
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
      queryClient.setQueryData<ChannelProfile[]>(settingsKeys.profiles, (current) =>
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
          queryKey: settingsKeys.playlists(publicationProfileId),
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
    [publicationProfileId, queryClient, setTabError],
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
          queryClient.setQueryData(settingsKeys.device, device.data);
        } else {
          warnings.push(`The device paths were not saved (${device.error.message}).`);
        }
      } catch {
        warnings.push("The device paths were not saved locally.");
      }
    }
    try {
      const merged: SettingsMap = await patchSettings(patch);
      queryClient.setQueryData(settingsKeys.values, merged);
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
  // YouTube actions
  // -------------------------------------------------------------------------

  const refreshConnections = useCallback(async () => {
    try {
      await queryClient.invalidateQueries({ queryKey: settingsKeys.youtube });
    } catch {
      // The card keeps the last loaded status.
    }
  }, [queryClient]);

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
          queryKey: settingsKeys.youtube,
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
  }, [pollingProfileId, queryClient, setTabError]);

  // -------------------------------------------------------------------------
  // Global save / discard
  // -------------------------------------------------------------------------

  const saveTab = useCallback(
    async (tab: SettingsTab): Promise<boolean> => {
      if (tab === "profiles") return saveProfilesInternal();
      if (tab === "publication") return savePublicationInternal();
      return savePreferencesInternal();
    },
    [savePreferencesInternal, saveProfilesInternal, savePublicationInternal],
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
      const labels = failed
        .map((tab) => (tab === "profiles" ? "Profiles" : tab === "publication" ? "Publication" : "Preferences"))
        .join(", ");
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
    discardProfiles();
    discardPublication();
    discardPreferences();
  }, [
    applyProfile,
    applyPublicationProfile,
    beginNewProfile,
    deleteProfileNow,
    discardPreferences,
    discardProfiles,
    discardPublication,
    disconnectYoutubeNow,
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
