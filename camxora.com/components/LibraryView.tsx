"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Icon } from "@/components/Icon";
import { TrackRail } from "@/components/TrackRail";
import { ReportClipModal } from "@/components/ReportClipModal";
import { ShareClipModal } from "@/components/ShareClipModal";
import { SongDetailsModal } from "@/components/SongDetailsModal";
import {
  SMenu,
  SMenuCheckboxItem,
  SMenuItem,
  SMenuSub,
  SMenuSubContent,
  SMenuSubTrigger,
  SMenuRadioGroup,
  SMenuRadioItem,
  SMenuSeparator,
} from "@/components/ui/s-menu";
import { useAuth } from "@/components/AuthProvider";
import { usePlayer } from "@/components/PlayerProvider";
import {
  fetchLikedTracks,
  type LikedTrack,
  type WebMusicClip,
  type WebMusicGeneration,
} from "@/lib/library-api";
import {
  addWebMusicPlaylistItem,
  createWebMusicPlaylist,
  createWebMusicWorkspace,
  deleteWebMusicGeneration,
  restoreWebMusicGeneration,
  setWebMusicTrash,
  coverWebMusicGeneration,
  reportWebMusicGeneration,
  radioWebMusicGeneration,
  deleteWebMusicPlaylist,
  fetchWebMusicLikedKeys,
  fetchWebMusicDislikedKeys,
  dislikeWebMusicGeneration,
  getWebMusicGeneration,
  likeWebMusicGeneration,
  listWebMusicGenerations,
  listWebMusicPlaylistItems,
  listWebMusicPlaylists,
  listWebMusicStudioProjects,
  listWebMusicWorkspaces,
  unlockWebMusicPreview,
  updateWebMusicGeneration,
  updateWebMusicGenerationTitle,
  type WebMusicPlaylistItem,
  type WebMusicPlaylistSummary,
  type WebMusicStudioProject,
  type WebMusicWorkspace,
} from "@/lib/web-music-api";
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
  type ClipDownloadKind,
} from "@/lib/clip-utils";

const PAGE_SIZE = 50;

/** Badge tone for the model label (one colour per V6 variant), matching Create. */
function modelBadgeTone(model?: string | null): "pro" | "mini" | "wild" {
  const value = String(model ?? "").toUpperCase().replace(/[\s-]/g, "_");
  if (value.includes("WILD")) return "wild";
  if (value.includes("MINI")) return "mini";
  return "pro";
}

const TABS = [
  { id: "songs", label: "Songs" },
  { id: "playlists", label: "Playlists" },
  { id: "albums", label: "Albums" },
  { id: "workspaces", label: "Workspaces" },
  { id: "projects", label: "Studio Projects" },
  { id: "covers", label: "Cover Art" },
  { id: "hooks", label: "Hooks" },
  { id: "likedHooks", label: "Liked Hooks" },
  { id: "history", label: "History" },
  { id: "trash", label: "Trash" },
] as const;

type LibTab = (typeof TABS)[number]["id"];

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

type LibRow = {
  song: WebMusicGeneration;
  clip: WebMusicClip;
  key: string;
  title: string;
  ready: boolean;
  duration: number;
  createdAt: number;
  liked: boolean;
  disliked: boolean;
};

type ConfirmState =
  | { kind: "generations"; ids: string[]; permanent?: boolean; variant?: "ok" | "alt" }
  | { kind: "playlist"; playlist: WebMusicPlaylistSummary }
  | null;

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

const SORT_OPTIONS: Array<{ id: FeedSort; label: string }> = [
  { id: "new", label: "Newest" },
  { id: "old", label: "Oldest" },
  { id: "most", label: "Most liked" },
  { id: "least", label: "Least liked" },
];

const DOWNLOAD_KINDS: Array<{ kind: ClipDownloadKind; label: string }> = [
  { kind: "mp3", label: "Download MP3" },
  { kind: "wav", label: "Download WAV" },
  { kind: "lrc", label: "Download LRC" },
  { kind: "srt", label: "Download SRT" },
];

function errorText(result: PromiseSettledResult<unknown>, fallback: string): string {
  return result.status === "rejected" && result.reason instanceof Error
    ? result.reason.message
    : fallback;
}

export function LibraryView({ initialTab }: { initialTab?: LibTab } = {}) {
  const { user, loading: authLoading } = useAuth();
  const { playTrack, enqueue } = usePlayer();
  const mounted = useRef(true);

  const [tab, setTab] = useState<LibTab>(initialTab ?? "songs");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<FeedFilter[]>([]);
  const [sort, setSort] = useState<FeedSort>("new");
  const [page, setPage] = useState(1);

  const [bootLoading, setBootLoading] = useState(true);
  const [loadingGenerations, setLoadingGenerations] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  const [generations, setGenerations] = useState<WebMusicGeneration[]>([]);
  const [totalGenerations, setTotalGenerations] = useState(0);
  const [playlists, setPlaylists] = useState<WebMusicPlaylistSummary[]>([]);
  const [workspaces, setWorkspaces] = useState<WebMusicWorkspace[]>([]);
  const [projects, setProjects] = useState<WebMusicStudioProject[]>([]);
  const [likedTracks, setLikedTracks] = useState<LikedTrack[]>([]);
  const [likedKeys, setLikedKeys] = useState<string[]>([]);
  const [dislikedKeys, setDislikedKeys] = useState<string[]>([]);

  const [trashMode, setTrashMode] = useState(false);
  const [trashItems, setTrashItems] = useState<WebMusicGeneration[]>([]);
  const [trashLoading, setTrashLoading] = useState(false);
  const [trashSelected, setTrashSelected] = useState<string[]>([]);
  const [trashCount, setTrashCount] = useState(0);
  const [reportTarget, setReportTarget] = useState<
    { song: WebMusicGeneration; variant: "ok" | "alt" } | null
  >(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [detailsTarget, setDetailsTarget] = useState<
    { song: WebMusicGeneration; variant: "ok" | "alt" } | null
  >(null);
  const [detailsBusy, setDetailsBusy] = useState(false);
  const [shareTarget, setShareTarget] = useState<
    { song: WebMusicGeneration; clip: WebMusicClip } | null
  >(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [attachNotice, setAttachNotice] = useState<null | "upload" | "record">(null);

  const [detailOpen, setDetailOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [detail, setDetail] = useState<WebMusicGeneration | null>(null);
  const [detailVariant, setDetailVariant] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [playlistDetail, setPlaylistDetail] = useState<WebMusicPlaylistSummary | null>(null);
  const [playlistItems, setPlaylistItems] = useState<WebMusicPlaylistItem[]>([]);
  const [playlistItemsLoading, setPlaylistItemsLoading] = useState(false);
  const [playlistError, setPlaylistError] = useState("");

  const [composer, setComposer] = useState<null | "playlist" | "workspace">(null);
  const [composerName, setComposerName] = useState("");
  const [composerBusy, setComposerBusy] = useState(false);

  const [confirm, setConfirm] = useState<ConfirmState>(null);
  const [deleting, setDeleting] = useState(false);
  const [toast, setToast] = useState("");

  const tabListRef = useRef<HTMLDivElement | null>(null);
  const [indicator, setIndicator] = useState({ left: 0, width: 0 });
  const [tabsOverflow, setTabsOverflow] = useState(false);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      window.location.href = "/login?next=/library";
      return;
    }
    let active = true;
    setBootLoading(true);
    setLoadingGenerations(true);
    setError("");
    void (async () => {
      const [gens, pls, wss, prjs, liked, keys, disliked] = await Promise.allSettled([
        listWebMusicGenerations(PAGE_SIZE, 0),
        listWebMusicPlaylists(),
        listWebMusicWorkspaces(),
        listWebMusicStudioProjects(),
        fetchLikedTracks(50),
        fetchWebMusicLikedKeys(),
        fetchWebMusicDislikedKeys(),
      ] as const);
      if (!active) return;
      const problems: string[] = [];

      if (gens.status === "fulfilled") {
        setGenerations(gens.value.items);
        setTotalGenerations(gens.value.total);
      } else {
        problems.push(errorText(gens, "Could not load your songs"));
      }
      if (pls.status === "fulfilled") setPlaylists(pls.value.items);
      else problems.push(errorText(pls, "Could not load your playlists"));
      if (wss.status === "fulfilled") setWorkspaces(wss.value.items);
      else problems.push(errorText(wss, "Could not load your workspaces"));
      if (prjs.status === "fulfilled") setProjects(prjs.value.items);
      else problems.push(errorText(prjs, "Could not load studio projects"));
      if (liked.status === "fulfilled") setLikedTracks(liked.value);
      else problems.push(errorText(liked, "Could not load liked tracks"));
      if (keys.status === "fulfilled") setLikedKeys(keys.value);
      else problems.push(errorText(keys, "Could not load your likes"));
      if (disliked.status === "fulfilled") setDislikedKeys(disliked.value);

      if (problems.length) setError(problems[0]);
      setBootLoading(false);
      setLoadingGenerations(false);
    })();
    return () => {
      active = false;
    };
  }, [authLoading, user]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2400);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    setPage(1);
  }, [tab, search, filters, sort]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("trash") === "1") setTrashMode(true);
  }, []);

  useEffect(() => {
    setTrashMode(tab === "trash");
  }, [tab]);

  useEffect(() => {
    let active = true;
    listWebMusicGenerations(1, 0, undefined, true)
      .then((page) => {
        if (active) setTrashCount(page.total);
      })
      .catch(() => {
        /* count is cosmetic */
      });
    return () => {
      active = false;
    };
  }, [trashMode, tab]);

  useEffect(() => {
    if (!trashMode) return;
    let active = true;
    setTrashLoading(true);
    listWebMusicGenerations(100, 0, undefined, true)
      .then((page) => {
        if (active) setTrashItems(page.items);
      })
      .catch(() => {
        if (active) setTrashItems([]);
      })
      .finally(() => {
        if (active) setTrashLoading(false);
      });
    return () => {
      active = false;
    };
  }, [trashMode]);

  useEffect(() => {
    const measure = () => {
      const list = tabListRef.current;
      if (!list) return;
      const active = list.querySelector<HTMLElement>('[aria-selected="true"]');
      if (!active) return;
      setIndicator({ left: active.offsetLeft, width: active.offsetWidth });
      setTabsOverflow(list.scrollWidth > list.clientWidth + 1);
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [tab, authLoading, bootLoading, detailOpen]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      closeDetail();
      setAttachNotice(null);
      setComposer(null);
      setConfirm(null);
      setPlaylistDetail(null);
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  useEffect(() => {
    if (bootLoading || !user) return;
    const params = new URLSearchParams(window.location.search);
    const clipId = params.get("clip");
    if (!clipId) return;
    const variant = params.get("variant") || undefined;
    void openDetailById(clipId, variant);
    // Deep link is only read once per load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bootLoading, user]);

  async function loadGenerations(offset = 0) {
    if (offset === 0) setLoadingGenerations(true);
    else setLoadingMore(true);
    try {
      const pageData = await listWebMusicGenerations(PAGE_SIZE, offset);
      if (!mounted.current) return;
      setGenerations((current) => {
        if (offset === 0) return pageData.items;
        const seen = new Set(current.map((item) => item.id));
        return [...current, ...pageData.items.filter((item) => !seen.has(item.id))];
      });
      setTotalGenerations(pageData.total);
    } catch (cause) {
      if (mounted.current) {
        setError(cause instanceof Error ? cause.message : "Could not load your songs");
      }
    } finally {
      if (mounted.current) {
        setLoadingGenerations(false);
        setLoadingMore(false);
      }
    }
  }

  const isLikedRow = (song: WebMusicGeneration, clip: WebMusicClip) =>
    likedKeys.includes(clipTrackKey(song.id, clip.variant));
  const isDislikedRow = (song: WebMusicGeneration, clip: WebMusicClip) =>
    dislikedKeys.includes(clipTrackKey(song.id, clip.variant));

  const allRows: LibRow[] = generations.flatMap((song) =>
    generationClips(song)
      .filter((clip) => ![...(song.trashed_variants ?? []), ...(song.purged_variants ?? [])].includes(clip.variant))
      .map((clip) => ({
      song,
      clip,
      key: clipTrackKey(song.id, clip.variant),
      title: clip.title || song.title || "Untitled",
      ready: clipIsReady(song, clip),
      duration: Math.round(clip.duration_seconds || 0),
      createdAt: song.created_at ? new Date(song.created_at).getTime() : 0,
      liked: isLikedRow(song, clip),
      disliked: isDislikedRow(song, clip),
    }))
  );

  const searchTerm = search.trim().toLowerCase();

  const filteredRows = allRows.filter((row) => {
    if (searchTerm) {
      const haystack =
        `${row.title} ${row.song.style || ""} ${row.song.lyrics || ""}`.toLowerCase();
      if (!haystack.includes(searchTerm)) return false;
    }
    if (filters.includes("liked") && !row.liked) return false;
    if (filters.includes("disliked") && !row.disliked) return false;
    if (filters.includes("hideDisliked") && row.disliked) return false;
    if (filters.includes("downloads") && !row.ready) return false;
    if (filters.includes("full") && row.duration > 0 && row.duration < 60) return false;
    return true;
  });

  const sortedRows = [...filteredRows].sort((a, b) => {
    if (sort === "old") return a.createdAt - b.createdAt;
    if (sort === "most") {
      const diff = Number(b.liked) - Number(a.liked);
      return diff || b.createdAt - a.createdAt;
    }
    if (sort === "least") {
      const diff = Number(a.liked) - Number(b.liked);
      return diff || b.createdAt - a.createdAt;
    }
    return b.createdAt - a.createdAt;
  });

  const rowSource =
    tab === "history"
      ? [...filteredRows].sort((a, b) => b.createdAt - a.createdAt)
      : sortedRows;

  const filteredLiked = likedTracks.filter((track) => {
    if (!searchTerm) return true;
    return `${track.title} ${track.artist_name || ""}`.toLowerCase().includes(searchTerm);
  });

  const filteredPlaylists = playlists.filter(
    (playlist) => !searchTerm || playlist.name.toLowerCase().includes(searchTerm)
  );
  const filteredWorkspaces = workspaces.filter(
    (workspace) => !searchTerm || workspace.name.toLowerCase().includes(searchTerm)
  );
  const filteredProjects = projects.filter(
    (project) => !searchTerm || project.title.toLowerCase().includes(searchTerm)
  );

  const isRowTab = tab === "songs" || tab === "history" || tab === "covers";
  const activeCount = tab === "likedHooks" ? filteredLiked.length : isRowTab ? rowSource.length : 0;
  const pageCount = Math.max(1, Math.ceil(activeCount / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageSlice = [(currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE] as const;
  const pageRows = isRowTab ? rowSource.slice(pageSlice[0], pageSlice[1]) : [];
  const likedPageRows =
    tab === "likedHooks" ? filteredLiked.slice(pageSlice[0], pageSlice[1]) : [];

  const coverRows = pageRows.filter(
    (row, index, all) =>
      Boolean(row.clip.image_url) &&
      all.findIndex((item) => item.clip.image_url === row.clip.image_url) === index
  );

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  const activeFilterCount = filters.length;
  const selectedClip =
    detail && detail.clips?.length
      ? detail.clips.find((clip) => clip.variant === detailVariant) ?? detail.clips[0]
      : detail
        ? generationClips(detail)[0]
        : null;
  const detailReady = detail && selectedClip ? clipIsReady(detail, selectedClip) : false;
  const detailCover = selectedClip?.image_url || "/hero.png";
  const detailInstrumental = detail ? generationIsInstrumental(detail) : false;
  const sortLabel = SORT_OPTIONS.find((option) => option.id === sort)?.label ?? "Newest";
  const showPager =
    !bootLoading &&
    (tab === "songs" || tab === "history" || tab === "covers" || tab === "likedHooks") &&
    activeCount > 0;

  function playClip(song: WebMusicGeneration, clip: WebMusicClip) {
    if (!clipIsReady(song, clip)) return;
    const variant = clip.variant || "ok";
    const audioUrl =
      clip.audio_url ||
      clip.download_url ||
      `/api/v3/web-music/generations/${song.id}/stream/${variant}`;
    if (!audioUrl) return;
    playTrack({
      title: clip.title || song.title || "Untitled",
      artist: "You",
      cover: clip.image_url || "/hero.png",
      duration: Math.max(1, Math.round(clip.duration_seconds || 180)),
      audioUrl,
    });
  }

  function playLiked(track: LikedTrack) {
    playTrack({
      title: track.title,
      artist: track.artist_name || "Camxora",
      cover: track.cover_url || "/hero.png",
      duration: Math.max(1, Math.round(track.duration_seconds || 180)),
      audioUrl: `/api/v3/streaming/tracks/${encodeURIComponent(track.id)}/stream`,
    });
  }

  function playPlaylistItem(item: WebMusicPlaylistItem) {
    if (!item.audio_url) return;
    playTrack({
      title: item.title || "Untitled",
      artist: "You",
      cover: item.image_url || "/hero.png",
      duration: 180,
      audioUrl: item.audio_url,
    });
  }

  async function toggleLike(song: WebMusicGeneration, clip: WebMusicClip) {
    const key = clipTrackKey(song.id, clip.variant);
    const nextLiked = !likedKeys.includes(key);
    setLikedKeys((current) =>
      nextLiked ? [...current, key] : current.filter((item) => item !== key)
    );
    if (nextLiked) {
      setDislikedKeys((current) => current.filter((item) => item !== key));
    }
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

  async function toggleDislike(song: WebMusicGeneration, clip: WebMusicClip) {
    const key = clipTrackKey(song.id, clip.variant);
    const nextDisliked = !dislikedKeys.includes(key);
    setDislikedKeys((current) =>
      nextDisliked ? [...current, key] : current.filter((item) => item !== key)
    );
    if (nextDisliked) {
      setLikedKeys((current) => current.filter((item) => item !== key));
    }
    setToast(nextDisliked ? "Noted — fewer like this" : "Dislike removed");
    try {
      await dislikeWebMusicGeneration(song.id, clip.variant, nextDisliked);
    } catch {
      setDislikedKeys((current) =>
        nextDisliked ? current.filter((item) => item !== key) : [...current, key]
      );
      setToast("Could not update dislike");
    }
  }

  async function submitReport(input: {
    reason: Parameters<typeof reportWebMusicGeneration>[1]["reason"];
    details: string;
  }) {
    if (!reportTarget) return;
    setReportBusy(true);
    try {
      await reportWebMusicGeneration(reportTarget.song.id, {
        variant: reportTarget.variant,
        reason: input.reason,
        details: input.details,
      });
      setToast("Report sent — thanks");
      setReportTarget(null);
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : "Could not send the report");
    } finally {
      if (mounted.current) setReportBusy(false);
    }
  }

  async function submitSongDetails(input: { title: string; lyrics: string }) {
    if (!detailsTarget) return;
    setDetailsBusy(true);
    try {
      const updated = await updateWebMusicGeneration(detailsTarget.song.id, {
        title: input.title,
        lyrics: input.lyrics,
        variant: detailsTarget.variant,
      });
      setGenerations((current) =>
        current.map((item) => (item.id === updated.id ? updated : item))
      );
      setDetail((current) => (current && current.id === updated.id ? updated : current));
      setToast("Song details saved");
      setDetailsTarget(null);
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : "Could not save the details");
    } finally {
      if (mounted.current) setDetailsBusy(false);
    }
  }

  async function coverFromLibrary(song: WebMusicGeneration, clip: WebMusicClip) {
    try {
      await coverWebMusicGeneration(song.id, {
        variant: clip.variant === "alt" ? "alt" : "ok",
        prompt: (song.style || song.title || "").trim(),
      });
      setToast("Cover started — it will appear in your library");
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : "Could not cover this song");
    }
  }

  function enqueueClip(song: WebMusicGeneration, clip: WebMusicClip) {
    if (appendClipToQueue(song, clip)) setToast("Added to queue");
  }

  function appendClipToQueue(
    song: WebMusicGeneration,
    clip: WebMusicClip
  ): boolean {
    const variant = clip.variant || "ok";
    const audioUrl =
      clip.audio_url ||
      clip.download_url ||
      `/api/v3/web-music/generations/${song.id}/stream/${variant}`;
    if (!audioUrl) return false;
    enqueue({
      title: clip.title || song.title || "Untitled",
      artist: "You",
      cover: clip.image_url || "/hero.png",
      duration: Math.max(1, Math.round(clip.duration_seconds || 180)),
      audioUrl,
    });
    return true;
  }

  /** Suno's "Song Radio": play this song, then keep queueing similar ones. */
  async function startRadio(song: WebMusicGeneration, clip: WebMusicClip) {
    try {
      const station = await radioWebMusicGeneration(song.id, 20);
      playClip(song, clip);
      for (const item of station.items) {
        const match = generationClips(item).find(
          (candidate) => candidate.ready && candidate.audio_url
        );
        if (match) appendClipToQueue(item, match);
      }
      setToast(
        station.items.length
          ? `Song Radio started — ${station.items.length} songs queued`
          : "Song Radio started — no similar songs yet"
      );
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : "Could not start Song Radio");
    }
  }

  async function addClipToPlaylist(
    song: WebMusicGeneration,
    clip: WebMusicClip,
    playlist: WebMusicPlaylistSummary
  ) {
    try {
      await addWebMusicPlaylistItem(playlist.id, song.id, clip.variant);
      setToast(`Added to ${playlist.name}`);
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : "Could not add to playlist");
    }
  }

  async function copyClipLink(song: WebMusicGeneration, clip: WebMusicClip) {
    const url = `${window.location.origin}/library?clip=${encodeURIComponent(
      song.id
    )}&variant=${encodeURIComponent(clip.variant)}`;
    try {
      await navigator.clipboard.writeText(url);
      setToast("Link copied");
    } catch {
      setToast(url);
    }
  }

  function openDetail(song: WebMusicGeneration, clip: WebMusicClip) {
    setDetail(song);
    setDetailId(song.id);
    setDetailVariant(clip.variant);
    setDetailOpen(true);
    const url = new URL(window.location.href);
    url.searchParams.set("clip", song.id);
    url.searchParams.set("variant", clip.variant);
    window.history.replaceState({}, "", url.toString());
    void openDetailById(song.id, clip.variant);
  }

  function closeDetail() {
    setDetailOpen(false);
    const url = new URL(window.location.href);
    url.searchParams.delete("clip");
    url.searchParams.delete("variant");
    window.history.replaceState({}, "", url.toString());
  }

  async function openDetailById(id: string, variant?: string) {
    setDetailId(id);
    setDetailOpen(true);
    setDetailLoading(true);
    if (variant) setDetailVariant(variant);
    try {
      const next = await getWebMusicGeneration(id);
      if (!mounted.current) return;
      setDetail(next);
      setDetailVariant(
        (current) => variant ?? current ?? next.clips?.[0]?.variant ?? "ok"
      );
      setGenerations((current) => current.map((item) => (item.id === next.id ? next : item)));
    } catch (cause) {
      if (mounted.current) {
        setToast(cause instanceof Error ? cause.message : "Could not load this track");
      }
    } finally {
      if (mounted.current) setDetailLoading(false);
    }
  }

  async function unlockPreview() {
    if (!detail) return;
    setDetailLoading(true);
    try {
      const updated = await unlockWebMusicPreview(detail.id);
      if (!mounted.current) return;
      setDetail(updated);
      setGenerations((current) =>
        current.map((item) => (item.id === updated.id ? updated : item))
      );
      setToast("Full song unlocked");
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : "Could not unlock this track");
    } finally {
      if (mounted.current) setDetailLoading(false);
    }
  }

  async function deleteGenerations(
    ids: string[],
    permanent = false,
    variant?: "ok" | "alt"
  ) {
    setConfirm(null);
    if (!ids.length || deleting) return;
    setDeleting(true);
    const deleted: string[] = [];
    const failures: string[] = [];
    for (const id of ids) {
      try {
        await deleteWebMusicGeneration(id, { permanent, variant });
        deleted.push(id);
      } catch (cause) {
        failures.push(cause instanceof Error ? cause.message : "Could not delete song");
      }
    }
    if (!mounted.current) return;
    const gone = new Set(deleted);
    if (permanent) {
      setGenerations((current) => current.filter((item) => !gone.has(item.id)));
      setTrashItems((current) => current.filter((item) => !gone.has(item.id)));
      setTotalGenerations((current) => Math.max(0, current - deleted.length));
    } else if (variant) {
      // Soft-deleting one version: keep the song, hide only that clip.
      setGenerations((current) => {
        let removed = 0;
        const next = current
          .map((item) =>
            gone.has(item.id)
              ? {
                  ...item,
                  trashed_variants: Array.from(
                    new Set([...(item.trashed_variants ?? []), variant])
                  ),
                }
              : item
          )
          .filter((item) => {
            const fullyTrashed = (item.trashed_variants ?? []).length >= 2;
            if (fullyTrashed) removed += 1;
            return !fullyTrashed;
          });
        setTotalGenerations((total) => Math.max(0, total - removed));
        return next;
      });
    } else {
      setGenerations((current) => current.filter((item) => !gone.has(item.id)));
      setTotalGenerations((current) => Math.max(0, current - deleted.length));
    }
    setSelectedIds((current) => current.filter((id) => !gone.has(id)));
    if (detailId && gone.has(detailId) && !variant) {
      closeDetail();
      setDetail(null);
      setDetailId(null);
      setDetailVariant(null);
    }
    setDeleting(false);
    setToast(
      permanent
        ? deleted.length === 1
          ? "Deleted permanently"
          : `${deleted.length} songs deleted permanently`
        : variant
          ? `${variant === "alt" ? "Version 2" : "Version 1"} moved to Trash`
          : deleted.length === 1
            ? "Moved to Trash"
            : `${deleted.length} songs moved to Trash`
    );
    if (failures.length) setError(failures[0]);
    if (!deleted.length) setToast("Could not delete song");
  }

  async function deletePlaylist(playlist: WebMusicPlaylistSummary) {
    setConfirm(null);
    if (deleting) return;
    setDeleting(true);
    try {
      await deleteWebMusicPlaylist(playlist.id);
      if (!mounted.current) return;
      setPlaylists((current) => current.filter((item) => item.id !== playlist.id));
      if (playlistDetail?.id === playlist.id) setPlaylistDetail(null);
      setToast("Playlist deleted");
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : "Could not delete playlist");
    } finally {
      if (mounted.current) setDeleting(false);
    }
  }

  async function openPlaylist(playlist: WebMusicPlaylistSummary) {
    setPlaylistDetail(playlist);
    setPlaylistItems([]);
    setPlaylistError("");
    setPlaylistItemsLoading(true);
    try {
      const payload = await listWebMusicPlaylistItems(playlist.id);
      if (mounted.current) setPlaylistItems(payload.items);
    } catch (cause) {
      if (mounted.current) {
        setPlaylistError(cause instanceof Error ? cause.message : "Could not load this playlist");
      }
    } finally {
      if (mounted.current) setPlaylistItemsLoading(false);
    }
  }

  async function submitComposer() {
    const name = composerName.trim();
    if (!composer || !name || composerBusy) return;
    setComposerBusy(true);
    try {
      if (composer === "playlist") {
        const created = await createWebMusicPlaylist(name);
        if (!mounted.current) return;
        setPlaylists((current) => [created, ...current]);
        setToast(`Created playlist "${created.name}"`);
      } else {
        const created = await createWebMusicWorkspace(name);
        if (!mounted.current) return;
        setWorkspaces((current) => [...current, created]);
        setToast(`Created workspace "${created.name}"`);
      }
      setComposer(null);
      setComposerName("");
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : "Could not create");
    } finally {
      if (mounted.current) setComposerBusy(false);
    }
  }

  function toggleTrash() {
    setSelectedIds([]);
    setTab(trashMode ? "songs" : "trash");
  }

  function toggleSelected(id: string) {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
    );
  }

  function selectAllVisible() {
    setSelectedIds(Array.from(new Set(pageRows.map((row) => row.song.id))));
  }

  function clearFilters() {
    setSearch("");
    setFilters([]);
  }

  const skeletonRows = (
    <>
      {[0, 1, 2, 3, 4].map((item) => (
        <div className="s-skel" key={item}>
          <span className="a" />
          <span className="b">
            <i />
            <i />
          </span>
        </div>
      ))}
    </>
  );

  const renderEmpty = (icon: string, title: string, copy: string, action?: ReactNode) => (
    <div className="s-empty">
      <span className="ico">
        <Icon name={icon} />
      </span>
      <b>{title}</b>
      <p>{copy}</p>
      {action}
    </div>
  );

  const noResults = renderEmpty(
    "fa-magnifying-glass",
    "No results",
    "Try a different search or clear your filters.",
    <button type="button" className="s-btn s-btn-secondary" onClick={clearFilters}>
      Clear filters
    </button>
  );

  const hasSearch = Boolean(searchTerm) || activeFilterCount > 0;

  const renderClipRow = (row: LibRow) => {
    const { song, clip, key, title, ready, duration, liked, disliked } = row;
    const failed = !ready && /fail|error|cancel/i.test(String(song.status ?? ""));
    const selectedForTrash = trashMode && selectedIds.includes(song.id);
    return (
      <div
        className={`s-row${selectedForTrash ? " selected" : ""}${failed ? " failed" : ""}`}
        key={key}
        role="group"
        aria-label={title}
        onClick={() => {
          if (trashMode) toggleSelected(song.id);
          else openDetail(song, clip);
        }}
      >
        {trashMode ? (
          <button
            type="button"
            className={`s-selectbox${selectedForTrash ? " on" : ""}`}
            aria-label={`Select ${title}`}
            aria-pressed={selectedForTrash}
            onClick={(event) => {
              event.stopPropagation();
              toggleSelected(song.id);
            }}
          >
            {selectedForTrash ? <Icon name="fa-check" /> : null}
          </button>
        ) : null}

        <button
          type="button"
          className="s-cover"
          aria-label={ready ? `Play ${title}` : "Song not ready"}
          onClick={(event) => {
            event.stopPropagation();
            if (ready) playClip(song, clip);
          }}
        >
          <img src={clip.image_url || "/hero.png"} alt="" loading="lazy" />
          <span className="s-cover-play">
            <span>
              <Icon
                name={ready ? "fa-play" : failed ? "fa-circle-xmark" : "fa-hourglass-half"}
                className={ready ? "" : failed ? "s-row-failed-icon" : "s-hourglass"}
              />
            </span>
          </span>
          {duration ? <span className="s-dur">{formatClipDuration(duration)}</span> : null}
        </button>

        <div className="s-row-body">
          <div className="s-row-title">
            <a
              href={`/library?clip=${encodeURIComponent(song.id)}&variant=${encodeURIComponent(
                clip.variant
              )}`}
              onClick={(event) => {
                event.preventDefault();
                openDetail(song, clip);
              }}
            >
              {title}
            </a>
            <span className={`s-model-badge ${modelBadgeTone(song.model || song.model_label)}`}>
              {song.model_label || song.model || "V6"}
            </span>
            {!ready ? (
              <span
                className={`s-status ${statusClass(song.status)}${failed ? " s-row-failed-text" : ""}`}
              >
                {statusLabel(song.status)}
              </span>
            ) : null}
            {song.is_preview ? <span className="s-status live">Preview</span> : null}
          </div>
          <div className="s-row-desc">
            {clipVersionLabel(clip.variant)} · {song.style || "No style tags"}
          </div>
          <div className="s-row-actions" onClick={(event) => event.stopPropagation()}>
            <button
              type="button"
              className="s-act"
              aria-label={ready ? `Play ${title}` : "Song not ready"}
              disabled={!ready}
              onClick={() => playClip(song, clip)}
            >
              <Icon name="fa-play" /> Play
            </button>
            <button
              type="button"
              className={`s-act icon-only${liked ? " on" : ""}`}
              aria-label={liked ? "Unlike clip" : "Like clip"}
              aria-pressed={liked}
              onClick={() => void toggleLike(song, clip)}
            >
              <Icon name="fa-heart" />
            </button>
            <button
              type="button"
              className={`s-act icon-only${disliked ? " on" : ""}`}
              aria-label={disliked ? "Remove dislike" : "Dislike clip"}
              aria-pressed={disliked}
              onClick={() => toggleDislike(song, clip)}
            >
              <Icon name="fa-thumbs-down" />
            </button>
            {ready ? (
              <>
                <a
                  className="s-act"
                  href={clipDownloadUrl(song.id, clip.variant || "ok", "mp3")}
                  download
                  aria-label="Download MP3"
                >
                  MP3
                </a>
                <a
                  className="s-act"
                  href={clipDownloadUrl(song.id, clip.variant || "ok", "wav")}
                  download
                  aria-label="Download WAV"
                >
                  WAV
                </a>
                <button
                  type="button"
                  className="s-act"
                  onClick={() => {
                    window.location.href = `/publish?clip=${encodeURIComponent(song.id)}&variant=${encodeURIComponent(clip.variant || "ok")}`;
                  }}
                >
                  <Icon name="fa-arrow-up-from-bracket" /> Publish
                </button>
              </>
            ) : null}
            <button
              type="button"
              className="s-act icon-only"
              aria-label="Share clip"
              title="Share"
              onClick={() => setShareTarget({ song, clip })}
            >
              <Icon name="fa-share" />
            </button>
            <Link
              className="s-act icon-only"
              href={`/create?remix=${encodeURIComponent(song.id)}&variant=${encodeURIComponent(clip.variant || "ok")}`}
              aria-label="Remix clip"
              title="Remix"
            >
              <Icon name="fa-wand-magic-sparkles" />
            </Link>
          </div>
        </div>

        <div
          className="s-anchor"
          style={{ position: "static" }}
          onClick={(event) => event.stopPropagation()}
        >
          <SMenu
            align="end"
            sideOffset={6}
            trigger={
              <button
                type="button"
                className="s-row-more"
                aria-label="More options"
              >
                <Icon name="fa-ellipsis-vertical" />
              </button>
            }
          >
            <SMenuItem onSelect={() => void copyClipLink(song, clip)}>
              <Icon name="fa-link" /> Copy link
            </SMenuItem>
            <SMenuItem onSelect={() => toggleDislike(song, clip)}>
              <Icon name="fa-thumbs-down" /> {disliked ? "Remove dislike" : "Dislike"}
            </SMenuItem>
            <SMenuSub>
              <SMenuSubTrigger>
                <Icon name="fa-repeat" /> Remix
              </SMenuSubTrigger>
              <SMenuSubContent>
                <SMenuItem
                  disabled={!ready}
                  onSelect={() => void coverFromLibrary(song, clip)}
                >
                  <Icon name="fa-retweet" /> Cover
                </SMenuItem>
                <SMenuItem
                  onSelect={() => {
                    const text = (song.style || song.lyrics || song.title || "").trim();
                    window.location.href = `/create?prompt=${encodeURIComponent(text)}`;
                  }}
                >
                  <Icon name="fa-quote-left" /> Reuse Prompt
                </SMenuItem>
                <SMenuItem
                  disabled={!ready}
                  onSelect={() =>
                    (window.location.href = `/create?mashup=${encodeURIComponent(
                      song.id
                    )}&variant=${encodeURIComponent(clip.variant || "ok")}`)
                  }
                >
                  <Icon name="fa-code-merge" /> Mashup
                </SMenuItem>
                <SMenuItem disabled title="Coming soon">
                  <Icon name="fa-waveform" /> Sample this song
                </SMenuItem>
                <SMenuItem disabled title="Coming soon">
                  <Icon name="fa-wand-sparkles" /> Use as Inspiration
                </SMenuItem>
                <SMenuItem
                  onSelect={() => {
                    window.location.href = `/create?remix=${encodeURIComponent(
                      song.id
                    )}&variant=${encodeURIComponent(clip.variant || "ok")}`;
                  }}
                >
                  <Icon name="fa-microphone-lines" /> Voice
                </SMenuItem>
              </SMenuSubContent>
            </SMenuSub>
            <SMenuSub>
              <SMenuSubTrigger>
                <Icon name="fa-pen-to-square" /> Edit
              </SMenuSubTrigger>
              <SMenuSubContent>
                <SMenuItem
                  onSelect={() =>
                    setDetailsTarget({
                      song,
                      variant: clip.variant === "alt" ? "alt" : "ok",
                    })
                  }
                >
                  <Icon name="fa-circle-info" /> Song Details
                </SMenuItem>
                <SMenuItem asChild>
                  <Link href="/studio/editor">
                    <Icon name="fa-table-columns" /> Open in Editor
                  </Link>
                </SMenuItem>
                <SMenuItem
                  disabled
                  title="Replace Section needs the section editor — coming soon"
                >
                  <Icon name="fa-scissors" /> Replace Section
                </SMenuItem>
                <SMenuItem disabled title="No crop service yet">
                  <Icon name="fa-crop-simple" /> Crop Song
                </SMenuItem>
              </SMenuSubContent>
            </SMenuSub>
            <SMenuItem disabled={!ready} onSelect={() => enqueueClip(song, clip)}>
              <Icon name="fa-bars-staggered" /> Add to Queue
            </SMenuItem>
            <SMenuSub>
              <SMenuSubTrigger>
                <Icon name="fa-list" /> Add to Playlist
              </SMenuSubTrigger>
              <SMenuSubContent>
                {playlists.length ? (
                  playlists.map((playlist) => (
                    <SMenuItem
                      key={playlist.id}
                      onSelect={() => void addClipToPlaylist(song, clip, playlist)}
                    >
                      <Icon name="fa-rectangle-list" /> {playlist.name}
                    </SMenuItem>
                  ))
                ) : (
                  <SMenuItem disabled>No playlists yet</SMenuItem>
                )}
              </SMenuSubContent>
            </SMenuSub>
            <SMenuItem disabled={!ready} onSelect={() => void startRadio(song, clip)}>
              <Icon name="fa-tower-broadcast" /> Song Radio
            </SMenuItem>
            <SMenuSeparator />
            <SMenuItem
              onSelect={() =>
                setReportTarget({
                  song,
                  variant: clip.variant === "alt" ? "alt" : "ok",
                })
              }
            >
              <Icon name="fa-flag" /> Report
            </SMenuItem>
            <SMenuSeparator />
            <SMenuItem
              onSelect={() =>
                setConfirm({
                  kind: "generations",
                  ids: [song.id],
                  variant: clip.variant === "alt" ? "alt" : "ok",
                })
              }
            >
              <Icon name="fa-trash" /> Move to Trash
            </SMenuItem>
            <SMenuSeparator />
            {DOWNLOAD_KINDS.filter(
              (format) =>
                format.kind === "mp3" ||
                format.kind === "wav" ||
                !generationIsInstrumental(song)
            ).map((format) => (
              <SMenuItem key={format.kind} asChild>
                <a
                  href={
                    format.kind === "mp3" && clip.download_url
                      ? clip.download_url
                      : clipDownloadUrl(song.id, clip.variant, format.kind)
                  }
                >
                  <Icon name="fa-download" /> {format.label}
                </a>
              </SMenuItem>
            ))}
            <SMenuSeparator />
            <SMenuItem
              onSelect={() => {
                window.location.href = `/publish?clip=${encodeURIComponent(song.id)}&variant=${encodeURIComponent(clip.variant || "ok")}`;
              }}
            >
              <Icon name="fa-arrow-up-from-bracket" /> Publish
            </SMenuItem>
            <SMenuItem asChild>
              <Link href="/studio/editor">
                <Icon name="fa-table-columns" /> Open in Studio
              </Link>
            </SMenuItem>
          </SMenu>
        </div>
      </div>
    );
  };

  const renderGridCard = (row: LibRow) => (
    <div
      className="s-card"
      key={row.key}
      role="button"
      tabIndex={0}
      onClick={() => openDetail(row.song, row.clip)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") openDetail(row.song, row.clip);
      }}
    >
      <div className="s-card-cover">
        <img src={row.clip.image_url || "/hero.png"} alt="" loading="lazy" />
      </div>
      <b>{row.title}</b>
      <small>{row.song.style || "No style tags"}</small>
    </div>
  );

  const renderLikedRow = (track: LikedTrack) => (
    <div
      className="s-row"
      key={track.id}
      role="group"
      aria-label={track.title}
      onClick={() => playLiked(track)}
    >
      <button
        type="button"
        className="s-cover"
        aria-label={`Play ${track.title}`}
        onClick={(event) => {
          event.stopPropagation();
          playLiked(track);
        }}
      >
        <img src={track.cover_url || "/hero.png"} alt="" loading="lazy" />
        <span className="s-cover-play">
          <span>
            <Icon name="fa-play" />
          </span>
        </span>
      </button>
      <div className="s-row-body">
        <div className="s-row-title">
          <b>{track.title}</b>
          <span className="s-tag">Hook</span>
        </div>
        <div className="s-row-desc">
          {track.artist_name || "Camxora"}
          {track.duration_seconds ? ` · ${formatClipDuration(track.duration_seconds)}` : ""}
          {track.added_at ? ` · ${formatDate(track.added_at)}` : ""}
        </div>
        <div className="s-row-actions" onClick={(event) => event.stopPropagation()}>
          <button
            type="button"
            className="s-act"
            aria-label={`Play ${track.title}`}
            onClick={() => playLiked(track)}
          >
            <Icon name="fa-play" /> Play
          </button>
        </div>
      </div>
    </div>
  );

  const renderPlaylistCard = (playlist: WebMusicPlaylistSummary) => (
    <button
      type="button"
      className="s-playlist"
      key={playlist.id}
      onClick={() => void openPlaylist(playlist)}
    >
      <span className="s-playlist-cover">
        <Icon name="fa-music" />
      </span>
      <b>{playlist.name}</b>
      <small>
        {playlist.song_count ?? 0} {playlist.song_count === 1 ? "track" : "tracks"} ·{" "}
        {playlist.is_public ? "Public" : "Private"}
      </small>
    </button>
  );

  async function reloadTrash() {
    try {
      const page = await listWebMusicGenerations(100, 0, undefined, true);
      if (mounted.current) setTrashItems(page.items);
    } catch {
      /* keep the current list */
    }
  }

  async function purgeTrashVersion(id: string, variant: string) {
    try {
      await deleteWebMusicGeneration(id, {
        permanent: true,
        variant: variant as "ok" | "alt",
      });
      if (!mounted.current) return;
      setTrashSelected((current) => current.filter((key) => key !== `${id}:${variant}`));
      await reloadTrash();
      setToast("Deleted permanently");
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : "Could not delete");
    }
  }

  async function purgeSelectedTrash() {
    if (!trashSelected.length) return;
    try {
      for (const key of trashSelected) {
        const [id, variant] = key.split(":");
        await deleteWebMusicGeneration(id, {
          permanent: true,
          variant: variant as "ok" | "alt",
        });
      }
      setTrashSelected([]);
      await reloadTrash();
      setToast("Deleted permanently");
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : "Could not delete");
    }
  }

  async function restoreSelectedTrash() {
    const keys = trashSelected;
    if (!keys.length) return;
    try {
      await setWebMusicTrash(keys, false);
      if (!mounted.current) return;
      setTrashItems((current) =>
        current
          .map((item) => {
            const remove = keys
              .filter((key) => key.startsWith(`${item.id}:`))
              .map((key) => key.split(":")[1]);
            return remove.length
              ? {
                  ...item,
                  trashed_variants: (item.trashed_variants ?? []).filter(
                    (value) => !remove.includes(value)
                  ),
                }
              : item;
          })
          .filter((item) => (item.trashed_variants ?? []).length > 0)
      );
      setTrashSelected([]);
      setToast("Restored to library");
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : "Could not restore");
    }
  }

  async function restoreSong(id: string, variant?: "ok" | "alt") {
    try {
      await restoreWebMusicGeneration(id, variant);
      if (!mounted.current) return;
      setTrashItems((current) =>
        current
          .map((item) =>
            item.id === id
              ? {
                  ...item,
                  trashed_variants: (item.trashed_variants ?? []).filter(
                    (value) => (variant ? value !== variant : false)
                  ),
                }
              : item
          )
          .filter((item) => (item.trashed_variants ?? []).length > 0)
      );
      setToast("Restored to library");
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : "Could not restore the song");
    }
  }

  const renderTrash = () => {
    if (trashLoading) return <p className="s-note">Loading Trashâ€¦</p>;
    if (!trashItems.length) {
      return renderEmpty(
        "fa-trash",
        "Trash is empty",
        "Songs you move to Trash land here first, so you can restore them.",
        <button
          type="button"
          className="s-btn s-btn-secondary"
          onClick={() => setTab("songs")}
        >
          Back to library
        </button>
      );
    }
    return (
      <div>
        {trashItems.flatMap((song) =>
          (song.trashed_variants ?? []).map((variant) => {
            const clip = generationClips(song).find((item) => item.variant === variant);
            const versionLabel = variant === "alt" ? "Version 2" : "Version 1";
            return (
              <div className="s-row" key={`${song.id}:${variant}`}>
                <button
                  type="button"
                  className={`s-selectbox${trashSelected.includes(`${song.id}:${variant}`) ? " on" : ""}`}
                  aria-label={`Select ${clip?.title || song.title}`}
                  aria-pressed={trashSelected.includes(`${song.id}:${variant}`)}
                  onClick={() =>
                    setTrashSelected((current) =>
                      current.includes(`${song.id}:${variant}`)
                        ? current.filter((key) => key !== `${song.id}:${variant}`)
                        : [...current, `${song.id}:${variant}`]
                    )
                  }
                >
                  {trashSelected.includes(`${song.id}:${variant}`) ? (
                    <Icon name="fa-check" />
                  ) : null}
                </button>
                <div className="s-row-body">
                  <div className="s-row-title">
                    <b>{clip?.title || song.title}</b>
                    <span className="s-row-version">· {versionLabel}</span>
                    <span className="s-model-badge">
                      {song.model_label || song.model || "V6"}
                    </span>
                  </div>
                  <div className="s-row-desc">
                    In Trash{song.created_at ? ` · ${formatDate(song.created_at)}` : ""}
                  </div>
                </div>
                <div className="s-trash-actions">
                  <button
                    type="button"
                    className="s-btn s-btn-sm s-btn-secondary"
                    onClick={() => void restoreSong(song.id, variant as "ok" | "alt")}
                    disabled={deleting}
                  >
                    <Icon name="fa-rotate-left" /> Restore to library
                  </button>
                  <button
                    type="button"
                    className="s-btn s-btn-sm s-danger-text"
                    onClick={() => void purgeTrashVersion(song.id, variant)}
                    disabled={deleting}
                  >
                    <Icon name="fa-trash" /> Delete permanently
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    );
  };

  const tabBody = () => {
    if (trashMode) return renderTrash();
    if (bootLoading) return skeletonRows;

    if (tab === "songs" || tab === "history") {
      if (!rowSource.length) {
        return hasSearch
          ? noResults
          : renderEmpty(
              tab === "history" ? "fa-clock" : "fa-music",
              tab === "history" ? "No history yet" : "No songs yet",
              tab === "history"
                ? "Your generation history will show up here."
                : "Describe a song or write lyrics, then hit Create.",
              <Link className="s-btn s-btn-primary" href="/create">
                <Icon name="fa-plus" /> Create a song
              </Link>
            );
      }
      return <>{pageRows.map(renderClipRow)}</>;
    }

    if (tab === "covers") {
      if (!coverRows.length) {
        return hasSearch
          ? noResults
          : renderEmpty(
              "fa-image",
              "No cover art yet",
              "Covers from your generated songs will collect here."
            );
      }
      return <div className="s-grid">{coverRows.map(renderGridCard)}</div>;
    }

    if (tab === "playlists") {
      return (
        <>
          <div className="s-playlists">
            <button
              type="button"
              className="s-playlist"
              onClick={() => {
                setComposerName("");
                setComposer("playlist");
              }}
            >
              <span className="s-playlist-cover">
                <Icon name="fa-plus" />
              </span>
              <b>New playlist</b>
              <small>Group your favourite tracks</small>
            </button>
            {filteredPlaylists.map(renderPlaylistCard)}
          </div>
          {!filteredPlaylists.length ? (
            <p className="s-note" style={{ padding: "8px 0" }}>
              {hasSearch ? "No playlists match your search." : "No playlists yet."}
            </p>
          ) : null}
        </>
      );
    }

    if (tab === "workspaces") {
      return (
        <>
          <div className="s-playlists">
            <button
              type="button"
              className="s-playlist"
              onClick={() => {
                setComposerName("");
                setComposer("workspace");
              }}
            >
              <span className="s-playlist-cover">
                <Icon name="fa-plus" />
              </span>
              <b>New workspace</b>
              <small>Keep projects and songs together</small>
            </button>
            {filteredWorkspaces.map((workspace) => (
              <div className="s-playlist" key={workspace.id}>
                <span className="s-playlist-cover">
                  <Icon name="fa-folder" />
                </span>
                <b>{workspace.name}</b>
                <small>
                  {workspace.is_default ? "Default workspace" : "Workspace"}
                  {workspace.created_at ? ` · ${formatDate(workspace.created_at)}` : ""}
                </small>
              </div>
            ))}
          </div>
          <p className="s-note" style={{ padding: "8px 0" }}>
            Choose a workspace from the Create page to save new songs into it.
          </p>
        </>
      );
    }

    if (tab === "projects") {
      if (!filteredProjects.length) {
        return hasSearch
          ? noResults
          : renderEmpty(
              "fa-table-columns",
              "No studio projects yet",
              "Save a project in the Studio editor and it will appear here.",
              <Link className="s-btn s-btn-secondary" href="/studio/editor">
                <Icon name="fa-table-columns" /> Open Studio
              </Link>
            );
      }
      return (
        <div className="s-playlists">
          {filteredProjects.map((project) => (
            <Link className="s-playlist" key={project.id} href="/studio/editor">
              <span className="s-playlist-cover">
                <Icon name="fa-table-columns" />
              </span>
              <b>{project.title}</b>
              <small>
                v{project.major_version} · {project.bpm} BPM · {project.time_signature}
                {project.updated_at ? ` · ${formatDate(project.updated_at)}` : ""}
              </small>
            </Link>
          ))}
        </div>
      );
    }

    if (tab === "likedHooks") {
      if (!filteredLiked.length) {
        return hasSearch
          ? noResults
          : renderEmpty(
              "fa-heart",
              "No liked hooks yet",
              "Tracks you like while listening will appear here."
            );
      }
      return <>{likedPageRows.map(renderLikedRow)}</>;
    }

    if (tab === "albums") {
      return renderEmpty(
        "fa-compact-disc",
        "No albums yet",
        "Albums published from the artist dashboard will appear here.",
        <Link className="s-btn s-btn-secondary" href="/artist-dashboard">
          Open artist dashboard
        </Link>
      );
    }

    return renderEmpty(
      "fa-wand-magic-sparkles",
      "Hooks are not enabled yet",
      "Short hook generation is not available in this workspace. Create a full song instead.",
      <Link className="s-btn s-btn-secondary" href="/create">
        Create a song
      </Link>
    );
  };

  if (authLoading) {
    return (
      <div className="s-page">
        <div className="s-lib">
          <div className="s-lib-head">
            <h1 className="s-lib-title">Library</h1>
          </div>
          <div className="s-lib-body">
            <div className="s-lib-tools" />
            {skeletonRows}
          </div>
        </div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="s-page">
      <div className="s-lib-shell">
        <div className="s-lib">
        <div className="s-lib-head">
          <h1 className="s-lib-title">Library</h1>
          <div className="s-lib-actions">
            <div className="s-anchor">
              <SMenu
                align="end"
                sideOffset={6}
                trigger={
                  <button type="button" className="s-pill" aria-label="Audio actions">
                    Audio <Icon name="fa-plus" />
                  </button>
                }
              >
                <SMenuItem onSelect={() => setAttachNotice("upload")}>
                  <Icon name="fa-arrow-up-from-bracket" /> Upload
                </SMenuItem>
                <SMenuItem onSelect={() => setAttachNotice("record")}>
                  <Icon name="fa-microphone" /> Record
                </SMenuItem>
              </SMenu>
            </div>
            <button
              type="button"
              className={`s-btn s-btn-icon${trashMode ? " s-btn-secondary" : ""}`}
              aria-label={trashMode ? "Exit trash" : "Open trash"}
              aria-pressed={trashMode}
              title="Trash"
              onClick={toggleTrash}
            >
              <Icon name="fa-trash" />
            </button>
          </div>
        </div>

        <div
          className={`s-tabs-sm${tabsOverflow ? " has-overflow" : ""}`}
          role="tablist"
          aria-label="Library sections"
          ref={tabListRef}
        >
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              className={`s-tab${tab === item.id ? " on" : ""}`}
              aria-selected={tab === item.id}
              onClick={() => setTab(item.id)}
            >
              {item.label}
              {item.id === "trash" && trashCount > 0 ? (
                <span className="s-tab-count">{trashCount}</span>
              ) : null}
            </button>
          ))}
          <span
            className="s-tab-indicator"
            aria-hidden="true"
            style={{ left: indicator.left, width: indicator.width }}
          />
        </div>

        {trashMode ? (
          <div className="s-lib-bar">
            <span className="s-note">{trashSelected.length} selected</span>
            <span className="s-spacer" />
            <button
              type="button"
              className="s-btn s-btn-sm s-btn-secondary"
              onClick={() => void restoreSelectedTrash()}
              disabled={!trashSelected.length || deleting}
            >
              <Icon name="fa-rotate-left" /> Restore selected
            </button>
            <button
              type="button"
              className="s-btn s-btn-sm s-danger-text"
              onClick={() => void purgeSelectedTrash()}
              disabled={!trashSelected.length || deleting}
            >
              <Icon name="fa-trash" /> Delete permanently
            </button>
            <button
              type="button"
              className="s-btn s-btn-sm s-danger-text"
              onClick={() =>
                setConfirm({
                  kind: "generations",
                  ids: trashItems.map((item) => item.id),
                  permanent: true,
                })
              }
              disabled={!trashItems.length || deleting}
            >
              <Icon name="fa-trash" /> Empty Trash
            </button>
            <button
              type="button"
              className="s-btn s-btn-sm s-btn-ghost"
              onClick={() => {
                setTab("songs");
              }}
            >
              Close
            </button>
          </div>
        ) : null}

        <div className="s-lib-tools">
          <label className="s-search">
            <Icon name="fa-magnifying-glass" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search"
              aria-label="Search library"
            />
          </label>

          <div className="s-anchor">
            <SMenu
              align="end"
              sideOffset={6}
              trigger={
                <button
                  type="button"
                  className={`s-pill${activeFilterCount ? " on" : ""}`}
                  aria-label={`Filters (${activeFilterCount})`}
                >
                  <Icon name="fa-filter" /> <span className="s-btn-label">Filters{activeFilterCount ? ` (${activeFilterCount})` : ""}</span>
                </button>
              }
            >
              {filterOptions.map((option) => {
                const on = filters.includes(option.id);
                return (
                  <SMenuCheckboxItem
                    key={option.id}
                    className={on ? "on" : undefined}
                    checked={on}
                    disabled={option.disabled}
                    onCheckedChange={() =>
                      setFilters((current) =>
                        current.includes(option.id)
                          ? current.filter((item) => item !== option.id)
                          : [...current, option.id]
                      )
                    }
                  >
                    {option.label}
                  </SMenuCheckboxItem>
                );
              })}
            </SMenu>
          </div>

          <div className="s-anchor">
            <SMenu
              align="end"
              sideOffset={6}
              trigger={
                <button type="button" className="s-pill" aria-label={`Sort: ${sortLabel}`}>
                  {sortLabel}
                  <Icon name="fa-chevron-down" />
                </button>
              }
            >
              <SMenuRadioGroup
                value={sort}
                onValueChange={(value) => setSort(value as typeof sort)}
              >
                {SORT_OPTIONS.map((option) => (
                  <SMenuRadioItem key={option.id} value={option.id}>
                    {option.label}
                  </SMenuRadioItem>
                ))}
              </SMenuRadioGroup>
            </SMenu>
          </div>

          <button
            type="button"
            className={`s-pill${filters.includes("liked") ? " on" : ""}`}
            aria-pressed={filters.includes("liked")}
            onClick={() =>
              setFilters((current) =>
                current.includes("liked")
                  ? current.filter((item) => item !== "liked")
                  : [...current, "liked"]
              )
            }
          >
            Liked
          </button>
          <button
            type="button"
            className="s-pill"
            disabled
            title="Public visibility is not available yet"
          >
            Public
          </button>
          <button
            type="button"
            className="s-pill"
            disabled
            title="Uploads are not available yet"
          >
            Uploads
          </button>
        </div>

        {error ? (
          <p className="s-error" role="alert">
            {error}
          </p>
        ) : null}

        <div className="s-lib-body">{tabBody()}</div>

        {showPager ? (
          <div className="s-lib-foot">
            <span className="s-note">Page</span>
            <div className="s-pager">
              <input
                aria-label="Page number"
                value={currentPage}
                onChange={(event) => {
                  const next = Number(event.target.value.replace(/\D/g, "")) || 1;
                  setPage(Math.min(pageCount, Math.max(1, next)));
                }}
              />
              <button
                type="button"
                aria-label="Previous page"
                onClick={() => setPage((value) => Math.max(1, value - 1))}
                disabled={currentPage <= 1}
              >
                <Icon name="fa-chevron-left" />
              </button>
              <button
                type="button"
                aria-label="Next page"
                onClick={() => {
                  if (currentPage < pageCount) setPage(currentPage + 1);
                  else if (tab !== "likedHooks" && generations.length < totalGenerations) {
                    void loadGenerations(generations.length);
                  }
                }}
                disabled={
                  currentPage >= pageCount &&
                  (tab === "likedHooks" || generations.length >= totalGenerations)
                }
              >
                <Icon name="fa-chevron-right" />
              </button>
            </div>
            {tab !== "likedHooks" && generations.length < totalGenerations ? (
              <button
                type="button"
                className="s-chip"
                onClick={() => void loadGenerations(generations.length)}
                disabled={loadingMore}
              >
                {loadingMore ? "Loading..." : `Load more (${generations.length}/${totalGenerations})`}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

        {detailOpen ? (
          <TrackRail
            key={detail?.id ?? "empty"}
            detail={detail}
            clip={selectedClip}
            liked={detail && selectedClip ? isLikedRow(detail, selectedClip) : false}
            playlists={playlists}
            loading={detailLoading}
            onClose={closeDetail}
            onPlay={() => {
              if (detail && selectedClip) playClip(detail, selectedClip);
            }}
            onLike={() => {
              if (detail && selectedClip) void toggleLike(detail, selectedClip);
            }}
            onUnlock={() => void unlockPreview()}
            onDelete={() => {
              if (detail) setConfirm({ kind: "generations", ids: [detail.id] });
            }}
            onRemix={(song, clip) => {
              window.location.href = `/create?remix=${encodeURIComponent(song.id)}&variant=${encodeURIComponent(clip.variant || "ok")}`;
            }}
            onRename={async (nextTitle, variant) => {
              if (!detail) return false;
              try {
                const updated = await updateWebMusicGenerationTitle(detail.id, nextTitle, variant);
                if (!mounted.current) return false;
                setDetail(updated);
                setGenerations((current) =>
                  current.map((item) => (item.id === updated.id ? updated : item))
                );
                setToast("Title updated");
                return true;
              } catch (cause) {
                setToast(cause instanceof Error ? cause.message : "Could not rename this track");
                return false;
              }
            }}
            onAddToPlaylist={async (playlist) => {
              if (!detail || !selectedClip?.ready) return;
              try {
                await addWebMusicPlaylistItem(playlist.id, detail.id, selectedClip.variant);
                setToast(`Added to ${playlist.name}`);
              } catch (cause) {
                setToast(cause instanceof Error ? cause.message : "Could not add to playlist");
              }
            }}
            onCreatePlaylist={async (name) => {
              try {
                const created = await createWebMusicPlaylist(name);
                if (mounted.current) setPlaylists((current) => [created, ...current]);
                setToast(`Created playlist "${created.name}"`);
                return created;
              } catch (cause) {
                setToast(cause instanceof Error ? cause.message : "Could not create playlist");
                return null;
              }
            }}
          />
        ) : null}
      </div>

      {playlistDetail ? (
        <div
          className="s-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label={playlistDetail.name}
          onClick={() => setPlaylistDetail(null)}
        >
          <div
            className="s-modal"
            style={{ width: "min(620px,100%)" }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="s-modal-head">
              <h3>{playlistDetail.name}</h3>
              <button
                type="button"
                className="s-btn s-btn-icon sm"
                aria-label="Close"
                onClick={() => setPlaylistDetail(null)}
              >
                <Icon name="fa-xmark" />
              </button>
            </div>
            <div className="s-modal-body">
              {playlistItemsLoading ? (
                <p className="s-note">Loading tracks...</p>
              ) : playlistError ? (
                <p className="s-error">{playlistError}</p>
              ) : playlistItems.length ? (
                <div>
                  {playlistItems.map((item) => (
                    <div
                      className="s-row"
                      key={item.id}
                      role="button"
                      tabIndex={0}
                      style={{ padding: 8 }}
                      onClick={() => playPlaylistItem(item)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") playPlaylistItem(item);
                      }}
                    >
                      <span className="s-cover s-cover-sm">
                        <img src={item.image_url || "/hero.png"} alt="" loading="lazy" />
                        <span className="s-cover-play">
                          <span>
                            <Icon name="fa-play" />
                          </span>
                        </span>
                      </span>
                      <div className="s-row-body" style={{ paddingRight: 0 }}>
                        <div className="s-row-title">
                          <b>{item.title || "Untitled"}</b>
                          <span className="s-tag">{clipVersionLabel(item.variant)}</span>
                        </div>
                        <div className="s-row-desc">{item.style || "No style tags"}</div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="s-note">This playlist is empty.</p>
              )}
            </div>
            <div className="s-modal-foot">
              <button
                type="button"
                className="s-btn s-btn-ghost s-danger-text"
                onClick={() => setConfirm({ kind: "playlist", playlist: playlistDetail })}
                disabled={deleting}
              >
                <Icon name="fa-trash" /> Delete playlist
              </button>
              <span style={{ flex: 1 }} />
              <button
                type="button"
                className="s-btn s-btn-secondary"
                onClick={() => setPlaylistDetail(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {composer ? (
        <div
          className="s-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label={composer === "playlist" ? "New playlist" : "New workspace"}
          onClick={() => setComposer(null)}
        >
          <div
            className="s-modal"
            style={{ width: "min(440px,100%)" }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="s-modal-head">
              <h3>{composer === "playlist" ? "New playlist" : "New workspace"}</h3>
              <button
                type="button"
                className="s-btn s-btn-icon sm"
                aria-label="Close"
                onClick={() => setComposer(null)}
              >
                <Icon name="fa-xmark" />
              </button>
            </div>
            <div className="s-modal-body">
              <label className="s-field">
                <span className="s-field-label">
                  {composer === "playlist" ? "Playlist name" : "Workspace name"}
                </span>
                <input
                  className="s-input"
                  autoFocus
                  value={composerName}
                  onChange={(event) => setComposerName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void submitComposer();
                  }}
                  maxLength={120}
                  placeholder={composer === "playlist" ? "My playlist" : "My workspace"}
                />
              </label>
            </div>
            <div className="s-modal-foot">
              <span style={{ flex: 1 }} />
              <button
                type="button"
                className="s-btn s-btn-ghost"
                onClick={() => setComposer(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="s-btn s-btn-primary"
                onClick={() => void submitComposer()}
                disabled={composerBusy || !composerName.trim()}
              >
                {composerBusy ? "Creating..." : "Create"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {attachNotice ? (
        <div
          className="s-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label={attachNotice === "upload" ? "Upload audio" : "Record audio"}
          onClick={() => setAttachNotice(null)}
        >
          <div
            className="s-modal"
            style={{ width: "min(500px,100%)" }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="s-modal-head">
              <h3>{attachNotice === "upload" ? "Upload audio" : "Record audio"}</h3>
              <button
                type="button"
                className="s-btn s-btn-icon sm"
                aria-label="Close"
                onClick={() => setAttachNotice(null)}
              >
                <Icon name="fa-xmark" />
              </button>
            </div>
            <div className="s-modal-body">
              <p className="s-note">
                {attachNotice === "upload"
                  ? "Upload your own audio to extend, cover, or remix an idea."
                  : "Record a take and use it as a reference for a new song."}
              </p>
              <div className="s-box">
                Uploads and recording are not enabled for this workspace yet. You can still
                add audio from the Studio editor.
              </div>
            </div>
            <div className="s-modal-foot">
              <Link className="s-btn s-btn-secondary" href="/studio/editor">
                <Icon name="fa-table-columns" /> Open Studio
              </Link>
              <span style={{ flex: 1 }} />
              <button
                type="button"
                className="s-btn s-btn-ghost"
                onClick={() => setAttachNotice(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {confirm ? (
        <div
          className="s-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="Confirm delete"
          onClick={() => setConfirm(null)}
        >
          <div
            className="s-modal"
            style={{ width: "min(440px,100%)" }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="s-modal-head">
              <h3>
                {confirm.kind === "generations"
                  ? confirm.variant
                    ? confirm.permanent
                      ? `Delete ${confirm.variant === "alt" ? "Version 2" : "Version 1"} permanently?`
                      : `Move ${confirm.variant === "alt" ? "Version 2" : "Version 1"} to Trash?`
                    : confirm.permanent
                      ? `Delete ${confirm.ids.length} ${confirm.ids.length === 1 ? "song" : "songs"} permanently?`
                      : `Move ${confirm.ids.length} ${confirm.ids.length === 1 ? "song" : "songs"} to Trash?`
                  : "Delete playlist?"}
              </h3>
              <button
                type="button"
                className="s-btn s-btn-icon sm"
                aria-label="Close"
                onClick={() => setConfirm(null)}
              >
                <Icon name="fa-xmark" />
              </button>
            </div>
            <div className="s-modal-body">
              <p className="s-note">
                {confirm.kind === "generations"
                  ? confirm.variant
                    ? confirm.permanent
                      ? "That version is removed for good. The other version stays in your library."
                      : "That version moves to Trash; the other version stays in your library. Restore it from Library → Trash."
                    : confirm.permanent
                      ? "This permanently removes the selected songs and their files. It cannot be undone."
                      : "They move to Trash first — restore them any time, or empty the trash to delete them for good."
                  : `"${confirm.playlist.name}" will be permanently deleted. The songs stay in your library.`}
              </p>
            </div>
            <div className="s-modal-foot">
              <span style={{ flex: 1 }} />
              <button
                type="button"
                className="s-btn s-btn-ghost"
                onClick={() => setConfirm(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="s-btn s-btn-danger"
                disabled={deleting}
                onClick={() => {
                  if (confirm.kind === "generations")
                    void deleteGenerations(
                      confirm.ids,
                      confirm.permanent,
                      confirm.variant
                    );
                  else void deletePlaylist(confirm.playlist);
                }}
              >
                {deleting
                  ? "Working…"
                  : confirm.kind === "generations" && !confirm.permanent
                    ? "Move to Trash"
                    : "Delete permanently"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {detailsTarget ? (
        <SongDetailsModal
          title={detailsTarget.song.title}
          lyrics={detailsTarget.song.lyrics || ""}
          busy={detailsBusy}
          onClose={() => setDetailsTarget(null)}
          onSubmit={submitSongDetails}
        />
      ) : null}

      {shareTarget ? (
        <ShareClipModal
          url={`${typeof window !== "undefined" ? window.location.origin : ""}/library?clip=${encodeURIComponent(shareTarget.song.id)}&variant=${encodeURIComponent(shareTarget.clip.variant || "ok")}`}
          title={shareTarget.clip.title || shareTarget.song.title || "Untitled"}
          downloadUrl={
            shareTarget.clip.download_url ||
            clipDownloadUrl(shareTarget.song.id, shareTarget.clip.variant, "mp3")
          }
          onClose={() => setShareTarget(null)}
          onToast={setToast}
        />
      ) : null}

      {reportTarget ? (
        <ReportClipModal
          title={reportTarget.song.title}
          busy={reportBusy}
          onClose={() => setReportTarget(null)}
          onSubmit={submitReport}
        />
      ) : null}

      {toast ? (
        <div className="s-toast" role="status">
          {toast}
        </div>
      ) : null}
    </div>
  );
}
