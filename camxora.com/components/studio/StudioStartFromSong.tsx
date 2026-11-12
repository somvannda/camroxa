"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { fetchGenerations, type WebMusicGeneration } from "@/lib/library-api";
import { createStudioProject } from "@/lib/studio-api";
import { buildSeedFromSong, isSeedable, pickSeedClip } from "@/lib/studio-seed";

/**
 * "Start from a song" (roadmap W1.4, spec §10).
 *
 * Lists recent generations and opens a project that already contains the chosen
 * audio. Renders nothing when the user has no seedable songs, so the home never
 * shows an empty section.
 */
export function StudioStartFromSong() {
  const { user } = useAuth();
  const router = useRouter();
  const [songs, setSongs] = useState<WebMusicGeneration[] | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    void (async () => {
      try {
        const items = await fetchGenerations(8);
        if (!cancelled) setSongs(items.filter(isSeedable).slice(0, 6));
      } catch {
        if (!cancelled) setSongs([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user]);

  const openSong = useCallback(
    async (song: WebMusicGeneration) => {
      setBusyId(song.id);
      setError("");
      try {
        const seed = buildSeedFromSong(song);
        const created = await createStudioProject(seed);
        router.push(`/studio/editor?project=${encodeURIComponent(created.id)}`);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Could not open that song.");
        setBusyId(null);
      }
    },
    [router]
  );

  if (!songs || songs.length === 0) return null;

  return (
    <section className="studio-start-songs" aria-labelledby="studio-start-songs-title">
      <div className="studio-home-head">
        <div>
          <p className="studio-home-eyebrow">From your library</p>
          <h2 id="studio-start-songs-title" className="studio-start-songs-title">
            Start from a song
          </h2>
          <p className="studio-home-sub">
            Open a finished track as a new project and keep arranging it.
          </p>
        </div>
      </div>

      {error ? (
        <div className="studio-home-alert" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => setError("")}>
            Dismiss
          </button>
        </div>
      ) : null}

      <ul className="studio-home-grid">
        {songs.map((song) => {
          const clip = pickSeedClip(song);
          return (
            <li key={song.id} className="studio-card">
              <button
                type="button"
                className="studio-card-main"
                onClick={() => void openSong(song)}
                disabled={busyId === song.id}
              >
                <span className="studio-card-title">{song.title || "Untitled song"}</span>
                <span className="studio-card-meta">
                  {busyId === song.id ? "Opening…" : song.style?.slice(0, 56) || "No style"}
                </span>
                <span className="studio-card-foot">
                  {clip?.duration_seconds
                    ? `${Math.floor(clip.duration_seconds / 60)}:${String(
                        Math.floor(clip.duration_seconds % 60)
                      ).padStart(2, "0")}`
                    : "ready to open"}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
