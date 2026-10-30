"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { Icon } from "@/components/Icon";
import type { WebMusicGeneration } from "@/lib/library-api";
import {
  createStudioSession,
  listWebMusicGenerations,
  listWebMusicStudioProjects,
  studioSessionForClip,
} from "@/lib/web-music-api";

type ProjectRow = { id: string; name: string; updated_at?: string | null };

function groupLabel(value?: string | null): string {
  if (!value) return "Earlier";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Earlier";
  const today = new Date();
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  if (date >= startOfToday) return "Today";
  if (date >= startOfYesterday) return "Yesterday";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/**
 * Suno's Studio landing: resume a project on the left, start from one of your
 * songs on the right. Mirrors suno.com/studio, in Camxora's components.
 */
export function StudioLanding() {
  const router = useRouter();
  const [songs, setSongs] = useState<WebMusicGeneration[]>([]);
  const [projects, setProjects] = useState<ProjectRow[]>([]);
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<"all" | "instrumental" | "vocal">("all");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.allSettled([listWebMusicGenerations(50), listWebMusicStudioProjects()])
      .then(([songResult, projectResult]) => {
        if (!active) return;
        if (songResult.status === "fulfilled") setSongs(songResult.value.items);
        if (projectResult.status === "fulfilled") {
          setProjects(
            (projectResult.value.items ?? [])
              // The editor opens Suno projects; local rows without a Suno id
              // cannot be hydrated, so they are not offered as "resume".
              .filter((project) => Boolean(project.suno_project_id))
              .map((project) => ({
                id: String(project.suno_project_id),
                name: project.title || "Untitled Project",
                updated_at: project.updated_at ?? null,
              }))
          );
        }
      })
      .catch(() => {
        if (active) setError("Could not load your studio.");
      });
    return () => {
      active = false;
    };
  }, []);

  const readySongs = useMemo(
    () => songs.filter((song) => String(song.status).toUpperCase() === "SUCCESS"),
    [songs]
  );
  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    const byKind = readySongs.filter((song) => {
      if (kind === "all") return true;
      const instrumental = song.instrumental === true;
      return kind === "instrumental" ? instrumental : !instrumental;
    });
    if (!term) return byKind;
    return byKind.filter((song) =>
      `${song.title} ${song.style ?? ""}`.toLowerCase().includes(term)
    );
  }, [readySongs, search, kind]);

  const grouped = useMemo(() => {
    const map = new Map<string, WebMusicGeneration[]>();
    for (const song of filtered) {
      const key = groupLabel(song.created_at);
      const list = map.get(key) ?? [];
      list.push(song);
      map.set(key, list);
    }
    return Array.from(map.entries());
  }, [filtered]);

  async function newProject() {
    setBusyId("new");
    setError("");
    try {
      const session = await createStudioSession("Untitled Project");
      router.push(`/studio/editor?project=${encodeURIComponent(session.id)}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create a project");
    } finally {
      setBusyId(null);
    }
  }

  async function editSong(song: WebMusicGeneration) {
    setBusyId(song.id);
    setError("");
    try {
      const clip = song.clips?.find((item) => item.ready) ?? song.clips?.[0];
      const variant = clip?.variant === "alt" ? "alt" : "ok";
      const session = await studioSessionForClip(song.id, variant);
      router.push(`/studio/editor?project=${encodeURIComponent(session.project_id)}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not open this song");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="st-landing">
      <section className="st-landing-left">
        <h3 className="s-day">Pick up where you left off</h3>
        <div className="st-resume">
          <button
            type="button"
            className="st-new-card"
            onClick={() => void newProject()}
            disabled={busyId === "new"}
          >
            <Icon name="fa-plus" />
            <span>{busyId === "new" ? "Creating…" : "New empty project"}</span>
          </button>
          <div className="st-recent-card">
            {projects[0] ? (
              <button
                type="button"
                className="st-recent"
                onClick={() =>
                  router.push(
                    `/studio/editor?project=${encodeURIComponent(projects[0].id)}`
                  )
                }
              >
                <span className="st-recent-art" />
                <span>
                  <b>{projects[0].name}</b>
                  <small>{groupLabel(projects[0].updated_at)}</small>
                </span>
              </button>
            ) : (
              <div className="st-recent empty">
                <span className="st-recent-art" />
                <span>
                  <b>No projects yet</b>
                  <small>Start with a song on the right</small>
                </span>
              </div>
            )}
          </div>
        </div>
        <button
          type="button"
          className="st-see-all"
          onClick={() => {
            const first = projects[0];
            if (first) {
              router.push(`/studio/editor?project=${encodeURIComponent(first.id)}`);
            }
          }}
          disabled={!projects.length}
          title={projects.length ? "Open your latest project" : "No projects yet"}
        >
          See all projects <Icon name="fa-chevron-right" />
        </button>
      </section>

      <section className="st-landing-right">
        <h3 className="s-day">Or start from one of your songs</h3>
        <div className="st-song-head">
          <input
            className="s-input"
            placeholder="Search your songs…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            aria-label="Search your songs"
          />
          <select
            className="s-input st-kind"
            value={kind}
            aria-label="Filter songs"
            onChange={(event) =>
              setKind(event.target.value as "all" | "instrumental" | "vocal")
            }
          >
            <option value="all">All songs</option>
            <option value="instrumental">Instrumental</option>
            <option value="vocal">With vocals</option>
          </select>
          <button type="button" className="s-btn s-btn-ghost" onClick={() => void newProject()}>
            <Icon name="fa-plus" /> New
          </button>
        </div>

        {error ? <p className="s-error">{error}</p> : null}

        <div className="st-song-list">
          {grouped.length ? (
            grouped.map(([label, list]) => (
              <div key={label}>
                <div className="st-group">{label}</div>
                {list.map((song) => (
                  <div className="s-row s-row-compact" key={song.id}>
                    <span
                      className="st-song-art"
                      style={
                        song.clips?.[0]?.image_url
                          ? { backgroundImage: `url(${song.clips[0].image_url})` }
                          : undefined
                      }
                    />
                    <div className="s-row-body">
                      <div className="s-row-title">
                        <b>{song.title}</b>
                        <span className="s-tag">
                          {song.model_label || song.model || "V6"}
                        </span>
                      </div>
                      <div className="s-row-desc">{song.style || "—"}</div>
                    </div>
                    <button
                      type="button"
                      className="s-btn s-btn-ghost"
                      disabled={busyId === song.id}
                      onClick={() => void editSong(song)}
                    >
                      {busyId === song.id ? "Opening…" : "Edit in Studio"}
                    </button>
                  </div>
                ))}
              </div>
            ))
          ) : (
            <p className="s-note">No finished songs yet — create one first.</p>
          )}
        </div>
      </section>
    </div>
  );
}
