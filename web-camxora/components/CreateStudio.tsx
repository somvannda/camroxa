"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import { TrackRail } from "@/components/TrackRail";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/components/AuthProvider";
import { usePlayer } from "@/components/PlayerProvider";
import { cn } from "@/lib/utils";
import type { WebMusicClip, WebMusicGeneration } from "@/lib/library-api";
import {
  WebMusicApiError,
  addWebMusicPlaylistItem,
  clipFilename,
  coverWebMusicStudioUpload,
  createWebMusicPlaylist,
  createWebMusicWorkspace,
  deleteWebMusicGeneration,
  extendWebMusicStudioUpload,
  fetchWebMusicClipBlob,
  fetchWebMusicClipWavBlob,
  fetchWebMusicLikedKeys,
  fetchWebMusicQuota,
  fetchWebMusicTimedLyricsBlob,
  getWebMusicStudioOperation,
  uploadWebMusicStudioAudio,
  type WebMusicStudioUpload,
  generateWebMusic,
  generateWebMusicDraft,
  generateWebMusicStyles,
  getWebMusicGeneration,
  listWebMusicGenerations,
  listWebMusicWorkspaces,
  likeWebMusicGeneration,
  saveBlob,
  unlockWebMusicPreview,
  updateWebMusicGenerationTitle,
  updateWebMusicWorkspace,
  type WebMusicGenerateInput,
  type WebMusicModel,
  type WebMusicPlaylistSummary,
  type WebMusicQuota,
  type WebMusicWorkspace,
} from "@/lib/web-music-api";
import { createStoreZip, type ZipEntry } from "@/lib/zip-store";
import {
  clipDownloadUrl,
  clipIsReady,
  clipTrackKey,
  clipVersionLabel,
  formatClipDuration,
  formatDate,
  generationClips,
  generationIsInstrumental,
  statusClass,
  statusLabel,
} from "@/lib/clip-utils";

type Mode = "simple" | "custom";
type LyricsMode = "write" | "prompt";

const models: Array<{ value: WebMusicModel; label: string }> = [
  { value: "V6", label: "V6 Pro" },
  { value: "V6_MINI", label: "V6 Mini" },
  { value: "V6_WILD", label: "V6 Wild" },
];

const SIMPLE_SONG_COUNTS = [1, 5, 10, 20] as const;
const BATCH_SUBMIT_GAP_MS = 900;
const DOWNLOAD_FORMATS: Array<{ value: DownloadKind; label: string }> = [
  { value: "mp3", label: "MP3" },
  { value: "wav", label: "WAV" },
  { value: "lrc", label: "LRC" },
  { value: "srt", label: "SRT" },
];

const styleChips = [
  "pop",
  "rock",
  "hip hop",
  "electronic",
  "khmer",
  "acoustic",
  "synthwave",
  "rnb",
  "jazz",
  "ambient",
  "dance",
  "cinematic",
];

type FeatureTab = "audio" | "voice" | "inspo" | null;
type DownloadKind = "lrc" | "srt" | "mp3" | "wav";
type FeedSort = "new" | "old" | "most" | "least";
type FeedFilter =
  | "liked"
  | "disliked"
  | "public"
  | "private"
  | "uploads"
  | "full"
  | "cover"
  | "voice"
  | "downloads"
  | "hideDisliked"
  | "hideStems";

function SelectBox({
  value,
  onChange,
  options,
  ariaLabel,
  className = "",
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  ariaLabel: string;
  className?: string;
  disabled?: boolean;
}) {
  return (
    <Select value={value} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger
        aria-label={ariaLabel}
        className={cn("select-box", className)}
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent className="create-select-content">
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function CreateStudio() {
  const { user, credits, loading, refresh } = useAuth();
  const { playTrack } = usePlayer();
  const [mode, setMode] = useState<Mode>("simple");
  const [prompt, setPrompt] = useState("");
  const [title, setTitle] = useState("");
  const [style, setStyle] = useState("");
  const [lyrics, setLyrics] = useState("");
  const [lyricsMode, setLyricsMode] = useState<LyricsMode>("write");
  const [instrumental, setInstrumental] = useState(false);
  const [model, setModel] = useState<WebMusicModel>("V6");
  const [vocalGender, setVocalGender] = useState<"f" | "m" | "both">("f");
  const [negativeTags, setNegativeTags] = useState("");
  const [styleWeight, setStyleWeight] = useState(0.5);
  const [weirdness, setWeirdness] = useState(0.5);
  const [audioWeight, setAudioWeight] = useState(0.5);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [stylesOpen, setStylesOpen] = useState(true);
  const [lyricsOpen, setLyricsOpen] = useState(true);
  const [featureTab, setFeatureTab] = useState<FeatureTab>(null);
  const [songs, setSongs] = useState<WebMusicGeneration[]>([]);
  const [loadingSongs, setLoadingSongs] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<WebMusicGeneration | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [writingLyrics, setWritingLyrics] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [quota, setQuota] = useState<WebMusicQuota | null>(null);
  const [workspaces, setWorkspaces] = useState<WebMusicWorkspace[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null);
  const [workspacesReady, setWorkspacesReady] = useState(false);
  const [workspaceBusy, setWorkspaceBusy] = useState(false);
  const [newWorkspaceOpen, setNewWorkspaceOpen] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState("");
  const [renameWorkspaceOpen, setRenameWorkspaceOpen] = useState(false);
  const [renameWorkspaceName, setRenameWorkspaceName] = useState("");
  const [playlists, setPlaylists] = useState<WebMusicPlaylistSummary[]>([]);
  const [totalSongs, setTotalSongs] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [simpleSongCount, setSimpleSongCount] = useState<number>(1);
  const [batchProgress, setBatchProgress] = useState<{ done: number; total: number } | null>(null);
  const [generatingStyles, setGeneratingStyles] = useState(false);
  const [stylesError, setStylesError] = useState("");
  const [selectedVariant, setSelectedVariant] = useState<string | null>(null);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedClipKeys, setSelectedClipKeys] = useState<string[]>([]);
  const [batchFormat, setBatchFormat] = useState<DownloadKind>("mp3");
  const [batchDownloadProgress, setBatchDownloadProgress] = useState<{ done: number; total: number } | null>(null);
  const [batchBusy, setBatchBusy] = useState(false);
  const [batchError, setBatchError] = useState("");
  const [cooldownSeconds, setCooldownSeconds] = useState(0);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const mounted = useRef(true);
  const cardBodyRef = useRef<HTMLDivElement | null>(null);

  const [createTab, setCreateTab] = useState<"songs" | "speech" | "sounds">("songs");
  const [feedSearch, setFeedSearch] = useState("");
  const [feedSort, setFeedSort] = useState<FeedSort>("new");
  const [feedFilters, setFeedFilters] = useState<FeedFilter[]>([]);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [sortOpen, setSortOpen] = useState(false);
  const [viewMode, setViewMode] = useState<"list" | "grid">("list");
  const [shareOpen, setShareOpen] = useState(false);
  const [workspaceMenuOpen, setWorkspaceMenuOpen] = useState(false);
  const [saveMenuOpen, setSaveMenuOpen] = useState(false);
  const [rowMenuKey, setRowMenuKey] = useState<string | null>(null);
  const [likedKeys, setLikedKeys] = useState<string[]>([]);
  const [dislikedKeys, setDislikedKeys] = useState<string[]>([]);
  const [toast, setToast] = useState("");
  const [feedPage, setFeedPage] = useState(1);
  const [attachModal, setAttachModal] = useState<null | "audio" | "voice" | "image" | "inspo" | "video" | "playlist" | "voices">(null);
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const [addSubmenu, setAddSubmenu] = useState<null | "lyrics" | "styles" | "audio" | "voice">(null);
  const [audioUpload, setAudioUpload] = useState<WebMusicStudioUpload | null>(null);
  const [audioUploading, setAudioUploading] = useState(false);
  const [audioBusy, setAudioBusy] = useState(false);
  const [audioError, setAudioError] = useState("");
  const [recording, setRecording] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recordChunks = useRef<Blob[]>([]);
  const [modelOpen, setModelOpen] = useState(false);
  const [creditsOpen, setCreditsOpen] = useState(false);
  const [stylePresetsOpen, setStylePresetsOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [durationMode, setDurationMode] = useState<"custom" | "auto">("auto");
  const [maxMode, setMaxMode] = useState(false);

  useEffect(() => {
    if (!user) return;
    let active = true;
    fetchWebMusicLikedKeys()
      .then((keys) => {
        if (active) setLikedKeys(keys);
      })
      .catch(() => null);
    return () => {
      active = false;
    };
  }, [user]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    setFeedPage(1);
  }, [feedSearch, feedSort, feedFilters, activeWorkspaceId]);

  useEffect(() => {
    const onDoc = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (!target.closest("[data-s-menu]")) {
        setFiltersOpen(false);
        setSortOpen(false);
        setModelOpen(false);
        setCreditsOpen(false);
        setShareOpen(false);
        setWorkspaceMenuOpen(false);
        setSaveMenuOpen(false);
        setRowMenuKey(null);
        setStylePresetsOpen(false);
        setAddMenuOpen(false);
        setAddSubmenu(null);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setFiltersOpen(false);
        setSortOpen(false);
        setModelOpen(false);
        setCreditsOpen(false);
        setShareOpen(false);
        setWorkspaceMenuOpen(false);
        setSaveMenuOpen(false);
        setRowMenuKey(null);
        setStylePresetsOpen(false);
        setAddMenuOpen(false);
        setAddSubmenu(null);
        setAttachModal(null);
      }
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    cardBodyRef.current?.scrollTo({ top: 0 });
  }, [mode]);

  useEffect(() => {
    if (cooldownSeconds <= 0) return;
    const timer = window.setTimeout(() => {
      setCooldownSeconds((current) => Math.max(0, current - 1));
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [cooldownSeconds]);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      window.location.href = "/login?next=/create";
      return;
    }
    let active = true;
    Promise.all([
      listWebMusicWorkspaces().catch(() => ({ items: [] as WebMusicWorkspace[] })),
      fetchWebMusicQuota().catch(() => null),
    ])
      .then(([workspacePayload, quotaPayload]) => {
        if (!active) return;
        setWorkspaces(workspacePayload.items);
        setQuota(quotaPayload);
        const defaultWorkspace =
          workspacePayload.items.find((workspace) => workspace.is_default) ??
          workspacePayload.items[0] ??
          null;
        setActiveWorkspaceId(defaultWorkspace?.id ?? null);
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Could not load your studio");
      })
      .finally(() => {
        if (active) setWorkspacesReady(true);
      });
    return () => {
      active = false;
    };
  }, [loading, user]);

  useEffect(() => {
    if (!workspacesReady || loading || !user) return;
    void reloadGenerations(activeWorkspaceId, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspacesReady, activeWorkspaceId, loading, user]);

  async function reloadGenerations(workspaceId: string | null, offset = 0) {
    if (offset === 0) setLoadingSongs(true);
    else setLoadingMore(true);
    try {
      const page = await listWebMusicGenerations(50, offset, workspaceId ?? undefined);
      if (!mounted.current) return;
      setSongs((current) => (offset === 0 ? page.items : [...current, ...page.items]));
      setTotalSongs(page.total);
      if (offset === 0) {
        const kept = selectedId ? page.items.find((item) => item.id === selectedId) : null;
        const next = kept ?? page.items[0] ?? null;
        if (next) {
          const variant =
            next.clips?.find((clip) => clip.variant === selectedVariant)?.variant ??
            next.clips?.[0]?.variant ??
            "ok";
          void loadDetail(next.id, variant);
        } else {
          setSelectedId(null);
          setSelectedDetail(null);
          setSelectedVariant(null);
        }
      }
    } catch (cause) {
      if (mounted.current) {
        setError(cause instanceof Error ? cause.message : "Could not load songs");
      }
    } finally {
      if (mounted.current) {
        setLoadingSongs(false);
        setLoadingMore(false);
      }
    }
  }

  async function loadDetail(id: string, variant?: string) {
    setSelectedId(id);
    if (variant) setSelectedVariant(variant);
    setDetailLoading(true);
    try {
      const detail = await getWebMusicGeneration(id);
      if (!mounted.current) return;
      setSelectedDetail(detail);
      const nextVariant =
        variant ??
        detail.clips?.find((clip) => clip.variant === selectedVariant)?.variant ??
        detail.clips?.[0]?.variant ??
        "ok";
      setSelectedVariant(nextVariant);
      setSongs((current) => current.map((item) => (item.id === detail.id ? detail : item)));
    } catch {
      if (mounted.current) setSelectedDetail(songs.find((item) => item.id === id) ?? null);
    } finally {
      if (mounted.current) setDetailLoading(false);
    }
  }

  async function selectSong(id: string, variant?: string) {
    await loadDetail(id, variant);
  }

  async function refreshSongs() {
    try {
      await reloadGenerations(activeWorkspaceId, 0);
      if (selectedId) {
        const detail = await getWebMusicGeneration(selectedId).catch(() => null);
        if (detail && mounted.current) setSelectedDetail(detail);
      }
      const nextQuota = await fetchWebMusicQuota().catch(() => null);
      if (nextQuota && mounted.current) setQuota(nextQuota);
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause.message : "Could not refresh songs");
    }
  }

  const hasPending = songs.some((song) =>
    ["pending", "queued", "running"].includes(String(song.status).toLowerCase())
  );

  useEffect(() => {
    if (!hasPending) return;
    const timer = window.setInterval(() => {
      void refreshSongs();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [hasPending, selectedId]);

  const formReady =
    mode === "simple"
      ? prompt.trim().length > 0
      : instrumental
        ? style.trim().length > 0
        : style.trim().length > 0 && lyrics.trim().length > 0;

  async function writeLyrics() {
    const seed =
      (mode === "custom" && lyricsMode === "prompt" ? lyrics.trim() : prompt.trim()) ||
      title.trim() ||
      style.trim();
    if (!seed) {
      setError("Add a song description, title, or style first.");
      return;
    }
    setWritingLyrics(true);
    setError("");
    try {
      const draft = await generateWebMusicDraft(seed);
      setLyrics(draft.lyrics);
      if (!title.trim() && draft.title) setTitle(draft.title);
      setLyricsMode("write");
      const nextQuota = await fetchWebMusicQuota().catch(() => null);
      if (nextQuota && mounted.current) setQuota(nextQuota);
      void refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not write lyrics");
    } finally {
      setWritingLyrics(false);
    }
  }

  function appendStyle(chip: string) {
    setStyle((current) =>
      current.toLowerCase().includes(chip)
        ? current
        : [current.trim(), chip].filter(Boolean).join(", ").slice(0, 1000)
    );
  }

  function shuffleStyle() {
    const picks = [...styleChips].sort(() => Math.random() - 0.5).slice(0, 3);
    setStyle(picks.join(", "));
  }

  async function probeAudioDuration(file: File): Promise<number | undefined> {
    return new Promise((resolve) => {
      const url = URL.createObjectURL(file);
      const audio = new Audio();
      audio.preload = "metadata";
      audio.onloadedmetadata = () => {
        const duration = Number.isFinite(audio.duration) ? audio.duration : undefined;
        URL.revokeObjectURL(url);
        resolve(duration);
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        resolve(undefined);
      };
      audio.src = url;
    });
  }

  async function uploadAudioFile(file: File) {
    setAudioUploading(true);
    setAudioError("");
    try {
      const duration = await probeAudioDuration(file);
      const upload = await uploadWebMusicStudioAudio(file, duration);
      if (!mounted.current) return;
      setAudioUpload(upload);
      setToast("Audio uploaded");
    } catch (cause) {
      if (mounted.current) {
        setAudioError(cause instanceof Error ? cause.message : "Could not upload the audio file");
      }
    } finally {
      if (mounted.current) setAudioUploading(false);
    }
  }

  async function toggleRecording() {
    if (recording) {
      recorderRef.current?.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      recordChunks.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) recordChunks.current.push(event.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        setRecording(false);
        const blob = new Blob(recordChunks.current, { type: recorder.mimeType || "audio/webm" });
        const file = new File([blob], `recording-${Date.now()}.webm`, { type: blob.type });
        void uploadAudioFile(file);
      };
      recorder.start();
      recorderRef.current = recorder;
      setAudioError("");
      setRecording(true);
    } catch {
      setAudioError("Microphone access was denied. Check your browser permission.");
    }
  }

  async function pollStudioOperation(id: string, attempt = 0) {
    if (!mounted.current) return;
    const operation = await getWebMusicStudioOperation(id).catch(() => null);
    if (!mounted.current) return;
    if (operation) {
      const status = operation.status.toLowerCase();
      if (status === "success" || status === "completed" || status === "done") {
        setToast("Audio is ready");
        void refreshSongs();
        void refresh();
        return;
      }
      if (status === "error" || status === "failed") {
        setError(operation.error_message || "The audio operation failed.");
        return;
      }
    }
    if (attempt >= 40) {
      setError("Audio is still processing. Check the feed in a minute.");
      return;
    }
    window.setTimeout(() => void pollStudioOperation(id, attempt + 1), 3000);
  }

  async function runAudioOperation(kind: "extend" | "cover") {
    if (!audioUpload || audioBusy) return;
    setAudioBusy(true);
    setAudioError("");
    const input = {
      prompt: prompt || style,
      title: title || audioUpload.filename,
      tags: style,
    };
    try {
      const operation =
        kind === "extend"
          ? await extendWebMusicStudioUpload(audioUpload.id, input)
          : await coverWebMusicStudioUpload(audioUpload.id, input);
      if (!mounted.current) return;
      setAttachModal(null);
      setToast(kind === "extend" ? "Extend queued" : "Cover queued");
      void pollStudioOperation(operation.id);
    } catch (cause) {
      if (mounted.current) {
        setAudioError(cause instanceof Error ? cause.message : "Could not start the audio operation");
      }
    } finally {
      if (mounted.current) setAudioBusy(false);
    }
  }

  async function pollGeneration(id: string, attempts = 0) {
    if (!mounted.current) return;
    try {
      const generation = await getWebMusicGeneration(id);
      if (!mounted.current) return;
      setSongs((current) =>
        current.map((item) => (item.id === generation.id ? generation : item))
      );
      if (selectedId === generation.id) setSelectedDetail(generation);
      const done =
        String(generation.status).toLowerCase() === "success" ||
        (generation.clips?.some((clip) => clip.ready) ?? false);
      if (!done && attempts < 80) {
        window.setTimeout(() => void pollGeneration(id, attempts + 1), 3000);
      } else if (done) {
        setNotice("Your song is ready.");
        void refreshSongs();
        void refresh();
      }
    } catch {
      if (attempts < 30) {
        window.setTimeout(() => void pollGeneration(id, attempts + 1), 3000);
      }
    }
  }

  function playSong(song: WebMusicGeneration, preferredClip?: WebMusicClip) {
    const clip =
      preferredClip ??
      song.clips?.find((item) => item.ready && item.audio_url) ??
      song.clips?.find((item) => item.audio_url) ??
      song.clips?.[0];
    const variant = clip?.variant || "ok";
    const audioUrl =
      clip?.audio_url ||
      (String(song.status).toLowerCase() === "success"
        ? clip?.download_url ||
          `/api/v3/web-music/generations/${song.id}/stream/${variant}`
        : "");
    if (!audioUrl) return;
    playTrack({
      title: clip?.title || song.title || "Untitled",
      artist: "You",
      cover: clip?.image_url || "/hero.png",
      duration: Math.max(1, Math.round(clip?.duration_seconds || 180)),
      audioUrl,
    });
  }

  async function suggestStyles() {
    const hasContext = Boolean(style.trim() || lyrics.trim() || title.trim() || prompt.trim());
    if (!hasContext) {
      setStylesError("Add a style, title, lyrics, or song description first.");
      return;
    }
    setGeneratingStyles(true);
    setStylesError("");
    try {
      const result = await generateWebMusicStyles({
        style: style.trim(),
        lyrics: lyrics.trim(),
        title: title.trim(),
        description: prompt.trim(),
      });
      setStyle(result.style);
      const nextQuota = await fetchWebMusicQuota().catch(() => null);
      if (nextQuota && mounted.current) setQuota(nextQuota);
      void refresh();
    } catch (cause) {
      setStylesError(cause instanceof Error ? cause.message : "Style generation failed");
    } finally {
      if (mounted.current) setGeneratingStyles(false);
    }
  }

  async function onCreateWorkspace() {
    const name = newWorkspaceName.trim();
    if (!name || workspaceBusy) return;
    setWorkspaceBusy(true);
    setError("");
    try {
      const created = await createWebMusicWorkspace(name);
      setWorkspaces((current) => [...current, created]);
      setNewWorkspaceName("");
      setNewWorkspaceOpen(false);
      setActiveWorkspaceId(created.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create workspace");
    } finally {
      if (mounted.current) setWorkspaceBusy(false);
    }
  }

  async function onRenameWorkspace() {
    if (!activeWorkspaceId || workspaceBusy) return;
    const name = renameWorkspaceName.trim();
    if (!name) return;
    setWorkspaceBusy(true);
    setError("");
    try {
      const updated = await updateWebMusicWorkspace(activeWorkspaceId, name);
      setWorkspaces((current) =>
        current.map((workspace) => (workspace.id === updated.id ? updated : workspace))
      );
      setRenameWorkspaceOpen(false);
      setRenameWorkspaceName("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not rename workspace");
    } finally {
      if (mounted.current) setWorkspaceBusy(false);
    }
  }

  async function loadMoreSongs() {
    if (loadingMore || songs.length >= totalSongs) return;
    await reloadGenerations(activeWorkspaceId, songs.length);
  }

  function toggleClipSelection(key: string) {
    setBatchError("");
    setSelectedClipKeys((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key]
    );
  }

  async function onBatchDownload() {
    if (!selectedClipKeys.length || batchBusy) return;
    const targets = songs
      .flatMap((song) =>
        generationClips(song).map((clip) => ({
          song,
          clip,
          key: clipTrackKey(song.id, clip.variant),
        }))
      )
      .filter(
        ({ song, clip, key }) =>
          selectedClipKeys.includes(key) &&
          clipIsReady(song, clip) &&
          !(generationIsInstrumental(song) && (batchFormat === "lrc" || batchFormat === "srt"))
      );
    if (!targets.length) {
      setBatchError("Select at least one ready track to download.");
      return;
    }
    setBatchBusy(true);
    setBatchError("");
    setBatchDownloadProgress({ done: 0, total: targets.length });
    try {
      const entries: ZipEntry[] = [];
      for (let index = 0; index < targets.length; index += 1) {
        const { song, clip } = targets[index];
        let blob: Blob;
        let extension = batchFormat;
        if (batchFormat === "mp3") {
          blob = await fetchWebMusicClipBlob(song.id, clip.variant);
        } else if (batchFormat === "wav") {
          blob = await fetchWebMusicClipWavBlob(song.id, clip.variant);
        } else {
          blob = await fetchWebMusicTimedLyricsBlob(song.id, clip.variant, batchFormat);
        }
        if (batchFormat === "lrc" || batchFormat === "srt") extension = batchFormat;
        entries.push({
          name: clipFilename(song, clip, extension),
          data: new Uint8Array(await blob.arrayBuffer()),
        });
        setBatchDownloadProgress({ done: index + 1, total: targets.length });
      }
      saveBlob(
        createStoreZip(entries),
        `camxora-${batchFormat}-${new Date().toISOString().slice(0, 10)}.zip`
      );
    } catch (cause) {
      setBatchError(cause instanceof Error ? cause.message : "Batch download failed");
    } finally {
      if (mounted.current) {
        setBatchBusy(false);
        setBatchDownloadProgress(null);
      }
    }
  }

  async function deleteSelected() {
    if (!selected || deletingId) return;
    if (!window.confirm(`Delete "${selected.title}" permanently?`)) return;
    setDeletingId(selected.id);
    setError("");
    try {
      await deleteWebMusicGeneration(selected.id);
      if (!mounted.current) return;
      setSongs((current) => current.filter((item) => item.id !== selected.id));
      setTotalSongs((current) => Math.max(0, current - 1));
      setSelectedId(null);
      setSelectedDetail(null);
      setSelectedVariant(null);
      setSelectedClipKeys((current) => current.filter((key) => !key.startsWith(`${selected.id}:`)));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete this track");
    } finally {
      if (mounted.current) setDeletingId(null);
    }
  }

  async function unlockSelected() {
    if (!selected) return;
    setDetailLoading(true);
    try {
      const updated = await unlockWebMusicPreview(selected.id);
      if (!mounted.current) return;
      setSelectedDetail(updated);
      setSongs((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      void refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not unlock this preview");
    } finally {
      if (mounted.current) setDetailLoading(false);
    }
  }

  async function onSubmit() {
    if (busy || !formReady) return;
    if (cooldownSeconds > 0) {
      setError(`Please wait ${cooldownSeconds}s before creating another song.`);
      return;
    }
    if (queueFull) {
      setError(`The generation queue is full (${queueUsed}/${queueLimit}). Try again shortly.`);
      return;
    }
    if (batchRequiresUpgrade) {
      setError("Batch generation is a Pro feature. Upgrade or buy a credit pack to continue.");
      return;
    }
    if (quota?.requires_upgrade) {
      setError("A credit pack is required to generate full tracks. Open Buy packs to continue.");
      return;
    }
    setBusy(true);
    setError("");
    setStylesError("");
    setNotice("");
    let finalLyrics = lyrics.trim();
    if (mode === "custom" && !instrumental && lyricsMode === "prompt") {
      try {
        const draft = await generateWebMusicDraft(finalLyrics);
        finalLyrics = draft.lyrics;
        setLyrics(draft.lyrics);
        if (!title.trim() && draft.title) setTitle(draft.title);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Could not write lyrics");
        setBusy(false);
        return;
      }
    }
    const count = mode === "simple" ? simpleSongCount : 1;
    const payload: WebMusicGenerateInput = {
      mode: mode === "simple" ? "simple" : "advanced",
      prompt:
        mode === "simple"
          ? prompt.trim() || undefined
          : lyricsMode === "prompt"
            ? finalLyrics || undefined
            : undefined,
      title: title.trim() || undefined,
      style: mode === "custom" ? style.trim() || undefined : undefined,
      lyrics: mode === "custom" && !instrumental ? finalLyrics || undefined : undefined,
      instrumental,
      model,
      negative_tags: negativeTags.trim() || undefined,
      vocal_gender: instrumental ? undefined : vocalGender,
      style_weight: styleWeight,
      weirdness_constraint: weirdness,
      audio_weight: audioWeight,
      workspace_id: activeWorkspaceId ?? undefined,
    };
    setBatchProgress(count > 1 ? { done: 0, total: count } : null);
    let createdCount = 0;
    try {
      for (let index = 0; index < count; index += 1) {
        if (index > 0) {
          await new Promise((resolve) => window.setTimeout(resolve, BATCH_SUBMIT_GAP_MS));
        }
        const created = await generateWebMusic(payload);
        createdCount += 1;
        setQuota(created.quota);
        setBatchProgress({ done: createdCount, total: count });
        const loaded = await getWebMusicGeneration(created.task_id).catch(() => null);
        const pending: WebMusicGeneration = loaded ?? {
          id: created.task_id,
          title: created.title || title || "Untitled",
          lyrics: finalLyrics,
          style: created.style || style,
          model,
          model_label: created.model_label,
          is_preview: created.is_preview,
          unlockable: created.unlockable,
          preview_seconds: created.preview_seconds ?? null,
          instrumental,
          status: created.status || "pending",
          created_at: new Date().toISOString(),
          negative_tags: negativeTags || null,
          vocal_gender: instrumental ? null : vocalGender,
          style_weight: styleWeight,
          weirdness_constraint: weirdness,
          audio_weight: audioWeight,
          clips: [],
        };
        setSongs((current) => [pending, ...current.filter((item) => item.id !== pending.id)]);
        if (index === 0) {
          setSelectedId(pending.id);
          setSelectedDetail(pending);
          setSelectedVariant("ok");
        }
        void pollGeneration(created.task_id);
      }
      setNotice(
        count > 1
          ? `Queued ${count} songs. They will appear here as they finish.`
          : "Generation started. Your song will appear here."
      );
      setCooldownSeconds(5);
      void refreshSongs();
      void refresh();
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Could not start generation";
      const hint =
        cause instanceof WebMusicApiError && cause.status === 402
          ? " Open Buy packs to add credits."
          : "";
      setError(
        createdCount > 0
          ? `Created ${createdCount} of ${count} songs, then stopped: ${message}${hint}`
          : `${message}${hint}`
      );
      const nextQuota = await fetchWebMusicQuota().catch(() => null);
      if (nextQuota && mounted.current) setQuota(nextQuota);
    } finally {
      if (mounted.current) {
        setBusy(false);
        setBatchProgress(null);
      }
    }
  }

  const selected =
    selectedDetail?.id === selectedId
      ? selectedDetail
      : songs.find((song) => song.id === selectedId) ?? null;
  const selectedClip =
    selected?.clips?.find((clip) => clip.variant === selectedVariant) ??
    selected?.clips?.[0] ??
    null;
  const selectedCover = selectedClip?.image_url || "/hero.png";
  const selectedReady =
    selected && selectedClip
      ? clipIsReady(selected, selectedClip)
      : String(selected?.status || "").toLowerCase() === "success";
  const batchCount = mode === "simple" ? simpleSongCount : 1;
  const requiredCredits = (quota?.credits_per_song ?? 0) * batchCount;
  const availableCredits = quota?.credits_remaining ?? credits ?? 0;
  const needsCredits = requiredCredits > 0 && availableCredits < requiredCredits;
  const hasSubscription = Boolean(quota?.has_subscription || quota?.is_pro);
  const batchRequiresUpgrade = batchCount > 1 && !hasSubscription;
  const queueLimit = quota?.queue_limit ?? 20;
  const queueUsed = quota?.queue_used ?? 0;
  const queueSlotsFree = Math.max(0, queueLimit - queueUsed);
  const queueFull = queueUsed >= queueLimit;
  const batchOverQueue = batchCount > 1 && batchCount > queueSlotsFree;
  const createStatusHint = busy
    ? "Adding this song to the global queue. Paid songs go first."
    : cooldownSeconds > 0
      ? `You can create another in ${cooldownSeconds}s. No need to wait for audio.`
      : queueFull
        ? `Queue full (${queueUsed}/${queueLimit}). Wait until one song starts at Suno.`
        : queueUsed > 0
          ? `${queueUsed} in the global queue. Suno starts them one by one.`
          : null;
  const batchWarning =
    mode !== "simple" || batchCount <= 1
      ? null
      : batchRequiresUpgrade
        ? `Batch generation is a Pro feature. Upgrade to Pro or buy a credit pack to create ${batchCount} songs at once.`
        : needsCredits
          ? `You need ${requiredCredits.toLocaleString()} credits to create ${batchCount} songs but have ${availableCredits.toLocaleString()}. Top up or upgrade to continue.`
          : batchOverQueue
            ? `Only ${queueSlotsFree} of ${queueLimit} queue slots are free. Extra songs wait in the queue until earlier ones start at Suno.`
            : null;
  const generationCount = totalSongs || songs.length;
  const generationWord = generationCount === 1 ? "song" : "songs";
  const versionCount = songs.reduce((total, song) => total + generationClips(song).length, 0);
  const versionWord = versionCount === 1 ? "version" : "versions";
  const selectedClipAddable = Boolean(selectedClip?.ready);

  const filterOptions: Array<{ id: FeedFilter; label: string; disabled?: boolean }> = [
    { id: "liked", label: "Liked" },
    { id: "disliked", label: "Disliked" },
    { id: "public", label: "Public", disabled: true },
    { id: "private", label: "Private", disabled: true },
    { id: "uploads", label: "Uploads", disabled: true },
    { id: "full", label: "Full song" },
    { id: "cover", label: "Cover", disabled: true },
    { id: "voice", label: "Voice", disabled: true },
    { id: "downloads", label: "Downloads" },
    { id: "hideDisliked", label: "Hide Disliked" },
    { id: "hideStems", label: "Hide Stems", disabled: true },
  ];

  const rowKeyOf = (song: WebMusicGeneration, clip: WebMusicClip) =>
    clipTrackKey(song.id, clip.variant);

  const isLikedRow = (song: WebMusicGeneration, clip: WebMusicClip) =>
    likedKeys.includes(rowKeyOf(song, clip));
  const isDislikedRow = (song: WebMusicGeneration, clip: WebMusicClip) =>
    dislikedKeys.includes(rowKeyOf(song, clip));

  type FeedRow = {
    song: WebMusicGeneration;
    clip: WebMusicClip;
    key: string;
    title: string;
    ready: boolean;
    duration: number;
    createdAt: number;
  };

  const feedRows: FeedRow[] = songs.flatMap((song) =>
    generationClips(song).map((clip) => ({
      song,
      clip,
      key: rowKeyOf(song, clip),
      title: clip.title || song.title || "Untitled",
      ready: clipIsReady(song, clip),
      duration: Math.round(clip.duration_seconds || 0),
      createdAt: song.created_at ? new Date(song.created_at).getTime() : 0,
    }))
  );

  const searchTerm = feedSearch.trim().toLowerCase();
  const filteredRows = feedRows.filter((row) => {
    if (searchTerm) {
      const haystack = `${row.title} ${row.song.style || ""} ${row.song.lyrics || ""}`.toLowerCase();
      if (!haystack.includes(searchTerm)) return false;
    }
    if (feedFilters.includes("liked") && !isLikedRow(row.song, row.clip)) return false;
    if (feedFilters.includes("disliked") && !isDislikedRow(row.song, row.clip)) return false;
    if (feedFilters.includes("hideDisliked") && isDislikedRow(row.song, row.clip)) return false;
    if (feedFilters.includes("downloads") && !row.ready) return false;
    if (feedFilters.includes("full") && row.duration > 0 && row.duration < 60) return false;
    return true;
  });

  const sortedRows = [...filteredRows].sort((a, b) => {
    if (feedSort === "old") return a.createdAt - b.createdAt;
    if (feedSort === "most") {
      const diff = Number(isLikedRow(b.song, b.clip)) - Number(isLikedRow(a.song, a.clip));
      return diff || b.createdAt - a.createdAt;
    }
    if (feedSort === "least") {
      const diff = Number(isLikedRow(a.song, a.clip)) - Number(isLikedRow(b.song, b.clip));
      return diff || b.createdAt - a.createdAt;
    }
    return b.createdAt - a.createdAt;
  });

  const pageSize = 50;
  const pageCount = Math.max(1, Math.ceil(sortedRows.length / pageSize));
  const pageRows = sortedRows.slice((feedPage - 1) * pageSize, feedPage * pageSize);
  const dayLabel = (value: number) => {
    if (!value) return "Earlier";
    const date = new Date(value);
    const today = new Date();
    const day = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
    if (value >= day) return "Today";
    if (value >= day - 86_400_000) return "Yesterday";
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  };
  const groupedRows = pageRows.reduce<Array<{ label: string; rows: FeedRow[] }>>((groups, row) => {
    const label = dayLabel(row.createdAt);
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.rows.push(row);
    else groups.push({ label, rows: [row] });
    return groups;
  }, []);
  const activeFilterCount = feedFilters.length;
  const displayCredits = quota?.credits_remaining ?? credits ?? 0;
  const modelLabel = models.find((item) => item.value === model)?.label ?? "V6 Pro";
  const activeWorkspace = workspaces.find((workspace) => workspace.id === activeWorkspaceId);
  const activeWorkspaceName = activeWorkspace?.name ?? "My Workspace";
  const savedStylePrompts = songs
    .map((song) => (song.style || "").trim())
    .filter((value, index, all) => value && all.indexOf(value) === index)
    .slice(0, 8);

  async function toggleLikeRow(song: WebMusicGeneration, clip: WebMusicClip) {
    const key = rowKeyOf(song, clip);
    const nextLiked = !likedKeys.includes(key);
    setLikedKeys((current) =>
      nextLiked ? [...current, key] : current.filter((item) => item !== key)
    );
    setToast(nextLiked ? "Saved to Liked" : "Removed from Liked");
    try {
      await likeWebMusicGeneration(song.id, clip.variant, nextLiked);
    } catch {
      setLikedKeys((current) =>
        nextLiked ? current.filter((item) => item !== key) : [...current, key]
      );
      setToast("Could not update like");
    }
  }

  function toggleDislikeRow(song: WebMusicGeneration, clip: WebMusicClip) {
    const key = rowKeyOf(song, clip);
    setDislikedKeys((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key]
    );
  }

  async function copyClipLink(song: WebMusicGeneration, clip: WebMusicClip) {
    const url = `${window.location.origin}/library?clip=${encodeURIComponent(song.id)}&variant=${encodeURIComponent(clip.variant)}`;
    try {
      await navigator.clipboard.writeText(url);
      setToast("Link copied");
    } catch {
      setToast(url);
    }
  }

  async function deleteRow(song: WebMusicGeneration) {
    setDeletingId(song.id);
    try {
      await deleteWebMusicGeneration(song.id);
      setSongs((current) => current.filter((item) => item.id !== song.id));
      if (selectedId === song.id) {
        setSelectedId(null);
        }
      setToast("Song deleted");
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : "Could not delete song");
    } finally {
      if (mounted.current) setDeletingId(null);
    }
  }

  function openDetail(song: WebMusicGeneration, clip: WebMusicClip) {
    void selectSong(song.id, clip.variant);
  }

  function clearAllFields() {
    setPrompt("");
    setTitle("");
    setStyle("");
    setLyrics("");
    setNegativeTags("");
    setInstrumental(false);
    setStyleWeight(0.5);
    setWeirdness(0.5);
    setAudioWeight(0.5);
    setError("");
    setNotice("");
    setStylesError("");
  }

  const createDisabled =
    busy ||
    !formReady ||
    needsCredits ||
    batchRequiresUpgrade ||
    queueFull ||
    cooldownSeconds > 0 ||
    Boolean(quota?.requires_upgrade);

  if (loading || !user) {
    return (
      <div className="s-page">
        <div className="s-create-grid">
          <div className="s-form-col">
            <div className="s-form-scroll">
              {[0, 1, 2].map((item) => (
                <div className="s-skel" key={item}>
                  <span className="a" />
                  <span className="b">
                    <i />
                    <i />
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div className="s-feed">
            <div className="s-feed-head" />
            <div className="s-feed-scroll">
              {[0, 1, 2, 3].map((item) => (
                <div className="s-skel" key={item}>
                  <span className="a" />
                  <span className="b">
                    <i />
                    <i />
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  const shortModel =
    model === "V6" ? "v6" : model === "V6_MINI" ? "v6-mini" : "v6-wild";
  const creditsLabel =
    displayCredits >= 1000
      ? `${(displayCredits / 1000).toFixed(1).replace(/\.0$/, "")}k`
      : displayCredits.toLocaleString();
  const sortLabel =
    feedSort === "new"
      ? "Newest"
      : feedSort === "old"
        ? "Oldest"
        : feedSort === "most"
          ? "Most liked"
          : "Least liked";

  const renderRow = (row: FeedRow) => {
    const { song, clip, key, title, ready } = row;
    const liked = isLikedRow(song, clip);
    const disliked = isDislikedRow(song, clip);
    const isSelected = selectedId === song.id && selectedVariant === clip.variant;
    const selectedForBatch = selectedClipKeys.includes(key);
    const instrumental = generationIsInstrumental(song);
    return (
      <div
        className={`s-row s-row-compact${isSelected ? " selected" : ""}`}
        key={key}
        role="group"
        aria-label={title}
        onClick={() => {
          if (selectionMode) {
            if (ready) toggleClipSelection(key);
            return;
          }
          openDetail(song, clip);
        }}
      >
        {selectionMode ? (
          <button
            type="button"
            className={`s-selectbox${selectedForBatch ? " on" : ""}`}
            aria-label={`Select ${title}`}
            aria-pressed={selectedForBatch}
            onClick={(event) => {
              event.stopPropagation();
              if (ready) toggleClipSelection(key);
            }}
          >
            {selectedForBatch ? <Icon name="fa-check" /> : null}
          </button>
        ) : null}

        <button
          type="button"
          className="s-row-play"
          aria-label={ready ? `Play ${title}` : "Song not ready"}
          onClick={(event) => {
            event.stopPropagation();
            if (ready) playSong(song, clip);
          }}
        >
          <Icon name={ready ? "fa-play" : "fa-hourglass-half"} />
        </button>

        <div className="s-row-body">
          <div className="s-row-title">
            <a
              href={`/library?clip=${encodeURIComponent(song.id)}`}
              onClick={(event) => {
                event.preventDefault();
                openDetail(song, clip);
              }}
            >
              {title}
            </a>
            <span className="s-row-version">· {clipVersionLabel(clip.variant)}</span>
            {song.is_preview ? <span className="s-status live">Preview</span> : null}
          </div>
          <div className="s-row-desc">
            {ready ? "Ready" : statusLabel(song.status)} · {song.model_label || song.model || shortModel} ·{" "}
            {formatDate(song.created_at)}
            {row.duration ? ` · ${formatClipDuration(row.duration)}` : ""}
          </div>
        </div>

        <div className="s-row-downloads" onClick={(event) => event.stopPropagation()}>
          {!instrumental && ready ? (
            <>
              <a className="s-dl" href={clipDownloadUrl(song.id, clip.variant, "lrc")} aria-label="Download LRC">
                LRC
              </a>
              <a className="s-dl" href={clipDownloadUrl(song.id, clip.variant, "srt")} aria-label="Download SRT">
                SRT
              </a>
            </>
          ) : null}
          {ready ? (
            <>
              <a
                className="s-dl"
                href={clip.download_url || clipDownloadUrl(song.id, clip.variant, "mp3")}
                aria-label="Download MP3"
              >
                MP3
              </a>
              <a className="s-dl" href={clipDownloadUrl(song.id, clip.variant, "wav")} aria-label="Download WAV">
                WAV
              </a>
            </>
          ) : null}
        </div>

        <div className="s-anchor" data-s-menu style={{ position: "static" }} onClick={(event) => event.stopPropagation()}>
          <button
            type="button"
            className="s-row-more"
            aria-label="More options"
            aria-expanded={rowMenuKey === key}
            onClick={() => setRowMenuKey((current) => (current === key ? null : key))}
          >
            <Icon name="fa-ellipsis-vertical" />
          </button>
          {rowMenuKey === key ? (
            <div className="s-menu" role="menu" style={{ right: 12, top: 40, minWidth: 220 }}>
              <button
                type="button"
                className="s-menu-item"
                role="menuitem"
                onClick={() => {
                  setRowMenuKey(null);
                  void toggleLikeRow(song, clip);
                }}
              >
                <Icon name="fa-heart" /> {liked ? "Remove like" : "Like"}
              </button>
              <button
                type="button"
                className="s-menu-item"
                role="menuitem"
                onClick={() => {
                  setRowMenuKey(null);
                  toggleDislikeRow(song, clip);
                }}
              >
                <Icon name="fa-thumbs-down" /> {disliked ? "Remove dislike" : "Dislike"}
              </button>
              <button
                type="button"
                className="s-menu-item"
                role="menuitem"
                onClick={() => {
                  setRowMenuKey(null);
                  void copyClipLink(song, clip);
                }}
              >
                <Icon name="fa-link" /> Copy link
              </button>
              <Link className="s-menu-item" role="menuitem" href="/studio/editor" onClick={() => setRowMenuKey(null)}>
                <Icon name="fa-wand-magic-sparkles" /> Remix / Edit
              </Link>
              <div className="s-menu-sep" />
              <button
                type="button"
                className="s-menu-item"
                role="menuitem"
                onClick={() => {
                  setRowMenuKey(null);
                  openDetail(song, clip);
                }}
                disabled={!selectedClipAddable && !ready}
              >
                <Icon name="fa-list" /> Add to playlist
              </button>
              <button
                type="button"
                className="s-menu-item"
                role="menuitem"
                onClick={() => {
                  setRowMenuKey(null);
                  window.location.href = `/publish?clip=${encodeURIComponent(song.id)}`;
                }}
              >
                <Icon name="fa-arrow-up-from-bracket" /> Publish
              </button>
              <Link className="s-menu-item" role="menuitem" href="/studio/editor" onClick={() => setRowMenuKey(null)}>
                <Icon name="fa-table-columns" /> Open in Studio
              </Link>
              <div className="s-menu-sep" />
              <button
                type="button"
                className="s-menu-item"
                role="menuitem"
                onClick={() => {
                  setRowMenuKey(null);
                  void deleteRow(song);
                }}
                disabled={deletingId === song.id}
              >
                <Icon name="fa-trash" /> {deletingId === song.id ? "Deleting…" : "Delete"}
              </button>
            </div>
          ) : null}
        </div>
      </div>
    );
  };

  return (
    <div className="s-page">
      <h1 className="sr-only">Create music</h1>
      <div className="s-create-grid with-rail">
        <div
          className={`s-form-col${dragging ? " dragging" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            setAttachModal("audio");
          }}
        >
          <div className="s-drop-hint" aria-hidden="true">
            Drop to attach · Drop here to remix
          </div>

          <div className="s-tabs" role="tablist" aria-label="What to create">
            {(
              [
                { id: "songs", label: "Songs" },
                { id: "speech", label: "Speech" },
                { id: "sounds", label: "Sounds" },
              ] as const
            ).map((item, index) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                className={`s-tab${createTab === item.id ? " on" : ""}`}
                aria-selected={createTab === item.id}
                onClick={() => setCreateTab(item.id)}
              >
                {item.label}
                {createTab === item.id ? (
                  <span
                    className="s-tab-indicator"
                    style={{ left: `${(index * 100) / 3}%`, width: `${100 / 3}%` }}
                  />
                ) : null}
              </button>
            ))}
          </div>

          {createTab !== "songs" ? (
            <div className="s-empty" style={{ flex: 1 }}>
              <span className="ico">
                <Icon name={createTab === "speech" ? "fa-microphone-lines" : "fa-wave-square"} />
              </span>
              <b>{createTab === "speech" ? "Speech" : "Sounds"} is coming soon</b>
              <p>
                {createTab === "speech"
                  ? "Turn a script into narrated audio with cloned voices. This workspace is not enabled yet."
                  : "Generate sound effects and one-shot samples. This workspace is not enabled yet."}
              </p>
              <button type="button" className="s-btn s-btn-secondary" onClick={() => setCreateTab("songs")}>
                Create a song instead
              </button>
            </div>
          ) : (
            <>
              <div className="s-form-scroll">
                <div className="s-form-topline">
                  <div className="s-segment" role="tablist" aria-label="Create form mode">
                    <button
                      type="button"
                      role="tab"
                      aria-selected={mode === "simple"}
                      className={`s-segment-item${mode === "simple" ? " on" : ""}`}
                      onClick={() => setMode("simple")}
                    >
                      Simple
                    </button>
                    <button
                      type="button"
                      role="tab"
                      aria-selected={mode === "custom"}
                      className={`s-segment-item${mode === "custom" ? " on" : ""}`}
                      onClick={() => setMode("custom")}
                    >
                      Advanced
                    </button>
                  </div>

                  <div className="s-top-meta">
                  <div className="s-anchor" data-s-menu>
                    <button
                      type="button"
                      className="s-credits"
                      aria-label={`Credits remaining: ${displayCredits.toLocaleString()}`}
                      onClick={() => setCreditsOpen((value) => !value)}
                    >
                      <Icon name="fa-coins" />
                      {creditsLabel}
                    </button>
                    {creditsOpen ? (
                      <div className="s-menu" role="menu" style={{ top: 46, left: 0, width: 260 }}>
                        <div className="s-menu-label">Credits</div>
                        <div className="s-menu-item" style={{ cursor: "default" }}>
                          <span>Balance</span>
                          <span className="check">{displayCredits.toLocaleString()}</span>
                        </div>
                        <div className="s-menu-item" style={{ cursor: "default" }}>
                          <span>Per song</span>
                          <span className="check">{(quota?.credits_per_song ?? 0).toLocaleString()}</span>
                        </div>
                        {quota ? (
                          <div className="s-menu-item" style={{ cursor: "default" }}>
                            <span>Plan</span>
                            <span className="check">
                              {quota.has_subscription || quota.is_pro ? "Pro" : "Free"}
                            </span>
                          </div>
                        ) : null}
                        <div className="s-menu-sep" />
                        <Link className="s-menu-item" href="/pricing" role="menuitem">
                          <Icon name="fa-bag-shopping" /> Buy credits
                        </Link>
                        <Link className="s-menu-item" href="/redeem" role="menuitem">
                          <Icon name="fa-ticket" /> Redeem code
                        </Link>
                      </div>
                    ) : null}
                  </div>

                  <div className="s-anchor" data-s-menu>
                    <button
                      type="button"
                      className="s-model"
                      aria-label="Model"
                      aria-expanded={modelOpen}
                      onClick={() => setModelOpen((value) => !value)}
                    >
                      {shortModel}
                      <Icon name="fa-chevron-down" />
                    </button>
                    {modelOpen ? (
                      <div className="s-menu" role="menu" style={{ top: 46, right: 0, width: 320 }}>
                        <div className="s-menu-label">Model</div>
                        <button type="button" className="s-menu-item" role="menuitem" disabled>
                          <Icon name="fa-wand-magic-sparkles" /> Create Custom Model
                          <span className="check">Beta</span>
                        </button>
                        <div className="s-menu-item" style={{ cursor: "default", height: "auto", padding: "4px 10px 8px" }}>
                          <span className="s-note">Create a model based on your uploads (100 Credits)</span>
                        </div>
                        <div className="s-menu-sep" />
                        <div className="s-menu-label">All Models</div>
                        {[
                          { value: "V6" as WebMusicModel, name: "v6", tag: "Pro", desc: "Powerful. Versatile. Refined. Our best model yet." },
                          { value: "V6_WILD" as WebMusicModel, name: "v6-wild", tag: "Pro", desc: "Best for experimental ideas." },
                          { value: "V6_MINI" as WebMusicModel, name: "v6-mini", tag: "", desc: "A free, more efficient version of premium v6 models." },
                        ].map((option) => (
                          <button
                            key={option.value}
                            type="button"
                            role="menuitemradio"
                            aria-checked={model === option.value}
                            className={`s-menu-item${model === option.value ? " on" : ""}`}
                            style={{ height: "auto", padding: "8px 10px", alignItems: "flex-start" }}
                            onClick={() => {
                              setModel(option.value);
                              setModelOpen(false);
                            }}
                          >
                            <span style={{ display: "flex", flexDirection: "column", gap: 2, textAlign: "left" }}>
                              <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                <b style={{ fontWeight: 500, color: "var(--s-text)" }}>{option.name}</b>
                                {option.tag ? <span className="s-tag">{option.tag}</span> : null}
                              </span>
                              <span className="s-note">{option.desc}</span>
                            </span>
                            {model === option.value ? <span className="check">✓</span> : null}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  </div>
                </div>

                <div className="s-attach">
                  <button
                    type="button"
                    className="s-attach-btn"
                    onClick={() => setAttachModal("audio")}
                    aria-label="Add audio - Browse, upload, or record audio"
                  >
                    <Icon name="fa-music" /> <span className="s-btn-label">Audio</span>
                  </button>
                  <button
                    type="button"
                    className="s-attach-btn"
                    onClick={() => setAttachModal("voice")}
                    aria-label="Add Voice"
                  >
                    <Icon name="fa-microphone" /> <span className="s-btn-label">Voice</span>
                  </button>
                  <button
                    type="button"
                    className="s-attach-btn"
                    onClick={() => setAttachModal(mode === "custom" ? "inspo" : "image")}
                    aria-label={mode === "custom" ? "Add inspiration from a playlist" : "Add an image to your creation."}
                  >
                    <Icon name={mode === "custom" ? "fa-lightbulb" : "fa-image"} />{" "}
                    <span className="s-btn-label">{mode === "custom" ? "Inspo" : "Image"}</span>
                  </button>
                </div>

                {mode === "simple" ? (
                  <>
                    <div className="s-prompt-box">
                      <textarea
                        id="create-prompt"
                        value={prompt}
                        onChange={(event) => setPrompt(event.target.value)}
                        placeholder="A warm Khmer ballad about the Mekong at sunset. Female vocal, acoustic guitar, 72 BPM…"
                        maxLength={5000}
                        rows={5}
                        aria-label="Song description"
                      />
                      <div className="s-prompt-foot">
                        <div className="s-anchor" data-s-menu>
                          <button
                            type="button"
                            className="s-add-btn"
                            aria-label="Add to prompt"
                            aria-expanded={addMenuOpen}
                            onClick={() => {
                              setAddMenuOpen((value) => !value);
                              setAddSubmenu(null);
                            }}
                          >
                            <Icon name="fa-plus" />
                          </button>
                          {addMenuOpen ? (
                            <div className="s-menu s-add-menu" role="menu" style={{ bottom: 44, left: 0, width: 230 }}>
                              {addSubmenu ? (
                                <>
                                  <button
                                    type="button"
                                    className="s-add-back"
                                    onClick={() => setAddSubmenu(null)}
                                  >
                                    <Icon name="fa-chevron-left" />
                                    {addSubmenu === "lyrics"
                                      ? "Lyrics"
                                      : addSubmenu === "styles"
                                        ? "Styles"
                                        : addSubmenu === "audio"
                                          ? "Audio"
                                          : "Voice"}
                                  </button>
                                  {addSubmenu === "lyrics" ? (
                                    <>
                                      <button
                                        type="button"
                                        className="s-menu-item"
                                        role="menuitem"
                                        onClick={() => {
                                          setAddMenuOpen(false);
                                          setAddSubmenu(null);
                                          setMode("custom");
                                          setAdvancedOpen(false);
                                          setLyricsOpen(true);
                                          window.setTimeout(() => document.getElementById("create-lyrics")?.focus(), 80);
                                        }}
                                      >
                                        <Icon name="fa-pen" /> Write lyrics
                                      </button>
                                      <button
                                        type="button"
                                        className="s-menu-item"
                                        role="menuitem"
                                        onClick={() => {
                                          setAddMenuOpen(false);
                                          setAddSubmenu(null);
                                          setMode("custom");
                                          setLyricsOpen(true);
                                          void writeLyrics();
                                        }}
                                      >
                                        <Icon name="fa-wand-magic-sparkles" /> Auto-generate
                                      </button>
                                      <button
                                        type="button"
                                        className={`s-menu-item${instrumental ? " on" : ""}`}
                                        role="menuitemcheckbox"
                                        aria-checked={instrumental}
                                        onClick={() => {
                                          setAddMenuOpen(false);
                                          setAddSubmenu(null);
                                          setInstrumental((value) => !value);
                                        }}
                                      >
                                        <Icon name={instrumental ? "fa-check" : "fa-music"} /> Instrumental
                                      </button>
                                    </>
                                  ) : null}
                                  {addSubmenu === "styles" ? (
                                    <>
                                      <button
                                        type="button"
                                        className="s-menu-item"
                                        role="menuitem"
                                        onClick={() => {
                                          setAddMenuOpen(false);
                                          setAddSubmenu(null);
                                          setMode("custom");
                                          setStylePresetsOpen(true);
                                        }}
                                      >
                                        <Icon name="fa-bookmark" /> Saved styles
                                      </button>
                                      <button
                                        type="button"
                                        className="s-menu-item"
                                        role="menuitem"
                                        onClick={() => {
                                          setAddMenuOpen(false);
                                          setAddSubmenu(null);
                                          shuffleStyle();
                                        }}
                                      >
                                        <Icon name="fa-shuffle" /> Shuffle styles
                                      </button>
                                      <button
                                        type="button"
                                        className="s-menu-item"
                                        role="menuitem"
                                        onClick={() => {
                                          setAddMenuOpen(false);
                                          setAddSubmenu(null);
                                          setMode("custom");
                                          void suggestStyles();
                                        }}
                                      >
                                        <Icon name="fa-wand-magic-sparkles" /> Enhance styles
                                      </button>
                                    </>
                                  ) : null}
                                  {addSubmenu === "audio" ? (
                                    <>
                                      <button
                                        type="button"
                                        className="s-menu-item"
                                        role="menuitem"
                                        onClick={() => {
                                          setAddMenuOpen(false);
                                          setAddSubmenu(null);
                                          setAttachModal("audio");
                                        }}
                                      >
                                        <Icon name="fa-arrow-up-from-bracket" /> Upload audio
                                      </button>
                                      <button
                                        type="button"
                                        className="s-menu-item"
                                        role="menuitem"
                                        onClick={() => {
                                          setAddMenuOpen(false);
                                          setAddSubmenu(null);
                                          setAttachModal("audio");
                                        }}
                                      >
                                        <Icon name="fa-microphone" /> Record audio
                                      </button>
                                    </>
                                  ) : null}
                                  {addSubmenu === "voice" ? (
                                    <>
                                      <button
                                        type="button"
                                        className="s-menu-item"
                                        role="menuitem"
                                        onClick={() => {
                                          setAddMenuOpen(false);
                                          setAddSubmenu(null);
                                          setAttachModal("voices");
                                        }}
                                      >
                                        <Icon name="fa-user" /> My voices
                                      </button>
                                      <button
                                        type="button"
                                        className="s-menu-item"
                                        role="menuitem"
                                        onClick={() => {
                                          setAddMenuOpen(false);
                                          setAddSubmenu(null);
                                          setAttachModal("voices");
                                        }}
                                      >
                                        <Icon name="fa-users" /> Browse voices
                                      </button>
                                    </>
                                  ) : null}
                                </>
                              ) : (
                                <>
                                  {(
                                    [
                                      { id: "lyrics", icon: "fa-font", label: "Lyrics" },
                                      { id: "styles", icon: "fa-music", label: "Styles" },
                                    ] as const
                                  ).map((item) => (
                                    <button
                                      key={item.id}
                                      type="button"
                                      className="s-menu-item"
                                      role="menuitem"
                                      onClick={() => setAddSubmenu(item.id)}
                                    >
                                      <Icon name={item.icon} /> {item.label}
                                      <Icon name="fa-chevron-right" className="s-menu-caret" />
                                    </button>
                                  ))}
                                  <button
                                    type="button"
                                    className="s-menu-item"
                                    role="menuitem"
                                    onClick={() => {
                                      setAddMenuOpen(false);
                                      setAttachModal("playlist");
                                    }}
                                  >
                                    <Icon name="fa-rectangle-list" /> Playlist
                                  </button>
                                  <button
                                    type="button"
                                    className="s-menu-item"
                                    role="menuitem"
                                    onClick={() => {
                                      setAddMenuOpen(false);
                                      setAttachModal("image");
                                    }}
                                  >
                                    <Icon name="fa-image" /> Image
                                  </button>
                                  <button
                                    type="button"
                                    className="s-menu-item"
                                    role="menuitem"
                                    onClick={() => {
                                      setAddMenuOpen(false);
                                      setAttachModal("video");
                                    }}
                                  >
                                    <Icon name="fa-video" /> Video
                                  </button>
                                  {(
                                    [
                                      { id: "audio", icon: "fa-file-audio", label: "Audio" },
                                      { id: "voice", icon: "fa-microphone", label: "Voice" },
                                    ] as const
                                  ).map((item) => (
                                    <button
                                      key={item.id}
                                      type="button"
                                      className="s-menu-item"
                                      role="menuitem"
                                      onClick={() => setAddSubmenu(item.id)}
                                    >
                                      <Icon name={item.icon} /> {item.label}
                                      <Icon name="fa-chevron-right" className="s-menu-caret" />
                                    </button>
                                  ))}
                                </>
                              )}
                            </div>
                          ) : null}
                        </div>
                        <span className="s-char">{prompt.length}/5000</span>
                      </div>
                      <span className="s-drop" aria-hidden="true">
                        <span>Drop to attach</span>
                        <span>Drop here to remix</span>
                      </span>
                    </div>

                    <div className="s-form-card">
                      <div className="s-rowline">
                        <span className="s-rowline-label">Songs to generate</span>
                        <div className="s-radio-pair" role="group" aria-label="Songs to generate">
                          {SIMPLE_SONG_COUNTS.map((count) => (
                            <button
                              key={count}
                              type="button"
                              className={simpleSongCount === count ? "on" : ""}
                              aria-pressed={simpleSongCount === count}
                              onClick={() => setSimpleSongCount(count)}
                            >
                              {count}
                            </button>
                          ))}
                        </div>
                      </div>
                      {simpleSongCount > 1 ? (
                        <p className="s-note">
                          {simpleSongCount} songs · {simpleSongCount * 2} versions
                          {requiredCredits > 0 ? ` · ${requiredCredits.toLocaleString()} credits` : ""}
                        </p>
                      ) : (
                        <p className="s-note">Each song returns 2 versions{requiredCredits > 0 ? ` · ${requiredCredits.toLocaleString()} credits` : ""}</p>
                      )}
                    </div>
                  </>
                ) : (
                  <>
                    <div className="s-form-card">
                      <div className="s-rowline">
                        <span className="s-rowline-label">Styles</span>
                        <div className="s-counts">
                          <span className="s-char">{style.length}/1000</span>
                        <div className="s-anchor" data-s-menu>
                          <button
                            type="button"
                            className="s-sec-toggle"
                            aria-label="Saved styles" aria-expanded={stylePresetsOpen}
                            title="Saved style prompts"
                            onClick={() => setStylePresetsOpen((value) => !value)}
                          >
                            <Icon name="fa-bookmark" />
                          </button>
                          {stylePresetsOpen ? (
                            <div className="s-menu" role="menu" style={{ top: 40, right: 0, width: 260 }}>
                              <div className="s-menu-label">Saved styles</div>
                              {savedStylePrompts.length ? (
                                savedStylePrompts.map((value) => (
                                  <button
                                    key={value}
                                    type="button"
                                    className="s-menu-item"
                                    role="menuitem"
                                    onClick={() => {
                                      setStyle(value);
                                      setStylePresetsOpen(false);
                                    }}
                                  >
                                    <Icon name="fa-bookmark" />
                                    <span
                                      style={{
                                        overflow: "hidden",
                                        textOverflow: "ellipsis",
                                        whiteSpace: "nowrap",
                                      }}
                                    >
                                      {value}
                                    </span>
                                  </button>
                                ))
                              ) : (
                                <div className="s-note" style={{ padding: 10 }}>
                                  Styles you generate are saved here.
                                </div>
                              )}
                            </div>
                          ) : null}
                        </div>

                          <button
                            type="button"
                            className="s-sec-toggle"
                            aria-expanded={stylesOpen}
                            aria-label={stylesOpen ? "Collapse styles" : "Expand styles"}
                            onClick={() => setStylesOpen((value) => !value)}
                          >
                            <Icon name={stylesOpen ? "fa-chevron-up" : "fa-chevron-down"} />
                          </button>
                        </div>
                      </div>
                      {stylesOpen ? (
                        <>
                      <div className="s-style-box">
                        <textarea
                          id="create-style"
                          value={style}
                          onChange={(event) => setStyle(event.target.value)}
                          placeholder={
                            instrumental
                              ? "Instrumental genre, mood, instrumentation, tempo…"
                              : "urbano, electric guitar, upbeat rock, 128 BPM, eurodance"
                          }
                          maxLength={1000}
                          rows={3}
                          aria-label="Styles"
                        />
                      </div>
                      <div className="s-rowline">
                        <button
                          type="button"
                          className={`s-chip${instrumental ? " on" : ""}`}
                          aria-pressed={instrumental}
                          onClick={() => setInstrumental((value) => !value)}
                        >
                          <Icon name={instrumental ? "fa-check" : "fa-music"} /> Instrumental
                        </button>
                        <div className="s-counts">
                          <button type="button" className="s-chip" onClick={shuffleStyle}>
                            <Icon name="fa-shuffle" /> Shuffle
                          </button>
                          <button
                            type="button"
                            className="s-chip"
                            onClick={() => void suggestStyles()}
                            disabled={generatingStyles}
                          >
                            <Icon name="fa-wand-magic-sparkles" /> {generatingStyles ? "Enhancing…" : "Enhance"}
                          </button>
                        </div>
                      </div>
                      </>
                      ) : null}
                    </div>

                    <div className="s-form-card">
                      <div className="s-rowline">
                        <span className="s-rowline-label">Lyrics</span>
                        <div className="s-lyrics-tools">
                          {!instrumental ? (
                            <span className="s-radio-pair" role="group" aria-label="Lyrics mode">
                              <button
                                type="button"
                                className={lyricsMode === "write" ? "on" : ""}
                                aria-pressed={lyricsMode === "write"}
                                onClick={() => setLyricsMode("write")}
                              >
                                Write
                              </button>
                              <button
                                type="button"
                                className={lyricsMode === "prompt" ? "on" : ""}
                                aria-pressed={lyricsMode === "prompt"}
                                onClick={() => setLyricsMode("prompt")}
                              >
                                Prompt
                              </button>
                            </span>
                          ) : null}
                          <button
                            type="button"
                            className="s-sec-toggle"
                            aria-expanded={lyricsOpen}
                            aria-label={lyricsOpen ? "Collapse lyrics" : "Expand lyrics"}
                            onClick={() => setLyricsOpen((value) => !value)}
                          >
                            <Icon name={lyricsOpen ? "fa-chevron-up" : "fa-chevron-down"} />
                          </button>
                        </div>
                      </div>
                      {lyricsOpen ? (
                        <>
                      <div className="s-lyrics-box">
                        <textarea
                          id="create-lyrics"
                          value={lyrics}
                          onChange={(event) => setLyrics(event.target.value)}
                          placeholder={
                            instrumental
                              ? "Instrumental track — lyrics are not used."
                              : lyricsMode === "write"
                                ? "Write lyrics, or paste a verse…"
                                : "Describe the story or feeling you want the lyrics to capture…"
                          }
                          disabled={instrumental}
                          maxLength={5000}
                          rows={5}
                          aria-label="Lyrics"
                        />
                        <div className="s-lyrics-foot">
                          {lyricsMode === "write" && !instrumental ? (
                            <button
                              type="button"
                              className="s-lyrics-auto"
                              onClick={() => void writeLyrics()}
                              disabled={writingLyrics || instrumental}
                              aria-label={writingLyrics ? "Generating lyrics" : "Auto-generate lyrics"}
                              title="Auto-generate lyrics"
                            >
                              <Icon name="fa-wand-magic-sparkles" />
                            </button>
                          ) : (
                            <span />
                          )}
                          <span className="s-char">{lyrics.length}/5000</span>
                        </div>
                      </div>
                      {lyricsMode === "prompt" && !instrumental ? (
                        <p className="s-note">Lyrics are written for you when the song starts.</p>
                      ) : null}
                      </>
                      ) : null}
                    </div>

                    <div className="s-more s-form-card">
                      <button
                        type="button"
                        className="s-more-head"
                        aria-expanded={advancedOpen}
                        onClick={() => setAdvancedOpen((value) => !value)}
                      >
                        <Icon name="fa-sliders" /> More Options
                        <Icon name={advancedOpen ? "fa-chevron-up" : "fa-chevron-down"} />
                      </button>
                      {advancedOpen ? (
                        <div className="s-more-body">
                          <div className="s-settings-row">
                            <span className="s-settings-label">Exclude styles</span>
                          </div>
                          <input
                            className="s-input"
                            value={negativeTags}
                            onChange={(event) => setNegativeTags(event.target.value)}
                            placeholder="choir, backing vocals, falsetto"
                            aria-label="Exclude styles"
                          />

                          <div className="s-settings-row">
                            <span className="s-settings-label">Vocal Gender</span>
                            <div className="s-radio-pair" role="group" aria-label="Vocal gender">
                              {(
                                [
                                  { value: "m", label: "Male" },
                                  { value: "f", label: "Female" },
                                ] as const
                              ).map((option) => (
                                <button
                                  key={option.value}
                                  type="button"
                                  className={vocalGender === option.value ? "on" : ""}
                                  aria-pressed={vocalGender === option.value}
                                  onClick={() => setVocalGender(option.value)}
                                  disabled={instrumental}
                                >
                                  {option.label}
                                </button>
                              ))}
                            </div>
                          </div>

                          <div className="s-settings-row">
                            <span className="s-settings-label">Duration</span>
                            <div className="s-radio-pair" role="group" aria-label="Duration">
                              <button
                                type="button"
                                className={durationMode === "custom" ? "on" : ""}
                                aria-pressed={durationMode === "custom"}
                                onClick={() => setDurationMode("custom")}
                              >
                                Custom
                              </button>
                              <button
                                type="button"
                                className={durationMode === "auto" ? "on" : ""}
                                aria-pressed={durationMode === "auto"}
                                onClick={() => setDurationMode("auto")}
                              >
                                Auto
                              </button>
                            </div>
                          </div>

                          <div className="s-settings-row">
                            <span className="s-settings-label">Max Mode</span>
                            <button
                              type="button"
                              className={`s-switch${maxMode ? " on" : ""}`}
                              role="switch"
                              aria-checked={maxMode}
                              aria-label="Max Mode"
                              onClick={() => setMaxMode((value) => !value)}
                            />
                          </div>

                          <div className="s-settings-row">
                            <span className="s-settings-label">Weirdness</span>
                            <div className="s-slider">
                              <input
                                type="range"
                                min={0}
                                max={1}
                                step={0.01}
                                value={weirdness}
                                aria-label="Weirdness"
                                style={{ "--v": `${Math.round(weirdness * 100)}%` } as React.CSSProperties}
                                onChange={(event) => setWeirdness(Number(event.target.value))}
                              />
                              <output>{Math.round(weirdness * 100)} %</output>
                            </div>
                          </div>

                          <div className="s-settings-row">
                            <span className="s-settings-label">Style Influence</span>
                            <div className="s-slider">
                              <input
                                type="range"
                                min={0}
                                max={1}
                                step={0.01}
                                value={styleWeight}
                                aria-label="Style Influence"
                                style={{ "--v": `${Math.round(styleWeight * 100)}%` } as React.CSSProperties}
                                onChange={(event) => setStyleWeight(Number(event.target.value))}
                              />
                              <output>{Math.round(styleWeight * 100)} %</output>
                            </div>
                          </div>

                          <div className="s-settings-row">
                            <span className="s-settings-label">Variety</span>
                            <div className="s-slider">
                              <input
                                type="range"
                                min={0}
                                max={1}
                                step={0.01}
                                value={audioWeight}
                                aria-label="Variety"
                                style={{ "--v": `${Math.round(audioWeight * 100)}%` } as React.CSSProperties}
                                onChange={(event) => setAudioWeight(Number(event.target.value))}
                              />
                              <output>{Math.round(audioWeight * 100)} %</output>
                            </div>
                          </div>

                          <div className="s-settings-row">
                            <span className="s-settings-label">Personalize</span>
                            <div className="s-radio-pair" role="group" aria-label="Personalize">
                              <button type="button" className="on">
                                My Taste
                              </button>
                            </div>
                          </div>
                        </div>
                      ) : null}
                    </div>

                    <div className="s-field s-form-card">
                      <span className="s-field-label">Song Title (Optional)</span>
                      <input
                        className="s-input"
                        value={title}
                        onChange={(event) => setTitle(event.target.value)}
                        placeholder="Song title"
                        maxLength={200}
                        aria-label="Song Title (Optional)"
                      />
                    </div>

                    {stylesError ? <p className="s-error">{stylesError}</p> : null}
                  </>
                )}

                    <div className="s-rowline s-form-card">
                      <span className="s-rowline-label">Save to...</span>
                      <div className="s-anchor" data-s-menu>
                        <button
                          type="button"
                          className="s-select"
                          onClick={() => { setWorkspaceMenuOpen(false); setSaveMenuOpen((value) => !value); }}
                        >
                          {activeWorkspaceName}
                          <Icon name="fa-chevron-down" />
                        </button>
                        {saveMenuOpen ? (
                          <div className="s-menu" role="menu" style={{ bottom: 46, right: 0, width: 240 }}>
                            <div className="s-menu-label">Workspaces</div>
                            <button
                              type="button"
                              className="s-menu-item"
                              role="menuitem"
                              onClick={() => {
                                setActiveWorkspaceId(null);
                                setSaveMenuOpen(false);
                              }}
                            >
                              <Icon name="fa-folder" /> My Workspace
                              {!activeWorkspaceId ? <span className="check">✓</span> : null}
                            </button>
                            {workspaces.filter((workspace) => !workspace.is_default).map((workspace) => (
                              <button
                                key={workspace.id}
                                type="button"
                                className="s-menu-item"
                                role="menuitem"
                                onClick={() => {
                                  setActiveWorkspaceId(workspace.id);
                                  setSaveMenuOpen(false);
                                }}
                              >
                                <Icon name="fa-folder" /> {workspace.name}
                                {activeWorkspaceId === workspace.id ? <span className="check">✓</span> : null}
                              </button>
                            ))}
                            <div className="s-menu-sep" />
                            <button
                              type="button"
                              className="s-menu-item"
                              role="menuitem"
                              onClick={() => {
                                setNewWorkspaceOpen(true);
                                setNewWorkspaceName("");
                                setSaveMenuOpen(false);
                              }}
                            >
                              <Icon name="fa-plus" /> New workspace
                            </button>
                            <button
                              type="button"
                              className="s-menu-item"
                              role="menuitem"
                              onClick={() => {
                                setRenameWorkspaceName(activeWorkspaceName);
                                setRenameWorkspaceOpen(true);
                                setSaveMenuOpen(false);
                              }}
                            >
                              <Icon name="fa-pen" /> Rename current
                            </button>
                          </div>
                        ) : null}
                      </div>
                    </div>

                    {newWorkspaceOpen ? (
                      <div className="s-rowline">
                        <input
                          className="s-input"
                          autoFocus
                          value={newWorkspaceName}
                          onChange={(event) => setNewWorkspaceName(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter") void onCreateWorkspace();
                            if (event.key === "Escape") setNewWorkspaceOpen(false);
                          }}
                          placeholder="Workspace name"
                          aria-label="New workspace name"
                          maxLength={120}
                        />
                        <button
                          type="button"
                          className="s-btn s-btn-secondary"
                          onClick={() => void onCreateWorkspace()}
                          disabled={workspaceBusy || !newWorkspaceName.trim()}
                        >
                          {workspaceBusy ? "Saving…" : "Create"}
                        </button>
                      </div>
                    ) : null}

                    {renameWorkspaceOpen ? (
                      <div className="s-rowline">
                        <input
                          className="s-input"
                          autoFocus
                          value={renameWorkspaceName}
                          onChange={(event) => setRenameWorkspaceName(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter") void onRenameWorkspace();
                            if (event.key === "Escape") setRenameWorkspaceOpen(false);
                          }}
                          placeholder="Workspace name"
                          aria-label="Workspace name"
                          maxLength={120}
                        />
                        <button
                          type="button"
                          className="s-btn s-btn-secondary"
                          onClick={() => void onRenameWorkspace()}
                          disabled={workspaceBusy || !renameWorkspaceName.trim()}
                        >
                          {workspaceBusy ? "Saving…" : "Save"}
                        </button>
                      </div>
                    ) : null}

                {batchWarning ? (
                  <p className="s-note warn">
                    {batchWarning} <Link href="/pricing">Upgrade</Link>
                  </p>
                ) : null}
              </div>

              <div className="s-form-foot">
                {error ? (
                  <p className="s-error" role="alert">
                    {error}
                  </p>
                ) : null}
                {notice ? <p className="s-note" role="status">{notice}</p> : null}
                {createStatusHint ? <p className="s-note" role="status">{createStatusHint}</p> : null}
                {(needsCredits && batchCount === 1) || quota?.requires_upgrade ? (
                  <p className="s-note warn">
                    Not enough credits for this selection. <Link href="/pricing">Buy packs</Link>
                  </p>
                ) : null}
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <button
                    type="button"
                    className="s-btn s-btn-ghost s-btn-icon s-cta-icon"
                    aria-label="Clear all form inputs"
                    title="Clear all form inputs"
                    onClick={clearAllFields}
                  >
                    <Icon name="fa-eraser" />
                  </button>
                  <button
                    type="button"
                    className="s-create-btn"
                    style={{ flex: 1 }}
                    onClick={onSubmit}
                    disabled={createDisabled}
                    aria-busy={busy}
                  >
                    {batchProgress
                      ? `Creating ${Math.min(batchProgress.done + 1, batchProgress.total)}/${batchProgress.total}…`
                      : busy
                        ? "Creating…"
                        : cooldownSeconds > 0
                          ? `Wait ${cooldownSeconds}s`
                          : queueFull
                            ? `Queue full (${queueUsed}/${queueLimit})`
                            : "Create"}
                  </button>
                </div>
                <p className="s-note" style={{ textAlign: "center" }}>
                  {requiredCredits > 0
                    ? `${requiredCredits.toLocaleString()} credits · ${availableCredits.toLocaleString()} available`
                    : "Uses your credit balance"}
                </p>
              </div>
            </>
          )}
        </div>

        <div className="s-feed">
          <div className="s-feed-head">
            <span className="s-workspace-label">Workspaces</span>
            <div className="s-anchor" data-s-menu>
              <button
                type="button"
                className="s-workspace"
                onClick={() => { setSaveMenuOpen(false); setWorkspaceMenuOpen((value) => !value); }}
                aria-expanded={workspaceMenuOpen}
              >
                <b>{activeWorkspaceName}</b>
                <Icon name="fa-chevron-down" />
              </button>
              {workspaceMenuOpen ? (
                <div className="s-menu" role="menu" style={{ top: 34, left: 0, width: 240 }}>
                  <div className="s-menu-label">Workspaces</div>
                  <button
                    type="button"
                    className="s-menu-item"
                    role="menuitem"
                    onClick={() => {
                      setActiveWorkspaceId(null);
                      setWorkspaceMenuOpen(false);
                    }}
                  >
                    <Icon name="fa-folder" /> My Workspace
                    {!activeWorkspaceId ? <span className="check">✓</span> : null}
                  </button>
                  {workspaces.filter((workspace) => !workspace.is_default).map((workspace) => (
                    <button
                      key={workspace.id}
                      type="button"
                      className="s-menu-item"
                      role="menuitem"
                      onClick={() => {
                        setActiveWorkspaceId(workspace.id);
                        setWorkspaceMenuOpen(false);
                        setSelectedClipKeys([]);
                      }}
                    >
                      <Icon name="fa-folder" /> {workspace.name}
                      {activeWorkspaceId === workspace.id ? <span className="check">✓</span> : null}
                    </button>
                  ))}
                  <div className="s-menu-sep" />
                  <button
                    type="button"
                    className="s-menu-item"
                    role="menuitem"
                    onClick={() => {
                      setNewWorkspaceOpen(true);
                      setNewWorkspaceName("");
                      setWorkspaceMenuOpen(false);
                    }}
                  >
                    <Icon name="fa-plus" /> New workspace
                  </button>
                  <button
                    type="button"
                    className="s-menu-item"
                    role="menuitem"
                    onClick={() => {
                      setRenameWorkspaceName(activeWorkspaceName);
                      setRenameWorkspaceOpen(true);
                      setWorkspaceMenuOpen(false);
                    }}
                  >
                    <Icon name="fa-pen" /> Rename current
                  </button>
                </div>
              ) : null}
            </div>

            <span className="s-spacer" />

            <button
              type="button"
              className="s-btn s-btn-icon sm"
              aria-label="New workspace"
              title="New workspace"
              onClick={() => {
                setNewWorkspaceName("");
                setNewWorkspaceOpen(true);
              }}
            >
              <Icon name="fa-plus" />
            </button>
            <button
              type="button"
              className={`s-btn s-btn-icon sm${selectionMode ? " on" : ""}`}
              aria-label="Select clips"
              aria-pressed={selectionMode}
              onClick={() => {
                setSelectionMode((value) => !value);
                setSelectedClipKeys([]);
              }}
            >
              <Icon name="fa-check-double" />
            </button>
            <div className="s-anchor" data-s-menu>
              <button
                type="button"
                className="s-btn s-btn-icon sm"
                aria-label="Share workspace"
                onClick={() => setShareOpen((value) => !value)}
                aria-expanded={shareOpen}
              >
                <Icon name="fa-share" />
              </button>
              {shareOpen ? (
                <div className="s-menu" role="menu" style={{ top: 46, right: 0, width: 230 }}>
                  <button
                    type="button"
                    className="s-menu-item"
                    role="menuitem"
                    onClick={() => {
                      void navigator.clipboard
                        .writeText(window.location.href)
                        .then(() => setToast("Workspace link copied"))
                        .catch(() => setToast("Could not copy link"));
                      setShareOpen(false);
                    }}
                  >
                    <Icon name="fa-link" /> Copy workspace link
                  </button>
                  <Link className="s-menu-item" href="/library" role="menuitem">
                    <Icon name="fa-rectangle-list" /> Open in Library
                  </Link>
                  <button
                    type="button"
                    className="s-menu-item"
                    role="menuitem"
                    onClick={() => {
                      setSelectionMode(true);
                      setShareOpen(false);
                    }}
                  >
                    <Icon name="fa-download" /> Select &amp; download
                  </button>
                </div>
              ) : null}
            </div>
          </div>

          <div className="s-feed-tools">
            <label className="s-search">
              <Icon name="fa-magnifying-glass" />
              <input
                value={feedSearch}
                onChange={(event) => setFeedSearch(event.target.value)}
                placeholder="Search clips"
                aria-label="Search clips"
              />
            </label>

            <div className="s-anchor" data-s-menu>
              <button
                type="button"
                className={`s-pill${activeFilterCount ? " on" : ""}`}
                onClick={() => setFiltersOpen((value) => !value)}
                aria-expanded={filtersOpen}
                aria-label={`Filters (${activeFilterCount})`}
              >
                <Icon name="fa-filter" /> <span className="s-btn-label">Filters{activeFilterCount ? ` (${activeFilterCount})` : ""}</span>
              </button>
              {filtersOpen ? (
                <div className="s-menu" role="menu" style={{ top: 46, right: 0, width: 200 }}>
                  {filterOptions.map((option) => {
                    const on = feedFilters.includes(option.id);
                    return (
                      <button
                        key={option.id}
                        type="button"
                        className={`s-menu-item${on ? " on" : ""}`}
                        role="menuitemcheckbox"
                        aria-checked={on}
                        disabled={option.disabled}
                        onClick={() =>
                          setFeedFilters((current) =>
                            current.includes(option.id)
                              ? current.filter((item) => item !== option.id)
                              : [...current, option.id]
                          )
                        }
                      >
                        {option.label}
                        {option.disabled ? <span className="check">—</span> : on ? <span className="check">✓</span> : null}
                      </button>
                    );
                  })}
                </div>
              ) : null}
            </div>

            <div className="s-anchor" data-s-menu>
              <button
                type="button"
                className="s-pill"
                onClick={() => setSortOpen((value) => !value)}
                aria-expanded={sortOpen}
                aria-label={sortLabel}
              >
                {sortLabel}
                <Icon name="fa-chevron-down" />
              </button>
              {sortOpen ? (
                <div className="s-menu" role="menu" style={{ top: 46, right: 0, width: 180 }}>
                  {(
                    [
                      { id: "new", label: "Newest" },
                      { id: "old", label: "Oldest" },
                      { id: "most", label: "Most liked" },
                      { id: "least", label: "Least liked" },
                    ] as const
                  ).map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      className="s-menu-item"
                      role="menuitemradio"
                      aria-checked={feedSort === option.id}
                      onClick={() => {
                        setFeedSort(option.id);
                        setSortOpen(false);
                      }}
                    >
                      {option.label}
                      {feedSort === option.id ? <span className="check">✓</span> : null}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            <button
              type="button"
              className="s-pill"
              aria-label={`View: $<span className="s-btn-label">{viewMode === "list" ? "List" : "Grid"}</span>`}
              onClick={() => setViewMode((value) => (value === "list" ? "grid" : "list"))}
            >
              <Icon name={viewMode === "list" ? "fa-list" : "fa-table-cells"} />
              <span className="s-btn-label">{viewMode === "list" ? "List" : "Grid"}</span>
            </button>

            <div className="s-pager">
              <button
                type="button"
                aria-label="Previous page"
                onClick={() => setFeedPage((value) => Math.max(1, value - 1))}
                disabled={feedPage <= 1}
              >
                <Icon name="fa-chevron-left" />
              </button>
              <input
                aria-label="Current page number"
                value={feedPage}
                onChange={(event) => {
                  const next = Number(event.target.value.replace(/\D/g, "")) || 1;
                  setFeedPage(Math.min(pageCount, Math.max(1, next)));
                }}
              />
              <button
                type="button"
                aria-label="Next page"
                onClick={() => {
                  if (feedPage < pageCount) setFeedPage(feedPage + 1);
                  else if (songs.length < totalSongs) void loadMoreSongs();
                }}
              >
                <Icon name="fa-chevron-right" />
              </button>
            </div>
          </div>

          {selectionMode ? (
            <div className="s-rowline" style={{ paddingBottom: 8 }}>
              <span className="s-note" role="status" aria-live="polite">
                {selectedClipKeys.length} selected
              </span>
              <div className="s-counts">
                <div className="s-radio-pair" role="group" aria-label="Batch download format">
                  {DOWNLOAD_FORMATS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={batchFormat === option.value ? "on" : ""}
                      aria-pressed={batchFormat === option.value}
                      onClick={() => {
                        setBatchFormat(option.value);
                        setBatchError("");
                      }}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  className="s-chip"
                  onClick={() => void onBatchDownload()}
                  disabled={batchBusy || selectedClipKeys.length === 0}
                >
                  <Icon name="fa-download" />
                  {batchBusy
                    ? batchDownloadProgress
                      ? `${batchDownloadProgress.done}/${batchDownloadProgress.total}`
                      : "Preparing…"
                    : "ZIP"}
                </button>
                <button type="button" className="s-chip" onClick={() => setSelectedClipKeys([])}>
                  Clear
                </button>
              </div>
            </div>
          ) : null}
          {batchError ? <p className="s-error">{batchError}</p> : null}

          <div className="s-feed-scroll">
            {loadingSongs ? (
              [0, 1, 2, 3].map((item) => (
                <div className="s-skel" key={item}>
                  <span className="a" />
                  <span className="b">
                    <i />
                    <i />
                  </span>
                </div>
              ))
            ) : !sortedRows.length ? (
              <div className="s-empty">
                <span className="ico">
                  <Icon name="fa-music" />
                </span>
                <b>{feedSearch || activeFilterCount ? "No clips match" : "Your songs will land here"}</b>
                <p>
                  {feedSearch || activeFilterCount
                    ? "Try a different search or clear your filters."
                    : "Describe a song or write lyrics, then hit Create."}
                </p>
                {feedSearch || activeFilterCount ? (
                  <button
                    type="button"
                    className="s-btn s-btn-secondary"
                    onClick={() => {
                      setFeedSearch("");
                      setFeedFilters([]);
                    }}
                  >
                    Clear filters
                  </button>
                ) : null}
              </div>
            ) : viewMode === "list" ? (
              groupedRows.map((group) => (
                <div key={group.label}>
                  <h3 className="s-day">{group.label}</h3>
                  {group.rows.map(renderRow)}
                </div>
              ))
            ) : (
              groupedRows.map((group) => (
                <div key={group.label}>
                  <h3 className="s-day">{group.label}</h3>
                  <div className="s-grid">
                    {group.rows.map((row) => (
                      <div
                        className="s-card"
                        key={row.key}
                        onClick={() => openDetail(row.song, row.clip)}
                        role="button"
                        tabIndex={0}
                      >
                        <div className="s-card-cover">
                          <img src={row.clip.image_url || "/hero.png"} alt="" loading="lazy" />
                        </div>
                        <b>{row.title}</b>
                        <small>{row.song.style || "No style tags"}</small>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}

            {songs.length < totalSongs ? (
              <div className="s-lib-foot">
                <button
                  type="button"
                  className="s-btn s-btn-secondary"
                  onClick={() => void loadMoreSongs()}
                  disabled={loadingMore}
                >
                  {loadingMore ? "Loading…" : `Load more (${songs.length} of ${totalSongs})`}
                </button>
              </div>
            ) : null}
          </div>
        </div>
        <TrackRail
          key={`${selected?.id ?? "empty"}:${selectedClip?.variant ?? ""}`}
          detail={selected ?? null}
          clip={selectedClip ?? null}
          liked={selected && selectedClip ? isLikedRow(selected, selectedClip) : false}
          playlists={playlists}
          loading={detailLoading}
          onPlay={() => {
            if (selected) playSong(selected, selectedClip ?? undefined);
          }}
          onLike={() => {
            if (selected && selectedClip) void toggleLikeRow(selected, selectedClip);
          }}
          onUnlock={() => void unlockSelected()}
          onDelete={() => void deleteSelected()}
          onRename={async (nextTitle, variant) => {
            if (!selected) return false;
            try {
              const updated = await updateWebMusicGenerationTitle(selected.id, nextTitle, variant);
              if (!mounted.current) return false;
              setSelectedDetail(updated);
              setSongs((current) =>
                current.map((item) => (item.id === updated.id ? updated : item))
              );
              return true;
            } catch (cause) {
              setError(cause instanceof Error ? cause.message : "Could not rename this track");
              return false;
            }
          }}
          onAddToPlaylist={async (playlist) => {
            if (!selected || !selectedClip?.ready) return;
            try {
              await addWebMusicPlaylistItem(playlist.id, selected.id, selectedClip.variant);
              setNotice(`Added to ${playlist.name}.`);
            } catch (cause) {
              setError(cause instanceof Error ? cause.message : "Could not add to playlist");
            }
          }}
          onCreatePlaylist={async (name) => {
            try {
              const created = await createWebMusicPlaylist(name);
              if (mounted.current) setPlaylists((current) => [...current, created]);
              setNotice(`Created playlist "${created.name}".`);
              return created;
            } catch (cause) {
              setError(cause instanceof Error ? cause.message : "Could not create playlist");
              return null;
            }
          }}
        />      </div>

      {attachModal ? (
        <div className="s-modal-overlay" role="dialog" aria-modal="true" onClick={() => setAttachModal(null)}>
          <div className="s-modal" style={{ width: "min(520px,100%)" }} onClick={(event) => event.stopPropagation()}>
            <div className="s-modal-head">
              <h3>
                {attachModal === "audio"
                  ? "Add audio"
                  : attachModal === "voices"
                    ? "Add voice reference"
                    : attachModal === "video"
                      ? "Add video"
                      : attachModal === "playlist"
                        ? "Add playlist"
                        : attachModal === "voice"
                          ? "Add voice"
                          : attachModal === "inspo"
                            ? "Add inspiration"
                            : "Add image"}
              </h3>
              <button type="button" className="s-btn s-btn-icon sm" onClick={() => setAttachModal(null)} aria-label="Close">
                <Icon name="fa-xmark" />
              </button>
            </div>
            <div className="s-modal-body">
              {attachModal === "audio" ? (
                <div className="s-audio-attach">
                  {audioUpload ? (
                    <div className="s-audio-file">
                      <span className="s-audio-ico">
                        <Icon name="fa-file-audio" />
                      </span>
                      <div>
                        <b>{audioUpload.filename}</b>
                        <small>
                          {audioUpload.duration_seconds
                            ? `${formatClipDuration(audioUpload.duration_seconds)} · `
                            : ""}
                          {Math.max(1, Math.round(audioUpload.size_bytes / 1024))} KB
                        </small>
                      </div>
                      <button
                        type="button"
                        className="s-btn s-btn-icon sm"
                        aria-label="Remove audio"
                        onClick={() => setAudioUpload(null)}
                      >
                        <Icon name="fa-xmark" />
                      </button>
                    </div>
                  ) : (
                    <label className="s-audio-drop">
                      <input
                        type="file"
                        accept="audio/*"
                        onChange={(event) => {
                          const file = event.target.files?.[0];
                          if (file) void uploadAudioFile(file);
                          event.target.value = "";
                        }}
                      />
                      <Icon name="fa-arrow-up-from-bracket" />
                      <b>Choose an audio file</b>
                      <span>MP3, WAV, M4A, OGG or WebM · up to 50 MB</span>
                    </label>
                  )}
                  <div className="s-counts">
                    <button
                      type="button"
                      className="s-btn s-btn-secondary"
                      onClick={() => void toggleRecording()}
                      disabled={audioUploading || audioBusy || Boolean(audioUpload)}
                    >
                      <Icon name={recording ? "fa-stop" : "fa-microphone"} />{" "}
                      {recording ? "Stop & upload" : "Record"}
                    </button>
                    {audioUpload ? (
                      <>
                        <button
                          type="button"
                          className="s-btn s-btn-primary"
                          onClick={() => void runAudioOperation("extend")}
                          disabled={audioBusy || audioUploading}
                        >
                          Extend
                        </button>
                        <button
                          type="button"
                          className="s-btn s-btn-secondary"
                          onClick={() => void runAudioOperation("cover")}
                          disabled={audioBusy || audioUploading}
                        >
                          Cover
                        </button>
                      </>
                    ) : null}
                  </div>
                  {audioUploading ? <p className="s-note">Uploading…</p> : null}
                  {audioBusy ? <p className="s-note">Queueing…</p> : null}
                  {audioError ? <p className="s-error">{audioError}</p> : null}
                  <p className="s-note">
                    Extend continues the track. Cover recreates it using your current prompt and styles.
                  </p>
                </div>
              ) : (
                <>
                  <p className="s-note">
                    {attachModal === "voices"
                      ? "Reuse a saved voice or pick one from the library as a vocal reference."
                      : attachModal === "video"
                        ? "Attach a video reference to guide motion, mood, or a visual cover."
                        : attachModal === "playlist"
                          ? "Reference one of your playlists as style inspiration for this song."
                          : attachModal === "voice"
                            ? "Pick a voice reference to shape the vocal tone of your next song."
                            : attachModal === "inspo"
                              ? "Pull a style reference from one of your playlists."
                              : "Attach artwork to your creation. Images are used as the cover."}
                  </p>
                  <div className="s-box">
                    Reference attachments are not enabled for this workspace yet. You can still upload and reuse audio
                    from the Studio editor.
                  </div>
                </>
              )}
            </div>
            <div className="s-modal-foot">
              <Link className="s-btn s-btn-secondary" href="/studio/editor">
                <Icon name="fa-table-columns" /> Open Studio
              </Link>
              <span style={{ flex: 1 }} />
              <button type="button" className="s-btn s-btn-ghost" onClick={() => setAttachModal(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {toast ? (
        <div className="s-toast" role="status">
          {toast}
        </div>
      ) : null}
    </div>
  );
}
