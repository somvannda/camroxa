"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/Icon";
import { getStudioSharedProject, type StudioProject } from "@/lib/studio-api";

type SharedLane = {
  id?: string;
  title?: string;
  style?: string;
  start?: number;
  duration?: number;
  color?: string;
};

function formatTime(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, "0")}`;
}

export default function SharedStudioPage() {
  const params = useParams<{ token: string }>();
  const token = Array.isArray(params?.token) ? params.token[0] : params?.token;
  const [project, setProject] = useState<StudioProject | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    let alive = true;
    getStudioSharedProject(token)
      .then((next) => {
        if (alive) setProject(next);
      })
      .catch((cause) => {
        if (alive) setError(cause instanceof Error ? cause.message : "Could not load project.");
      });
    return () => {
      alive = false;
    };
  }, [token]);

  const lanes = useMemo<SharedLane[]>(() => {
    const data = project?.data as { lanes?: SharedLane[] } | undefined;
    return Array.isArray(data?.lanes) ? data.lanes : [];
  }, [project]);

  const duration = useMemo(
    () => Math.max(1, ...lanes.map((lane) => Number(lane.start ?? 0) + Number(lane.duration ?? 0))),
    [lanes]
  );

  return (
    <main className="shared-studio-page">
      <header className="shared-studio-head">
        <Link href="/" className="shared-studio-brand">
          <Icon name="fa-wave-square" /> CAMXORA
        </Link>
        <span className="shared-studio-badge">Read-only Studio share</span>
      </header>

      {error ? (
        <section className="shared-studio-empty">
          <h1>Project unavailable</h1>
          <p>{error}</p>
        </section>
      ) : !project ? (
        <section className="shared-studio-empty">
          <p>Loading project…</p>
        </section>
      ) : (
        <section className="shared-studio-card">
          <div className="shared-studio-title">
            <div>
              <p className="shared-studio-kicker">STUDIO PROJECT</p>
              <h1>{project.title}</h1>
              <p>
                {project.bpm} BPM · {project.time_signature} · {lanes.length} track
                {lanes.length === 1 ? "" : "s"}
              </p>
            </div>
            <span className="shared-studio-time">{formatTime(duration)}</span>
          </div>

          <div className="shared-studio-timeline" aria-label="Read-only project timeline">
            {lanes.map((lane, index) => {
              const start = Math.max(0, Number(lane.start ?? 0));
              const length = Math.max(0.2, Number(lane.duration ?? 0));
              return (
                <div className="shared-studio-track" key={lane.id || index}>
                  <span>{lane.title || `Track ${index + 1}`}</span>
                  <div className="shared-studio-track-line">
                    <div
                      className="shared-studio-clip"
                      style={{
                        left: `${(start / duration) * 100}%`,
                        width: `${(length / duration) * 100}%`,
                        background: lane.color || "#8b5cf6",
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <footer className="shared-studio-footer">
            <span>Shared from CAMXORA Studio</span>
            <Link href="/create">
              Create your own <Icon name="fa-arrow-right" />
            </Link>
          </footer>
        </section>
      )}
    </main>
  );
}
