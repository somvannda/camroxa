import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Dialog, DialogContent } from "../../../components/dialog";
import { Button } from "../../../components/button";
import { Card } from "../../../components/card";
import { PageHeader } from "../../../components/page-header";
import { Badge } from "../../../components/status";
import { toast } from "../../../components/toast";
import { apiRequest, errorMessage } from "../../../lib/api";
import { AutomationCard } from "../components/automation-card";
import { ChannelPairCard } from "../components/channel-pair-card";
import { MusicErrorBanner } from "../components/music-error-banner";
import { MusicHistoryCard } from "../components/music-history-card";
import { MusicSettingsStrip } from "../components/music-settings-strip";
import { SongEditorCard } from "../components/song-editor-card";
import {
  costByType,
  formatButtonCredits,
  formatCredits,
  formatCreditLine,
  operationUnitCost,
  planCostBreakdown,
} from "../music-costs";
import {
  batchStatusText,
  buildDraftDescription,
  buildHistoryAvoidLists,
  buildReservationToken,
  createBatchesSummary,
  effectPreview,
  flattenHistory,
  historySummary,
  inclusiveDateList,
  inclusiveDaySpan,
  isTerminalBatchStatus,
  planManualRunDirectories,
  sanitizeSelection,
  toggleSelection,
  validatePairs,
  type HistoryRow,
} from "../music-format";
import {
  buildMusicSettings,
  DEFAULT_MUSIC_SETTINGS,
  imageSourceMode,
  manualOutputBase,
  type MusicSettings,
} from "../music-settings";
import type {
  BatchCreatePayload,
  BatchCreateResponse,
  BatchStatusResponse,
  ClaimPoolResponse,
  ClaimedPoolItem,
  ComposerState,
  DraftResponse,
  DraftSeeds,
  HistoryFilters,
  MusicHistoryResponse,
  PolishResponse,
  PromptOption,
} from "../music-types";
import { fetchMusicHistory, MUSIC_LOAD_ERROR_COPY, useMusicWorkspace } from "../use-music-workspace";
import { useMusicSettingsAutosave } from "../use-settings-autosave";
import { todayYmd } from "../music-format";

function blankComposer(): ComposerState {
  const today = todayYmd();
  return {
    fromDate: today,
    toDate: today,
    primaryIds: [],
    secondaryIds: [],
    title: "",
    album: "",
    lyrics: "",
  };
}

function pickPromptId(
  current: string,
  preferred: string,
  options: PromptOption[],
): string {
  if (current && options.some((option) => option.id === current)) return current;
  if (preferred && options.some((option) => option.id === preferred)) return preferred;
  return options[0]?.id ?? "";
}

function statusTone(status: string): "neutral" | "success" | "warning" | "danger" {
  if (status === "completed") return "success";
  if (status === "failed") return "danger";
  if (status === "partial") return "warning";
  return "neutral";
}

async function writeClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // fall through to the selection-based fallback
  }
  try {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const copied = document.execCommand("copy");
    document.body.removeChild(area);
    return copied;
  } catch {
    return false;
  }
}

export function MusicPage() {
  const query = useMusicWorkspace();
  const data = query.data;

  const [settings, setSettings] = useState<MusicSettings>(DEFAULT_MUSIC_SETTINGS);
  const [settingsReady, setSettingsReady] = useState(false);
  const [composer, setComposer] = useState<ComposerState>(blankComposer);
  const [descriptions, setDescriptions] = useState<PromptOption[]>([]);
  const [structures, setStructures] = useState<PromptOption[]>([]);
  const [descriptionId, setDescriptionId] = useState("");
  const [structureId, setStructureId] = useState("");
  const promptTouched = useRef(false);

  const [history, setHistory] = useState<MusicHistoryResponse>({ batches: [], summary: "", updated_at: "" });
  const [historyFilters, setHistoryFilters] = useState<HistoryFilters>({
    fromDate: "",
    toDate: "",
    lastBatchOnly: false,
  });
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedRowKey, setSelectedRowKey] = useState<string | null>(null);

  const [drafting, setDrafting] = useState(false);
  const [polishing, setPolishing] = useState(false);
  const [seedNotice, setSeedNotice] = useState("");
  const [undoLyrics, setUndoLyrics] = useState<string | null>(null);

  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batchSummary, setBatchSummary] = useState("");
  const [batchStatus, setBatchStatus] = useState("");
  const [batchStatusTone, setBatchStatusTone] = useState<"neutral" | "success" | "warning" | "danger">("neutral");
  const [confirmOpen, setConfirmOpen] = useState(false);

  const saveStatus = useMusicSettingsAutosave(settings, settingsReady);

  useEffect(() => {
    if (!data) return;
    if (!settingsReady) {
      setSettings(buildMusicSettings(data.settings));
      setSettingsReady(true);
    }
    setHistory(data.history);
    const mergeOptions = (current: PromptOption[], next: PromptOption[]) => {
      if (next.length === 0) return current;
      const merged = new Map(next.map((option) => [option.id, option]));
      for (const option of current) {
        if (!merged.has(option.id)) merged.set(option.id, option);
      }
      return [...merged.values()];
    };
    setDescriptions((current) => mergeOptions(current, data.descriptions));
    setStructures((current) => mergeOptions(current, data.structures));
    if (!promptTouched.current) {
      setDescriptionId((current) =>
        pickPromptId(
          current,
          String(data.settings.defaultDescriptionId ?? ""),
          data.descriptions,
        ),
      );
      setStructureId((current) =>
        pickPromptId(current, String(data.settings.defaultStructureId ?? ""), data.structures),
      );
    }
    setComposer((current) => {
      const primaryFallback = data.profiles.length > 0 ? [data.profiles[0].id] : [];
      // Pairing needs two distinct channels; never default both sides to the
      // same profile (the lists hide each other's selection).
      const secondaryFallback = data.profiles.length > 1 ? [data.profiles[1].id] : [];
      const persisted = buildMusicSettings(data.settings);
      const primaryIds = sanitizeSelection(
        current.primaryIds.length > 0 ? current.primaryIds : persisted.primaryProfileIds,
        data.profiles,
        primaryFallback,
      );
      const secondaryIds = sanitizeSelection(
        current.secondaryIds.length > 0 ? current.secondaryIds : persisted.secondaryProfileIds,
        data.profiles,
        secondaryFallback,
      ).filter((id) => !primaryIds.includes(id));
      return { ...current, primaryIds, secondaryIds };
    });
  }, [data, settingsReady]);

  // Keep the saved pairing in /settings in step with the visible selection, so
  // the next app launch opens the same Primary/Secondary channels.
  useEffect(() => {
    if (!settingsReady) return;
    setSettings((current) => {
      const samePrimary =
        current.primaryProfileIds.join("\u0000") === composer.primaryIds.join("\u0000");
      const sameSecondary =
        current.secondaryProfileIds.join("\u0000") === composer.secondaryIds.join("\u0000");
      if (samePrimary && sameSecondary) return current;
      return {
        ...current,
        primaryProfileIds: composer.primaryIds,
        secondaryProfileIds: composer.secondaryIds,
      };
    });
  }, [composer.primaryIds, composer.secondaryIds, settingsReady]);

  const primaryProfiles = useMemo(
    () => (data?.profiles ?? []).filter((profile) => composer.primaryIds.includes(profile.id)),
    [composer.primaryIds, data?.profiles],
  );
  const secondaryProfiles = useMemo(
    () => (data?.profiles ?? []).filter((profile) => composer.secondaryIds.includes(profile.id)),
    [composer.secondaryIds, data?.profiles],
  );

  const dayCount = useMemo(
    () => inclusiveDaySpan(composer.fromDate, composer.toDate),
    [composer.fromDate, composer.toDate],
  );
  const invalidRange = dayCount === null;
  const pairs = useMemo(
    () => validatePairs(composer.primaryIds, composer.secondaryIds),
    [composer.primaryIds, composer.secondaryIds],
  );
  const costs = useMemo(() => costByType(data?.costs), [data?.costs]);
  const simpleMode = settings.simpleMode;
  const allProfiles = data?.profiles ?? [];
  const emptyChannelMessage =
    allProfiles.length === 0
      ? "No profiles available yet."
      : "Nothing left to pair. Add another channel profile in Settings.";
  const breakdown = useMemo(
    () =>
      planCostBreakdown({
        lyricCost: costs.get("lyric"),
        musicCost: costs.get("music"),
        imageCost: costs.get("background_image"),
        titleCost: costs.get("title"),
        albumCost: costs.get("album"),
        videoCost: costs.get("video"),
        mergeCost: costs.get("video_merge"),
        publishCost: costs.get("publish"),
        primary: primaryProfiles,
        secondary: secondaryProfiles,
        songCount: settings.songCount,
        autoGenImage: settings.autoGenImage,
        autoGSuno: settings.autoGSuno,
        autoVideo: settings.autoVideoAfterSuno,
        autoMerge: settings.autoMergeAfterVideo,
        autoReel: settings.autoReelAfterVideo,
        autoUpload: false,
        dayCount,
        imageSourceMode: imageSourceMode(data?.settings),
        simpleMode,
      }),
    [costs, data?.settings, dayCount, primaryProfiles, secondaryProfiles, settings, simpleMode],
  );

  const descriptionName = descriptions.find((option) => option.id === descriptionId)?.name ?? "";
  const structureName = structures.find((option) => option.id === structureId)?.name ?? "";
  const effects = useMemo(() => effectPreview(settings.creativity), [settings.creativity]);
  const historyRows = useMemo(
    () => flattenHistory(history.batches, historyFilters),
    [history.batches, historyFilters],
  );
  const historyLabel = useMemo(
    () => historySummary(history.batches, historyRows, history.summary),
    [history.batches, history.summary, historyRows],
  );

  const historyLimit = Math.max(8, Math.min(100, settings.historyWindow));
  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      setHistory(await fetchMusicHistory(historyLimit));
    } catch {
      // Keep the last loaded rows; the poll/refresh path must not blank history.
    } finally {
      setHistoryLoading(false);
    }
  }, [historyLimit]);

  useEffect(() => {
    if (!batchId) return;
    let cancelled = false;
    let timer: number | null = null;

    const ensureDirs = async (dirs: Array<string | null | undefined>) => {
      for (const dir of dirs) {
        if (!dir) continue;
        await window.camxora.files.ensureDir(dir).catch(() => undefined);
      }
    };

    const poll = async () => {
      try {
        const status = await apiRequest<BatchStatusResponse>({
          method: "GET",
          path: `/batches/${batchId}`,
        });
        if (cancelled) return;
        setBatchStatus(batchStatusText(status));
        setBatchStatusTone(statusTone(status.status));
        await ensureDirs([status.ok_run_dir, status.alt_run_dir]);
        if (isTerminalBatchStatus(status.status)) {
          setBatchId(null);
          void refreshHistory();
        }
      } catch {
        // A poll error keeps the last status (MU-89).
      }
    };

    void poll();
    timer = window.setInterval(() => void poll(), 2500);
    return () => {
      cancelled = true;
      if (timer !== null) window.clearInterval(timer);
    };
  }, [batchId, refreshHistory]);

  const updateSettings = (patch: Partial<MusicSettings>) => {
    setSettings((current) => ({ ...current, ...patch }));
  };

  const updateComposer = (patch: Partial<ComposerState>) => {
    setComposer((current) => ({ ...current, ...patch }));
  };

  const toggleProfile = (side: "primary" | "secondary", profileId: string) => {
    setComposer((current) => {
      if (side === "primary") {
        const primaryIds = toggleSelection(current.primaryIds, profileId);
        // A channel can only be paired once, so selecting it on one side
        // removes it from the other side instead of leaving a stale duplicate.
        return {
          ...current,
          primaryIds,
          secondaryIds: primaryIds.includes(profileId)
            ? current.secondaryIds.filter((id) => id !== profileId)
            : current.secondaryIds,
        };
      }
      const secondaryIds = toggleSelection(current.secondaryIds, profileId);
      return {
        ...current,
        secondaryIds,
        primaryIds: secondaryIds.includes(profileId)
          ? current.primaryIds.filter((id) => id !== profileId)
          : current.primaryIds,
      };
    });
  };

  const chooseDescription = (id: string) => {
    promptTouched.current = true;
    setDescriptionId(id);
  };

  const chooseStructure = (id: string) => {
    promptTouched.current = true;
    setStructureId(id);
  };

  const copyComposer = async (kind: "title" | "lyrics" | "both") => {
    const text =
      kind === "title"
        ? composer.title
        : kind === "lyrics"
          ? composer.lyrics
          : [composer.title, composer.lyrics].filter((part) => part.trim()).join("\n\n");
    if (!text.trim()) return;
    const copied = await writeClipboard(text);
    if (!copied) {
      toast("Unable to copy to the clipboard.", "danger");
      return;
    }
    toast(
      kind === "title" ? "Title copied." : kind === "lyrics" ? "Lyrics copied." : "Title and lyrics copied.",
      "success",
    );
  };

  const claimPoolItem = async (
    kind: "titles" | "albums" | "openings",
    token: string,
  ): Promise<ClaimedPoolItem> => {
    const response = await apiRequest<ClaimPoolResponse>({
      method: "POST",
      path: `/content-pools/${kind}/claim`,
      body: { reservation_token: token, consumer: "music-draft", limit: 1, ttl_seconds: 900 },
    });
    return response.item;
  };

  const draft = async () => {
    if (drafting) return;
    if (!descriptionName.trim()) {
      setError("Choose a song description before drafting.");
      return;
    }
    setDrafting(true);
    setError("");
    const token = buildReservationToken();
    const claimed: Array<{ kind: "titles" | "albums" | "openings"; item: ClaimedPoolItem }> = [];
    try {
      let seeds: DraftSeeds | null = null;
      if (settings.useContentPools) {
        const title = await claimPoolItem("titles", token);
        claimed.push({ kind: "titles", item: title });
        const album = await claimPoolItem("albums", token);
        claimed.push({ kind: "albums", item: album });
        let opening: ClaimedPoolItem | null = null;
        if (settings.uniqueOpening) {
          opening = await claimPoolItem("openings", token);
          claimed.push({ kind: "openings", item: opening });
        }
        seeds = {
          titleSeed: title.text,
          albumSeed: album.text,
          openingSeed: opening
            ? [opening.text, opening.secondary_text ?? ""].filter(Boolean).join("\n")
            : null,
        };
      }

      const avoid = buildHistoryAvoidLists(history.batches, settings.historyWindow);
      const draftResponse = await apiRequest<DraftResponse>({
        method: "POST",
        path: "/generation/draft",
        body: {
          language: settings.language,
          secondary_language: settings.secondaryLanguage || null,
          creativity_level: settings.creativity,
          description: buildDraftDescription(descriptionName, seeds),
          structure: structureName,
          description_id: descriptionId || null,
          structure_id: structureId || null,
          mood_id: null,
          structure_mode: "template",
          avoid_titles: avoid.titles,
          avoid_albums: avoid.albums,
          avoid_openings: avoid.openings,
          title_seed: seeds?.titleSeed ?? null,
          album_seed: seeds?.albumSeed ?? null,
          forced_opening: seeds?.openingSeed ?? null,
          channel_profile_id: primaryProfiles[0]?.id ?? null,
        },
      });

      await Promise.allSettled(
        claimed.map(({ kind, item }) =>
          apiRequest({
            method: "POST",
            path: `/content-pools/${kind}/finalize`,
            body: { item_id: item.id, reservation_token: item.reservation_token },
          }),
        ),
      );

      setComposer((current) => ({
        ...current,
        title: draftResponse.title,
        album: draftResponse.album,
        lyrics: draftResponse.lyrics,
      }));
      setUndoLyrics(null);
      if (seeds) {
        const openingLine = seeds.openingSeed?.split("\n")[0] ?? "";
        setSeedNotice(
          `Draft seeded from pools and polished into a new result: title "${seeds.titleSeed}", album "${seeds.albumSeed}"` +
            (openingLine ? `, opening "${openingLine}"` : "") +
            ". The generated draft keeps these as inspiration, not as raw copy.",
        );
      } else {
        setSeedNotice("");
      }
      toast(`Draft ready: "${draftResponse.title}"`, "success");
    } catch (cause) {
      await Promise.allSettled(
        claimed.map(({ kind, item }) =>
          apiRequest({
            method: "POST",
            path: `/content-pools/${kind}/release`,
            body: { item_id: item.id, reservation_token: item.reservation_token },
          }),
        ),
      );
      setError(errorMessage(cause) || "Unable to generate a draft.");
    } finally {
      setDrafting(false);
    }
  };

  const polish = async () => {
    if (polishing) return;
    const lyrics = composer.lyrics.trim();
    if (!lyrics) return;
    const primary = primaryProfiles[0];
    if (!primary) {
      setError("Select at least one primary channel before polishing lyrics.");
      return;
    }
    setPolishing(true);
    setError("");
    try {
      const response = await apiRequest<PolishResponse>({
        method: "POST",
        path: "/generation/polish-lyrics",
        body: {
          lyrics,
          strength: settings.polishStrength,
          channel_profile_id: primary.id,
          structure_id: structureId || null,
          mood_id: null,
          title: composer.title.trim() || null,
          album: composer.album.trim() || null,
        },
      });
      setUndoLyrics(composer.lyrics);
      setComposer((current) => ({ ...current, lyrics: response.lyrics }));
      toast("Lyrics rewritten.", "success");
    } catch (cause) {
      setError(errorMessage(cause) || "Unable to rewrite the lyrics.");
    } finally {
      setPolishing(false);
    }
  };

  const undoPolish = () => {
    if (undoLyrics === null) return;
    setComposer((current) => ({ ...current, lyrics: undoLyrics }));
    setUndoLyrics(null);
    toast("Previous lyrics restored.", "info");
  };

  const selectHistoryRow = (row: HistoryRow) => {
    setSelectedRowKey(row.key);
    setSeedNotice("");
    setUndoLyrics(null);
    if (row.song.description_id) {
      const id = row.song.description_id;
      if (!descriptions.some((option) => option.id === id)) {
        setDescriptions((current) => [
          ...current,
          { id, name: row.song.description_name || "History description" },
        ]);
      }
      promptTouched.current = true;
      setDescriptionId(id);
    }
    if (row.song.structure_id) {
      const id = row.song.structure_id;
      if (!structures.some((option) => option.id === id)) {
        setStructures((current) => [
          ...current,
          { id, name: row.song.structure_name || "History structure" },
        ]);
      }
      promptTouched.current = true;
      setStructureId(id);
    }
    setComposer((current) => ({
      ...current,
      title: row.song.title || current.title,
      album: row.song.album || current.album,
      lyrics: row.song.lyrics || current.lyrics,
    }));
  };

  const openFolder = async (row: HistoryRow, side: "primary" | "secondary") => {
    const path =
      (side === "primary" ? row.song.output_dir_ok : row.song.output_dir_alt)?.trim() ?? "";
    if (!path) {
      setError("This row has no folder path yet. Run the batch first.");
      return;
    }
    const ensured = await window.camxora.files.ensureDir(path);
    if (!ensured.ok) {
      setError(ensured.error.message || "Unable to create the run folder.");
      return;
    }
    const opened = await window.camxora.files.open(path);
    if (!opened.ok) {
      setError(opened.error.message || "Unable to open the run folder.");
    }
  };

  const batchSlots = () => {
    const days = inclusiveDateList(composer.fromDate, composer.toDate);
    const manualMode = imageSourceMode(data?.settings) === "manual";
    const baseDir = manualOutputBase(data?.settings);
    const slots: Array<{
      date: string;
      okName: string;
      altName: string;
      payload: BatchCreatePayload;
      okRunDir: string;
      altRunDir: string;
    }> = [];

    for (const date of days) {
      primaryProfiles.forEach((okProfile, index) => {
        const altProfile = secondaryProfiles[index];
        if (!altProfile) return;
        const planned =
          manualMode && baseDir
            ? planManualRunDirectories({
                baseDir,
                okProfileFolder: okProfile.folder_name || okProfile.name,
                altProfileFolder: altProfile.folder_name || altProfile.name,
                runLabel: date,
              })
            : { okRunDir: "", altRunDir: "", runFolderName: "" };
        slots.push({
          date,
          okName: okProfile.name,
          altName: altProfile.name,
          okRunDir: planned.okRunDir,
          altRunDir: planned.altRunDir,
          payload: {
            ok_profile_id: okProfile.id,
            alt_profile_id: altProfile.id,
            description_id: descriptionId || null,
            // Simple mode: Suno picks the section layout, and only the
            // description + song count shape the request.
            structure_id: simpleMode ? null : structureId || null,
            mood_id: null,
            structure_mode: simpleMode ? "suno" : "template",
            shuffle_structure: simpleMode ? false : settings.shuffleStructure,
            shuffle_mood: simpleMode ? false : settings.shuffleMood,
            auto_gen_image: settings.autoGenImage,
            auto_gsuno: settings.autoGSuno,
            auto_video_after_suno: settings.autoVideoAfterSuno,
            auto_merge_after_video: settings.autoMergeAfterVideo,
            auto_reel_after_video: settings.autoReelAfterVideo,
            auto_upload_youtube: false,
            song_count: settings.songCount,
            language: simpleMode ? DEFAULT_MUSIC_SETTINGS.language : settings.language,
            secondary_language: simpleMode ? null : settings.secondaryLanguage || null,
            creativity_level: simpleMode
              ? DEFAULT_MUSIC_SETTINGS.creativity
              : settings.creativity,
            pairing_mode: "match_key",
            from_date: date,
            to_date: date,
            ok_run_dir: planned.okRunDir || null,
            alt_run_dir: planned.altRunDir || null,
          },
        });
      });
    }
    return { slots, days: days.length, pairs: primaryProfiles.length };
  };

  const ensureRunDirs = async (dirs: Array<string | null | undefined>) => {
    for (const dir of dirs) {
      if (!dir) continue;
      const result = await window.camxora.files.ensureDir(dir);
      if (!result.ok) {
        toast(`Unable to create ${dir}. ${result.error.message}`, "warning");
      }
    }
  };

  const runGenerate = async () => {
    setConfirmOpen(false);
    if (generating) return;
    setGenerating(true);
    setError("");
    const { slots, days, pairs: pairCount } = batchSlots();
    const outcome = {
      planned: slots.length,
      dayCount: days,
      pairCount,
      created: [] as Array<{ date: string; okName: string; altName: string }>,
      failed: [] as Array<{ date: string; okName: string; altName: string; message: string }>,
    };
    let lastBatchId = "";

    for (const slot of slots) {
      try {
        const response = await apiRequest<BatchCreateResponse>({
          method: "POST",
          path: "/batches",
          body: slot.payload,
        });
        lastBatchId = response.batch_id;
        outcome.created.push({ date: slot.date, okName: slot.okName, altName: slot.altName });
        await ensureRunDirs([
          response.ok_run_dir || slot.okRunDir,
          response.alt_run_dir || slot.altRunDir,
        ]);
      } catch (cause) {
        outcome.failed.push({
          date: slot.date,
          okName: slot.okName,
          altName: slot.altName,
          message: errorMessage(cause),
        });
      }
    }

    const summary = createBatchesSummary(outcome);
    setBatchSummary(summary);
    if (lastBatchId) {
      setBatchId(lastBatchId);
      setBatchStatus("Batch queued. Watching progress.");
      setBatchStatusTone("neutral");
    }
    if (outcome.created.length === 0) {
      setError(summary);
    } else if (outcome.failed.length > 0) {
      toast(summary, "warning", 8000);
    } else {
      toast(summary, "success");
    }
    setGenerating(false);
    await refreshHistory();
    void query.refetch();
  };

  const requestGenerate = () => {
    const { days, pairs: pairCount } = batchSlots();
    if (days > 1 || pairCount > 2) {
      setConfirmOpen(true);
      return;
    }
    void runGenerate();
  };

  const lyricUnit = operationUnitCost(costs.get("lyric"));
  const draftLabel = formatButtonCredits("Draft", lyricUnit);
  const polishLabel = formatButtonCredits("Polish", lyricUnit);
  const generateLabel = formatButtonCredits("Generate", breakdown?.total ?? null);
  const unitCostLabels = [
    formatCreditLine("Draft", lyricUnit),
    formatCreditLine("Polish", lyricUnit),
    "Revisions: 0 credits",
    formatCreditLine("Suno", operationUnitCost(costs.get("music"))),
    formatCreditLine("Image", operationUnitCost(costs.get("background_image"))),
    formatCreditLine("Video", operationUnitCost(costs.get("video"))),
    formatCreditLine("Merge", operationUnitCost(costs.get("video_merge"))),
    formatCreditLine("Upload", operationUnitCost(costs.get("publish"))),
  ];

  const warnings: string[] = [];
  if (pairs.mismatch) warnings.push("Primary and Secondary channel counts must match.");
  if (pairs.overlap) warnings.push("Choose different channels for each side.");
  if (descriptions.length === 0) {
    warnings.push("No song descriptions are available. Add one in Settings.");
  } else if (!descriptionId) {
    warnings.push("Choose a song description before generating.");
  }
  if (!simpleMode && structures.length === 0) {
    warnings.push("No song structures are available. Add one in Settings.");
  }

  const canGenerate =
    !generating &&
    !invalidRange &&
    pairs.canPair &&
    descriptions.length > 0 &&
    Boolean(descriptionId) &&
    (simpleMode || structures.length > 0);

  const stale = query.isError && Boolean(data);

  if (query.isLoading) {
    return (
      <div className="pb-6">
        <PageHeader
          eyebrow="Workspace"
          title="Music"
          description="Compose songs, pair channels, generate batches and review history."
        />
        <div className="p-6">
          <Card className="p-5" data-testid="music-loading">
            <p className="text-body text-text-secondary">Loading music workspace...</p>
          </Card>
        </div>
      </div>
    );
  }

  if (query.isError && !data) {
    return (
      <div className="pb-6">
        <PageHeader
          eyebrow="Workspace"
          title="Music"
          description="Compose songs, pair channels, generate batches and review history."
        />
        <div className="space-y-4 p-6">
          <MusicErrorBanner message={MUSIC_LOAD_ERROR_COPY} />
          <Card className="p-5">
            <p className="text-body text-text-secondary">{errorMessage(query.error)}</p>
            <Button className="mt-3" onClick={() => void query.refetch()}>
              Retry
            </Button>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="pb-6" data-testid="music-page">
      <PageHeader
        eyebrow="Workspace"
        title="Music"
        description="Compose songs, pair channels, generate batches and review history."
        actions={stale ? <Badge tone="warning">Stale</Badge> : undefined}
      />
      <div className="space-y-4 p-6">
        {error ? <MusicErrorBanner message={error} onDismiss={() => setError("")} /> : null}

        <MusicSettingsStrip
              settings={settings}
              fromDate={composer.fromDate}
              toDate={composer.toDate}
              onFromDate={(value) => updateComposer({ fromDate: value })}
              onToDate={(value) => updateComposer({ toDate: value })}
              onSettingsChange={updateSettings}
            />

            <div
              className={
                simpleMode
                  ? "grid items-start gap-4 xl:grid-cols-[0.7fr_0.7fr_1.2fr]"
                  : "grid items-start gap-4 xl:grid-cols-[1.5fr_0.75fr_0.75fr_0.95fr]"
              }
            >
          {simpleMode ? null : (
          <SongEditorCard
            composer={composer}
            settings={settings}
            effects={effects}
            draftLabel={draftLabel}
            polishLabel={polishLabel}
            drafting={drafting}
            polishing={polishing}
            draftEnabled={Boolean(descriptionName.trim()) && !invalidRange && !drafting}
            polishEnabled={composer.lyrics.trim().length > 0 && primaryProfiles.length > 0}
            seedNotice={seedNotice}
            undoAvailable={undoLyrics !== null}
            onDraft={() => void draft()}
            onPolish={() => void polish()}
            onUndo={undoPolish}
            onFieldChange={updateComposer}
            onPolishStrength={(value) => updateSettings({ polishStrength: value })}
            onCopy={(kind) => void copyComposer(kind)}
          />
          )}

          <ChannelPairCard
            side="primary"
            title="Primary channels"
            profiles={allProfiles.filter(
              (profile) => !composer.secondaryIds.includes(profile.id),
            )}
            selectedIds={composer.primaryIds}
            onToggle={(id) => toggleProfile("primary", id)}
            locked={generating}
            testId="primary-channels"
            note="Channels already paired on the Secondary side are hidden here."
            emptyMessage={emptyChannelMessage}
          />
          <ChannelPairCard
            side="secondary"
            title="Secondary channels"
            profiles={allProfiles.filter(
              (profile) => !composer.primaryIds.includes(profile.id),
            )}
            selectedIds={composer.secondaryIds}
            onToggle={(id) => toggleProfile("secondary", id)}
            locked={generating}
            testId="secondary-channels"
            note="Channels already paired on the Primary side are hidden here."
            emptyMessage={emptyChannelMessage}
          />

          <AutomationCard
            descriptionId={descriptionId}
            structureId={structureId}
            descriptions={descriptions}
            structures={structures}
            onDescriptionChange={chooseDescription}
            onStructureChange={chooseStructure}
            toggles={{
              autoGenImage: settings.autoGenImage,
              autoGSuno: settings.autoGSuno,
              autoVideoAfterSuno: settings.autoVideoAfterSuno,
              autoMergeAfterVideo: settings.autoMergeAfterVideo,
              autoReelAfterVideo: settings.autoReelAfterVideo,
              autoUploadYouTube: settings.autoUploadYouTube,
            }}
            onToggle={(key, value) => updateSettings({ [key]: value })}
            saveStatus={saveStatus}
            unitCostLabels={unitCostLabels}
            breakdown={breakdown}
            warnings={warnings}
            batchSummary={batchSummary}
            batchStatus={batchStatus}
            batchStatusTone={batchStatusTone}
            generating={generating}
            generateEnabled={canGenerate}
            generateLabel={generateLabel}
            onGenerate={requestGenerate}
            simple={simpleMode}
          />
        </div>

        <MusicHistoryCard
          rows={historyRows}
          summary={historyLabel}
          updatedAt={history.updated_at ?? ""}
          filters={historyFilters}
          loading={historyLoading}
          selectedKey={selectedRowKey}
          onFiltersChange={(patch) => setHistoryFilters((current) => ({ ...current, ...patch }))}
          onSelectRow={selectHistoryRow}
          onOpenFolder={(row, side) => void openFolder(row, side)}
        />
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent
          title="Generate this plan?"
          description={`${dayCount ?? 0} planned ${dayCount === 1 ? "day" : "days"} × ${
            primaryProfiles.length
          } ${primaryProfiles.length === 1 ? "channel pair" : "channel pairs"}.`}
        >
          <p className="text-body text-text-secondary">
            This creates one batch per planned day and channel pair, for{" "}
            <span className="text-text-primary text-tabular">
              {breakdown?.songJobs ?? 0} song jobs
            </span>
            {breakdown?.total !== null && breakdown?.total !== undefined ? (
              <>
                {" "}
                at{" "}
                <span className="text-text-primary text-tabular">
                  {formatCredits(breakdown.total)} credits
                </span>
              </>
            ) : null}
            .
          </p>
          <div className="mt-4 flex justify-end gap-2">
            <Button onClick={() => setConfirmOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={() => void runGenerate()}>
              Generate
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
