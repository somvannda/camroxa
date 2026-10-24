"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";
import { usePlayer } from "@/components/PlayerProvider";
import {
  fetchGenerations,
  fetchLikedTracks,
  fetchPlaylists,
  type LikedTrack,
  type WebMusicGeneration,
  type WebMusicPlaylist,
} from "@/lib/library-api";

const tabs = [
  { id: "all", label: "All" },
  { id: "generated", label: "Generated" },
  { id: "playlists", label: "Playlists" },
  { id: "liked", label: "Liked" },
];

const fmtDuration = (seconds?: number | null) => {
  if (!seconds || seconds <= 0) return "—";
  const total = Math.round(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
};

const fmtDate = (value?: string | null) => {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
};

export function LibraryView() {
  const { user, credits, loading: authLoading } = useAuth();
  const { playTrack } = usePlayer();
  const [tab, setTab] = useState("all");
  const [generations, setGenerations] = useState<WebMusicGeneration[]>([]);
  const [playlists, setPlaylists] = useState<WebMusicPlaylist[]>([]);
  const [liked, setLiked] = useState<LikedTrack[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      window.location.href = "/login?next=/library";
      return;
    }
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([fetchGenerations(), fetchPlaylists(), fetchLikedTracks()])
      .then(([nextGenerations, nextPlaylists, nextLiked]) => {
        if (!active) return;
        setGenerations(nextGenerations);
        setPlaylists(nextPlaylists);
        setLiked(nextLiked);
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Could not load library");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [authLoading, user]);

  const playGeneration = (generation: WebMusicGeneration) => {
    const clip = generation.clips?.[0];
    playTrack({
      title: generation.title || "Untitled",
      artist: "You",
      cover: clip?.image_url || "/hero.png",
      duration: Math.round(clip?.duration_seconds || 180),
      elapsed: 0,
    });
  };

  const playLiked = (track: LikedTrack) => {
    playTrack({
      title: track.title,
      artist: track.artist_name || "Camxora",
      cover: track.cover_url || "/hero.png",
      duration: Math.round(track.duration_seconds || 180),
      elapsed: 0,
    });
  };

  if (authLoading || loading) {
    return (
      <div className="page">
        <div className="page-head">
          <div>
            <div className="eyebrow">Your collection</div>
            <h1>Your Library</h1>
            <p>Loading your music…</p>
          </div>
        </div>
      </div>
    );
  }

  if (!user) return null;

  const hasAnything = generations.length > 0 || playlists.length > 0 || liked.length > 0;

  const generationList = (
    <div className="gen-list">
      {generations.map((generation) => (
        <div className="gen-row" key={generation.id}>
          <img src={generation.clips?.[0]?.image_url || "/hero.png"} alt="" />
          <div>
            <strong>{generation.title || "Untitled"}</strong>
            <span>
              {generation.style || "No style"} · {fmtDuration(generation.clips?.[0]?.duration_seconds)} ·{" "}
              {fmtDate(generation.created_at)}
            </span>
          </div>
          <span className="pill priv">{generation.status || "draft"}</span>
          <button
            className="mini-act"
            type="button"
            onClick={() => playGeneration(generation)}
          >
            <Icon name="fa-play" /> Play
          </button>
        </div>
      ))}
    </div>
  );

  const playlistList = (
    <div className="playlist-grid">
      {playlists.map((playlist) => (
        <Link className="playlist-card" href="/library" key={playlist.id}>
          <div className="playlist-cover">
            <Icon name="fa-music" />
          </div>
          <h3>{playlist.name}</h3>
          <p>
            {playlist.song_count} {playlist.song_count === 1 ? "track" : "tracks"} ·{" "}
            {playlist.is_public ? "Public" : "Private"}
          </p>
        </Link>
      ))}
    </div>
  );

  const likedList = (
    <div className="gen-list">
      {liked.map((track) => (
        <div className="gen-row" key={track.id}>
          <img src={track.cover_url || "/hero.png"} alt="" />
          <div>
            <strong>{track.title}</strong>
            <span>
              {track.artist_name || "Camxora"} · {fmtDuration(track.duration_seconds)} ·{" "}
              {fmtDate(track.added_at)}
            </span>
          </div>
          <button className="mini-act" type="button" onClick={() => playLiked(track)}>
            <Icon name="fa-play" /> Play
          </button>
        </div>
      ))}
    </div>
  );

  const emptyState = (
    <div className="library-empty">
      <span className="library-empty-icon">
        <Icon name="fa-music" />
      </span>
      <h2>Your library is waiting.</h2>
      <p>Generate your first song, then it will show up here with your playlists and likes.</p>
      <Link className="btn btn-primary" href="/create">
        <Icon name="fa-plus" /> Create a song
      </Link>
    </div>
  );

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Your collection</div>
          <h1>Your Library</h1>
          <p>Generated songs, playlists and liked tracks — all in one place.</p>
        </div>
        <Link className="btn btn-primary" href="/create">
          <Icon name="fa-plus" /> Create a song
        </Link>
      </div>

      <div className="stats-row">
        <div className="stat-card">
          <b>{generations.length}</b>
          <span>Generations</span>
        </div>
        <div className="stat-card">
          <b>{playlists.length}</b>
          <span>Playlists</span>
        </div>
        <div className="stat-card">
          <b>{liked.length}</b>
          <span>Liked tracks</span>
        </div>
        <div className="stat-card">
          <b>{(credits ?? 0).toLocaleString()}</b>
          <span>Credits</span>
        </div>
      </div>

      {error ? (
        <div className="panel library-error" role="alert">
          {error}
        </div>
      ) : null}

      <div className="tabs" role="tablist" aria-label="Library sections">
        {tabs.map((item) => (
          <button
            className={`tab${tab === item.id ? " on" : ""}`}
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {!hasAnything ? (
        emptyState
      ) : (
        <>
          {tab === "all" ? (
            <>
              {generations.length ? (
                <>
                  <div className="sec-head">
                    <h2>Recent generations</h2>
                    <Link href="/create">Create more</Link>
                  </div>
                  {generationList}
                </>
              ) : null}
              {playlists.length ? (
                <>
                  <div className="sec-head" style={{ marginTop: 30 }}>
                    <h2>Playlists</h2>
                  </div>
                  {playlistList}
                </>
              ) : null}
              {liked.length ? (
                <>
                  <div className="sec-head" style={{ marginTop: 30 }}>
                    <h2>Liked tracks</h2>
                  </div>
                  {likedList}
                </>
              ) : null}
            </>
          ) : null}

          {tab === "generated" ? (
            generations.length ? generationList : (
              <div className="library-empty compact">
                <h2>No generations yet.</h2>
                <p>Create your first track in the studio.</p>
              </div>
            )
          ) : null}

          {tab === "playlists" ? (
            playlists.length ? playlistList : (
              <div className="library-empty compact">
                <h2>No playlists yet.</h2>
                <p>Playlists you create will appear here.</p>
              </div>
            )
          ) : null}

          {tab === "liked" ? (
            liked.length ? likedList : (
              <div className="library-empty compact">
                <h2>No liked tracks yet.</h2>
                <p>Tap the heart on any track to save it here.</p>
              </div>
            )
          ) : null}
        </>
      )}
    </div>
  );
}
