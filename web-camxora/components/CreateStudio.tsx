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
  { value: "V6", label: "V6 · best quality" },
  { value: "V6_MINI", label: "V6 Mini · lower cost" },
];

function statusLabel(status: string): string {
  return status.replace(/_/g, " ");
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
  const [songs, setSongs] = useState<WebMusicGeneration[]>([]);
  const [loadingSongs, setLoadingSongs] = useState(true);
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
        if (active) setSongs(items);
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

  const formReady =
    mode === "simple"
      ? prompt.trim().length > 0
      : instrumental
        ? style.trim().length > 0
        : style.trim().length > 0 && lyrics.trim().length > 0;

  async function writeLyrics() {
    const seed = prompt.trim() || title.trim() || style.trim();
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

  async function pollGeneration(id: string, attempts = 0) {
    if (!mounted.current) return;
    try {
      const generation = await fetchGeneration(id);
      if (!mounted.current) return;
      setSongs((current) => [
        generation,
        ...current.filter((item) => item.id !== generation.id),
      ]);
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
    const payload: GenerateSongInput = {
      mode: mode === "simple" ? "simple" : "advanced",
      prompt: mode === "simple" ? prompt.trim() || undefined : undefined,
      title: mode === "custom" ? title.trim() || undefined : undefined,
      style: mode === "custom" ? style.trim() || undefined : undefined,
      lyrics: mode === "custom" && !instrumental ? lyrics.trim() || undefined : undefined,
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
      setNotice("Generation started. Your song will appear here.");
      void pollGeneration(created.task_id);
      void refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not start generation");
    } finally {
      setBusy(false);
    }
  }

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
      <div className="page-head">
        <div>
          <div className="eyebrow">Studio</div>
          <h1>Create.</h1>
          <p>Describe a song or write the details yourself. Camxora handles the rest.</p>
        </div>
        <span className="credit-chip">
          <Icon name="fa-coins" /> {(credits ?? user.credit_balance ?? 0).toLocaleString()} credits
        </span>
      </div>

      <div className="create-layout">
        <section className="panel create-card">
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
              Custom
            </button>
          </div>

          {mode === "simple" ? (
            <div className="field">
              <label htmlFor="create-prompt">Describe your song</label>
              <textarea
                id="create-prompt"
                className="textarea create-prompt"
                placeholder="A warm Khmer ballad about the Mekong at sunset. Female vocal, acoustic guitar, 72 BPM?"
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                maxLength={5000}
              />
            </div>
          ) : null}

          {mode === "custom" ? (
            <>
              <div className="create-lyrics-head">
                <label>Lyrics</label>
                <div className="create-inline-tabs">
                  <button
                    className={lyricsMode === "write" ? "on" : ""}
                    type="button"
                    onClick={() => setLyricsMode("write")}
                  >
                    Write
                  </button>
                  <button
                    className={lyricsMode === "prompt" ? "on" : ""}
                    type="button"
                    onClick={() => setLyricsMode("prompt")}
                  >
                    Prompt
                  </button>
                </div>
              </div>
              <textarea
                className="textarea create-lyrics"
                value={lyrics}
                onChange={(event) => setLyrics(event.target.value)}
                placeholder={
                  lyricsMode === "write"
                    ? "[Verse]\nWrite your lyrics here?"
                    : "Describe the story or feeling you want the lyrics to capture?"
                }
                disabled={instrumental}
                maxLength={5000}
              />
              <button
                className="create-text-btn"
                type="button"
                onClick={writeLyrics}
                disabled={writingLyrics || instrumental}
              >
                <Icon name="fa-wand-magic-sparkles" /> {writingLyrics ? "Writing lyrics?" : "Write lyrics for me"}
              </button>

              <div className="create-row">
                <div className="field">
                  <label htmlFor="create-style">Style of music</label>
                  <input
                    id="create-style"
                    className="input"
                    value={style}
                    onChange={(event) => setStyle(event.target.value)}
                    placeholder="Khmer pop, acoustic, 72 BPM"
                    maxLength={1000}
                  />
                </div>
                <div className="field">
                  <label htmlFor="create-title">Song title</label>
                  <input
                    id="create-title"
                    className="input"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="Optional"
                    maxLength={200}
                  />
                </div>
              </div>

            </>
          ) : null}

          <div className="create-toggle-row">
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
            Advanced options
            <Icon name={advancedOpen ? "fa-chevron-up" : "fa-chevron-down"} />
          </button>

          {advancedOpen ? (
            <div className="create-advanced">
              <div className="create-row">
                <div className="field">
                  <label htmlFor="create-model">Model</label>
                  <select id="create-model" className="select" value={model} onChange={(event) => setModel(event.target.value)}>
                    {models.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="create-vocal">Vocal</label>
                  <select id="create-vocal" className="select" value={vocalGender} onChange={(event) => setVocalGender(event.target.value as "f" | "m" | "both")}>
                    <option value="f">Female</option>
                    <option value="m">Male</option>
                    <option value="both">Both</option>
                  </select>
                </div>
              </div>
              <div className="create-sliders">
                <label>Style influence <b>{Math.round(styleWeight * 100)}%</b><input type="range" min="0" max="1" step="0.01" value={styleWeight} onChange={(event) => setStyleWeight(Number(event.target.value))} /></label>
                <label>Weirdness <b>{Math.round(weirdness * 100)}%</b><input type="range" min="0" max="1" step="0.01" value={weirdness} onChange={(event) => setWeirdness(Number(event.target.value))} /></label>
                <label>Audio influence <b>{Math.round(audioWeight * 100)}%</b><input type="range" min="0" max="1" step="0.01" value={audioWeight} onChange={(event) => setAudioWeight(Number(event.target.value))} /></label>
              </div>
              <div className="field">
                <label htmlFor="create-negative">Exclude styles</label>
                <input id="create-negative" className="input" value={negativeTags} onChange={(event) => setNegativeTags(event.target.value)} placeholder="e.g. heavy distortion, screaming" />
              </div>
            </div>
          ) : null}

          {error ? <p className="fine create-error" role="alert">{error}</p> : null}
          {notice ? <p className="fine create-notice" role="status">{notice}</p> : null}

          <div className="create-submit">
            <span className="create-cost"><Icon name="fa-coins" /> Uses your credit balance</span>
            <button className="btn btn-primary" type="button" onClick={onSubmit} disabled={busy || !formReady}>
              <Icon name="fa-music" /> {busy ? "Creating…" : "Create"}
            </button>
          </div>
        </section>

        <aside className="panel create-workspace">
          <div className="sec-head">
            <h2>Your songs</h2>
            <Link href="/library">Open library</Link>
          </div>
          {loadingSongs ? (
            <p className="fine" style={{ textAlign: "left" }}>Loading your songs…</p>
          ) : !songs.length ? (
            <div className="create-empty">
              <span><Icon name="fa-music" /></span>
              <h3>No songs yet</h3>
              <p>Your generations will appear here as soon as they start.</p>
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
                return (
                  <div className="create-song" key={song.id}>
                    <span className="create-song-art"><Icon name="fa-music" /></span>
                    <div>
                      <b>{song.title || "Untitled"}</b>
                      <span>{song.style || song.model || "Camxora"}</span>
                    </div>
                    <button
                      className="create-song-play"
                      type="button"
                      aria-label={ready ? `Play ${song.title || "track"}` : "Song not ready"}
                      onClick={() => playSong(song)}
                      disabled={!ready}
                    >
                      <Icon name="fa-play" />
                    </button>
                    <em className={ready ? "ready" : ""}>
                      {ready ? "Ready" : statusLabel(song.status)}
                    </em>
                  </div>
                );
              })}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
