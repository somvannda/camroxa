"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";
import { usePlayer } from "@/components/PlayerProvider";
import { fetchGenerations, type WebMusicGeneration } from "@/lib/library-api";
import {
  fetchGeneration,
  generateLyrics,
  generateSong,
  type GenerateSongInput,
} from "@/lib/create-api";

type Mode = "simple" | "custom";
type LyricsMode = "write" | "prompt";

const models = [
  { value: "V6", label: "V6 Pro" },
  { value: "V6_MINI", label: "V6 Mini" },
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

function statusLabel(status: string): string {
  return status.replace(/_/g, " ");
}

function clipVersionLabel(variant?: string | null): string {
  return variant === "alt" ? "Version 2" : "Version 1";
}

function clipDownloadUrl(
  songId: string,
  variant: string,
  kind: DownloadKind
): string {
  const base = `/api/v3/web-music/generations/${encodeURIComponent(songId)}`;
  if (kind === "mp3") return `${base}/download?variant=${encodeURIComponent(variant)}`;
  if (kind === "wav") return `${base}/download-wav?variant=${encodeURIComponent(variant)}`;
  return `${base}/timed-lyrics?variant=${encodeURIComponent(variant)}&format=${kind}`;
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function percent(value?: number | null): string {
  return `${Math.round((value ?? 0.5) * 100)}%`;
}

function vocalLabel(value?: string | null): string {
  if (value === "f") return "Female";
  if (value === "m") return "Male";
  if (value === "both") return "Both";
  return "Not set";
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
  const [model, setModel] = useState("V6");
  const [vocalGender, setVocalGender] = useState<"f" | "m" | "both">("f");
  const [negativeTags, setNegativeTags] = useState("");
  const [styleWeight, setStyleWeight] = useState(0.5);
  const [weirdness, setWeirdness] = useState(0.5);
  const [audioWeight, setAudioWeight] = useState(0.5);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [featureTab, setFeatureTab] = useState<FeatureTab>(null);
  const [copied, setCopied] = useState<"style" | "lyrics" | null>(null);
  const [songs, setSongs] = useState<WebMusicGeneration[]>([]);
  const [loadingSongs, setLoadingSongs] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<WebMusicGeneration | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [writingLyrics, setWritingLyrics] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      window.location.href = "/login?next=/create";
      return;
    }
    let active = true;
    fetchGenerations(20)
      .then((items) => {
        if (!active) return;
        setSongs(items);
        if (items[0]) {
          void selectSong(items[0].id);
        } else {
          setSelectedId(null);
          setSelectedDetail(null);
        }
      })
      .catch(() => {
        if (active) setSongs([]);
      })
      .finally(() => {
        if (active) setLoadingSongs(false);
      });
    return () => {
      active = false;
    };
  }, [loading, user]);

  async function selectSong(id: string) {
    setSelectedId(id);
    setDetailLoading(true);
    try {
      const detail = await fetchGeneration(id);
      if (!mounted.current) return;
      setSelectedDetail(detail);
      setSongs((current) => current.map((item) => (item.id === detail.id ? detail : item)));
    } catch {
      if (mounted.current) setSelectedDetail(songs.find((item) => item.id === id) ?? null);
    } finally {
      if (mounted.current) setDetailLoading(false);
    }
  }

  async function refreshSongs() {
    try {
      const items = await fetchGenerations(20);
      if (!mounted.current) return;
      setSongs(items);
      if (selectedId) {
        const detail = await fetchGeneration(selectedId).catch(() => null);
        if (detail && mounted.current) setSelectedDetail(detail);
      }
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
      const draft = await generateLyrics(seed);
      setLyrics(draft.lyrics);
      if (!title.trim() && draft.title) setTitle(draft.title);
      setLyricsMode("write");
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

  async function copyText(text: string, kind: "style" | "lyrics") {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(kind);
      window.setTimeout(() => setCopied(null), 1600);
    } catch {
      setError("Copy failed. Select the text and copy it manually.");
    }
  }

  async function pollGeneration(id: string, attempts = 0) {
    if (!mounted.current) return;
    try {
      const generation = await fetchGeneration(id);
      if (!mounted.current) return;
      setSongs((current) => [
        generation,
        ...current.filter((item) => item.id !== generation.id),
      ]);
      setSelectedId((current) => {
        if (current === generation.id) setSelectedDetail(generation);
        return current;
      });
      const done =
        String(generation.status).toLowerCase() === "success" ||
        (generation.clips?.some((clip) => clip.ready) ?? false);
      if (!done && attempts < 40) {
        window.setTimeout(() => void pollGeneration(id, attempts + 1), 3000);
      } else if (done) {
        setNotice("Your song is ready.");
        void refresh();
      }
    } catch {
      if (attempts < 20) {
        window.setTimeout(() => void pollGeneration(id, attempts + 1), 3000);
      }
    }
  }

  function playSong(song: WebMusicGeneration) {
    const clip = song.clips?.find((item) => item.ready && item.audio_url) ??
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
      title: song.title || "Untitled",
      artist: "You",
      cover: clip?.image_url || "/hero.png",
      duration: Math.max(1, Math.round(clip?.duration_seconds || 180)),
      audioUrl,
    });
  }

  async function onSubmit() {
    if (busy || !formReady) return;
    setBusy(true);
    setError("");
    setNotice("");
    let finalLyrics = lyrics.trim();
    if (mode === "custom" && !instrumental && lyricsMode === "prompt") {
      try {
        const draft = await generateLyrics(finalLyrics);
        finalLyrics = draft.lyrics;
        setLyrics(draft.lyrics);
        if (!title.trim() && draft.title) setTitle(draft.title);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Could not write lyrics");
        setBusy(false);
        return;
      }
    }
    const payload: GenerateSongInput = {
      mode: mode === "simple" ? "simple" : "advanced",
      prompt: mode === "simple" ? prompt.trim() || undefined : undefined,
      title: mode === "custom" ? title.trim() || undefined : undefined,
      style: mode === "custom" ? style.trim() || undefined : undefined,
      lyrics: mode === "custom" && !instrumental ? finalLyrics || undefined : undefined,
      instrumental,
      model,
      negative_tags: negativeTags.trim() || undefined,
      vocal_gender: instrumental ? undefined : vocalGender,
      style_weight: styleWeight,
      weirdness_constraint: weirdness,
      audio_weight: audioWeight,
    };
    try {
      const created = await generateSong(payload);
      const pending: WebMusicGeneration = {
        id: created.task_id,
        title: created.title || title || "Untitled",
        style: created.style || style,
        status: created.status || "pending",
        created_at: new Date().toISOString(),
        clips: [],
      };
      setSongs((current) => [pending, ...current.filter((item) => item.id !== pending.id)]);
      setSelectedId(pending.id);
      setSelectedDetail(pending);
      setNotice("Generation started. Your song will appear here.");
      void pollGeneration(created.task_id);
      void refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not start generation");
    } finally {
      setBusy(false);
    }
  }

  const selected =
    selectedDetail?.id === selectedId
      ? selectedDetail
      : songs.find((song) => song.id === selectedId) ?? null;
  const selectedClip =
    selected?.clips?.find((clip) => clip.ready && clip.audio_url) ??
    selected?.clips?.find((clip) => clip.audio_url) ??
    selected?.clips?.[0] ??
    null;
  const selectedCover = selectedClip?.image_url || "/hero.png";
  const selectedReady =
    Boolean(selectedClip?.audio_url) ||
    String(selected?.status || "").toLowerCase() === "success";

  if (loading || !user) {
    return (
      <div className="page">
        <div className="page-head">
          <div>
            <div className="eyebrow">Studio</div>
            <h1>Create</h1>
            <p>{loading ? "Checking your session…" : "Redirecting to sign in…"}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page create-page">
      <div className="create-layout">
        <section className="panel create-card">
          <div className="create-card-top">
            <div className="create-tabs" role="tablist" aria-label="Creation mode">
              <button
                className={mode === "simple" ? "on" : ""}
                type="button"
                role="tab"
                aria-selected={mode === "simple"}
                onClick={() => setMode("simple")}
              >
                Simple
              </button>
              <button
                className={mode === "custom" ? "on" : ""}
                type="button"
                role="tab"
                aria-selected={mode === "custom"}
                onClick={() => setMode("custom")}
              >
                Advanced
              </button>
            </div>
            <label className="create-model-pill">
              <Icon name="fa-bolt" />
              <select
                id="create-model"
                value={model}
                onChange={(event) => setModel(event.target.value)}
                aria-label="Model"
              >
                {models.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
              <Icon name="fa-chevron-down" />
            </label>
          </div>

          <div className="create-feature-tabs">
            {(["audio", "voice", "inspo"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                className={featureTab === tab ? "on" : ""}
                onClick={() => setFeatureTab((current) => (current === tab ? null : tab))}
              >
                + {tab}
              </button>
            ))}
          </div>
          {featureTab ? (
            <p className="create-feature-note">
              {featureTab === "audio"
                ? "Reference audio uploads are coming soon."
                : featureTab === "voice"
                  ? "Voice reference uploads are coming soon."
                  : "Inspiration references are coming soon."}
            </p>
          ) : null}

          <div className="create-card-body">
            {mode === "simple" ? (
              <div className="create-field">
                <div className="create-field-head">
                  <label htmlFor="create-prompt">Song description</label>
                  <span>{prompt.length}/5000</span>
                </div>
                <textarea
                  id="create-prompt"
                  className="textarea create-prompt"
                  placeholder="A warm Khmer ballad about the Mekong at sunset. Female vocal, acoustic guitar, 72 BPM…"
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  maxLength={5000}
                  rows={8}
                />
              </div>
            ) : (
              <>
                <div className="create-section-head">
                  <h3>Lyrics</h3>
                  {lyricsMode === "write" ? (
                    <button
                      className="create-auto"
                      type="button"
                      onClick={writeLyrics}
                      disabled={writingLyrics || instrumental}
                    >
                      <Icon name="fa-wand-magic-sparkles" />
                      {writingLyrics ? "Generating…" : "Auto-generate"}
                    </button>
                  ) : (
                    <span className="create-auto-note">Generated on Create</span>
                  )}
                </div>
                <div className="create-lyrics-tabs" role="tablist" aria-label="Lyrics mode">
                  <button
                    className={lyricsMode === "write" ? "on" : ""}
                    type="button"
                    role="tab"
                    aria-selected={lyricsMode === "write"}
                    onClick={() => setLyricsMode("write")}
                  >
                    Write
                  </button>
                  <button
                    className={lyricsMode === "prompt" ? "on" : ""}
                    type="button"
                    role="tab"
                    aria-selected={lyricsMode === "prompt"}
                    onClick={() => setLyricsMode("prompt")}
                  >
                    Prompt
                  </button>
                </div>
                <textarea
                  className="textarea create-lyrics"
                  value={lyrics}
                  onChange={(event) => setLyrics(event.target.value)}
                  placeholder={
                    lyricsMode === "write"
                      ? "Write lyrics, or paste a verse…"
                      : "Describe the story or feeling you want the lyrics to capture…"
                  }
                  disabled={instrumental}
                  maxLength={5000}
                  rows={7}
                />
                <div className="create-char-row">
                  <span>{lyrics.length}/5000</span>
                  {lyricsMode === "write" ? (
                    <button
                      className="create-write-link"
                      type="button"
                      onClick={writeLyrics}
                      disabled={writingLyrics || instrumental}
                    >
                      {writingLyrics ? "Writing…" : "Write lyrics for me"}
                    </button>
                  ) : null}
                </div>

                <div className="create-section-head">
                  <h3>Styles</h3>
                  <button className="create-shuffle" type="button" onClick={shuffleStyle}>
                    <Icon name="fa-shuffle" /> Shuffle
                  </button>
                </div>
                <textarea
                  id="create-style"
                  className="textarea create-style"
                  value={style}
                  onChange={(event) => setStyle(event.target.value)}
                  placeholder="urbano, electric guitar, upbeat rock, 128 BPM, eurodance"
                  maxLength={1000}
                  rows={4}
                />
                <div className="create-chips">
                  {styleChips.map((chip) => (
                    <button key={chip} type="button" onClick={() => appendStyle(chip)}>
                      {chip}
                    </button>
                  ))}
                </div>
                <div className="create-field create-negative">
                  <label htmlFor="create-negative">Negative tags (optional)</label>
                  <input
                    id="create-negative"
                    className="input"
                    value={negativeTags}
                    onChange={(event) => setNegativeTags(event.target.value)}
                    placeholder="choir, backing vocals, falsetto"
                  />
                </div>
              </>
            )}

            <div className="create-option-card">
              <div>
                <b>Instrumental</b>
                <span>No vocals — music only.</span>
              </div>
              <button
                className={`toggle${instrumental ? " on" : ""}`}
                type="button"
                role="switch"
                aria-label="Instrumental"
                aria-checked={instrumental}
                onClick={() => setInstrumental((value) => !value)}
              >
                <i />
              </button>
            </div>

            <button
              className="create-advanced-toggle"
              type="button"
              aria-expanded={advancedOpen}
              onClick={() => setAdvancedOpen((value) => !value)}
            >
              <Icon name="fa-sliders" />
              More Options
              <Icon name={advancedOpen ? "fa-chevron-up" : "fa-chevron-down"} />
            </button>

            {advancedOpen ? (
              <div className="create-advanced">
                <div className="create-field">
                  <label htmlFor="create-vocal">Vocal gender</label>
                  <select
                    id="create-vocal"
                    className="select"
                    value={vocalGender}
                    onChange={(event) => setVocalGender(event.target.value as "f" | "m" | "both")}
                  >
                    <option value="f">Female</option>
                    <option value="m">Male</option>
                    <option value="both">Both</option>
                  </select>
                </div>
                <div className="create-sliders">
                  <label>Style influence <b>{Math.round(styleWeight * 100)}%</b><input type="range" min="0" max="1" step="0.01" value={styleWeight} onChange={(event) => setStyleWeight(Number(event.target.value))} /></label>
                  <label>Weirdness <b>{Math.round(weirdness * 100)}%</b><input type="range" min="0" max="1" step="0.01" value={weirdness} onChange={(event) => setWeirdness(Number(event.target.value))} /></label>
                  <label>Audio influence <b>{Math.round(audioWeight * 100)}%</b><input type="range" min="0" max="1" step="0.01" value={audioWeight} onChange={(event) => setAudioWeight(Number(event.target.value))} /></label>
                </div>
              </div>
            ) : null}

            <label className="create-title-row" htmlFor="create-title">
              <Icon name="fa-music" />
              <input
                id="create-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Song title (optional)"
                maxLength={200}
              />
            </label>

            {error ? <p className="fine create-error" role="alert">{error}</p> : null}
            {notice ? <p className="fine create-notice" role="status">{notice}</p> : null}
          </div>

          <div className="create-submit">
            <span className="create-cost"><Icon name="fa-coins" /> Uses your credit balance</span>
            <button className="btn btn-primary" type="button" onClick={onSubmit} disabled={busy || !formReady}>
              <Icon name="fa-music" /> {busy ? "Creating…" : "Create"}
            </button>
          </div>
        </section>

        <section className="panel create-workspace">
          <div className="create-workspace-head">
            <div>
              <p className="create-eyebrow">Workspaces</p>
              <h2>My Workspace</h2>
            </div>
            <div className="create-workspace-actions">
              <span className="create-song-count">{songs.length} songs</span>
              <button type="button" onClick={() => void refreshSongs()} aria-label="Refresh songs">
                <Icon name="fa-rotate" />
              </button>
              <Link href="/library">Library</Link>
            </div>
          </div>
          <div className="create-workspace-toolbar">
            <span><Icon name="fa-layer-group" /> All generations</span>
            <span>{loadingSongs ? "Loading…" : "Newest first"}</span>
          </div>
          {loadingSongs ? (
            <p className="fine" style={{ textAlign: "left" }}>Loading your songs…</p>
          ) : !songs.length ? (
            <div className="create-empty">
              <span><Icon name="fa-music" /></span>
              <h3>Your songs will land here</h3>
              <p>Write a description or lyrics, then hit Create.</p>
            </div>
          ) : (
            <div className="create-song-list">
              {songs.map((song) => {
                const clip = song.clips?.find((item) => item.ready && item.audio_url) ??
                  song.clips?.find((item) => item.audio_url) ??
                  song.clips?.[0];
                const ready =
                  Boolean(clip?.audio_url) ||
                  String(song.status).toLowerCase() === "success";
                const variant = clip?.variant || "ok";
                return (
                  <div
                    className={`create-song${selectedId === song.id ? " selected" : ""}`}
                    key={song.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => void selectSong(song.id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        void selectSong(song.id);
                      }
                    }}
                  >
                    <button
                      className={`create-song-cover${ready ? "" : " pending"}`}
                      type="button"
                      aria-label={ready ? `Play ${song.title || "track"}` : "Song not ready"}
                      onClick={(event) => {
                        event.stopPropagation();
                        if (ready) playSong(song);
                      }}
                      disabled={!ready}
                    >
                      <img src={clip?.image_url || "/hero.png"} alt="" />
                      <span><Icon name={ready ? "fa-play" : "fa-clock"} /></span>
                    </button>
                    <div className="create-song-info">
                      <div className="create-song-title">
                        <b>{song.title || "Untitled"}</b>
                        <em>{clipVersionLabel(variant)}</em>
                      </div>
                      <span className="create-song-meta">
                        <i className={ready ? "ready" : ""}>{ready ? "Ready" : statusLabel(song.status)}</i>
                        {" · "}
                        {song.model_label || song.model || "V6"}
                        {" · "}
                        {formatDate(song.created_at)}
                      </span>
                    </div>
                    <div className="create-song-actions" onClick={(event) => event.stopPropagation()}>
                      {ready && clip ? (
                        <>
                          {!song.instrumental ? (
                            <>
                              <a href={clipDownloadUrl(song.id, variant, "lrc")} title="Download LRC">LRC</a>
                              <a href={clipDownloadUrl(song.id, variant, "srt")} title="Download SRT">SRT</a>
                            </>
                          ) : null}
                          <a href={clip.download_url || clipDownloadUrl(song.id, variant, "mp3")} title="Download MP3">MP3</a>
                          <a href={clipDownloadUrl(song.id, variant, "wav")} title="Download WAV">WAV</a>
                        </>
                      ) : (
                        <span className="create-song-waiting">Waiting</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          {songs.length ? (
            <p className="create-list-foot">Showing all {songs.length} songs</p>
          ) : null}
        </section>

        <aside className="panel create-inspector">
          {!selected ? (
            <div className="create-inspector-empty">
              <Icon name="fa-circle-info" />
              <p>Select a track to see its settings, style, and lyrics.</p>
            </div>
          ) : detailLoading ? (
            <p className="fine" style={{ textAlign: "left" }}>Loading details…</p>
          ) : (
            <>
              <div className="create-detail-head">
                <img src={selectedCover} alt="" />
                <div>
                  <div className="create-detail-title">
                    <h3>{selected.title || "Untitled"}</h3>
                    <em>{clipVersionLabel(selectedClip?.variant)}</em>
                  </div>
                  <span className="create-detail-sub">
                    <i className={selectedReady ? "ready" : ""}>{selectedReady ? "Ready" : statusLabel(selected.status)}</i>
                    {" · "}
                    {selected.model_label || selected.model || "V6"}
                    {" · "}
                    {formatDate(selected.created_at)}
                  </span>
                </div>
              </div>

              <div className="create-detail-actions">
                <button
                  className="create-action create-action-play"
                  type="button"
                  onClick={() => playSong(selected)}
                  disabled={!selectedReady}
                  aria-label="Play track"
                >
                  <Icon name="fa-play" /> Play
                </button>
                {selectedReady && selectedClip ? (
                  <>
                    {!selected.instrumental ? (
                      <>
                        <a href={clipDownloadUrl(selected.id, selectedClip.variant || "ok", "lrc")} title="Download LRC">LRC</a>
                        <a href={clipDownloadUrl(selected.id, selectedClip.variant || "ok", "srt")} title="Download SRT">SRT</a>
                      </>
                    ) : null}
                    <a href={selectedClip.download_url || clipDownloadUrl(selected.id, selectedClip.variant || "ok", "mp3")} title="Download MP3">MP3</a>
                    <a href={clipDownloadUrl(selected.id, selectedClip.variant || "ok", "wav")} title="Download WAV">WAV</a>
                  </>
                ) : null}
              </div>

              <div className="create-detail-section">
                <div className="create-detail-label">Settings</div>
                <div className="create-settings">
                  <div><span>Model</span><b>{selected.model_label || selected.model || "V6"}</b></div>
                  <div><span>Type</span><b>{selected.instrumental ? "Instrumental" : "With Vocals"}</b></div>
                  <div><span>Vocal Gender</span><b>{vocalLabel(selected.vocal_gender)}</b></div>
                  <div><span>Style Influence</span><b>{percent(selected.style_weight)}</b></div>
                  <div><span>Weirdness</span><b>{percent(selected.weirdness_constraint)}</b></div>
                  <div><span>Audio Weight</span><b>{percent(selected.audio_weight)}</b></div>
                  <div><span>Status</span><b>{selectedReady ? "Ready" : statusLabel(selected.status)}</b></div>
                </div>
              </div>

              {selected.negative_tags ? (
                <div className="create-detail-section">
                  <div className="create-detail-label">Negative Tags</div>
                  <div className="create-detail-box">{selected.negative_tags}</div>
                </div>
              ) : null}

              <div className="create-detail-section">
                <div className="create-detail-label-row">
                  <span className="create-detail-label">Style</span>
                  <button type="button" className="create-copy" onClick={() => void copyText(selected.style || "", "style")} aria-label="Copy style">
                    <Icon name={copied === "style" ? "fa-check" : "fa-copy"} />
                  </button>
                </div>
                <div className="create-detail-box">{selected.style || "—"}</div>
              </div>

              <div className="create-detail-section">
                <div className="create-detail-label-row">
                  <span className="create-detail-label">Lyrics</span>
                  <button type="button" className="create-copy" onClick={() => void copyText(selected.lyrics || "", "lyrics")} aria-label="Copy lyrics">
                    <Icon name={copied === "lyrics" ? "fa-check" : "fa-copy"} />
                  </button>
                </div>
                <pre className="create-detail-lyrics">{selected.instrumental ? "Instrumental" : selected.lyrics || "No lyrics saved."}</pre>
              </div>

              <Link className="create-open-studio" href="/studio/editor">
                <Icon name="fa-table-columns" /> Open in Studio
              </Link>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
