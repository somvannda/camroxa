"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";
import { fetchGenerations, type WebMusicGeneration } from "@/lib/library-api";

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function isReady(generation: WebMusicGeneration): boolean {
  return generation.clips?.some((clip) => clip.ready) ?? false;
}

export function ArtistDashboardView() {
  const { user, credits, loading: authLoading } = useAuth();
  const [generations, setGenerations] = useState<WebMusicGeneration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setError("");
    fetchGenerations(50)
      .then((items) => {
        if (active) setGenerations(items);
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Could not load your catalog");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [authLoading, user]);

  if (authLoading) {
    return <p className="fine" style={{ textAlign: "left" }}>Loading…</p>;
  }

  if (!user) {
    return (
      <div className="page">
        <div className="invite-signin panel">
          <span className="invite-hero-icon"><Icon name="fa-chart-line" /></span>
          <h1>Creator dashboard</h1>
          <p>Sign in to see your catalog, generation status, and credit balance.</p>
          <Link className="btn btn-primary" href="/login?next=/artist-dashboard">Sign in</Link>
        </div>
      </div>
    );
  }

  const ready = generations.filter(isReady).length;
  const inProgress = generations.length - ready;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Creator dashboard</div>
          <h1>{user.display_name}</h1>
          <p>Your catalog, generation activity, and current credit balance.</p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-primary" href="/create">
            <Icon name="fa-plus" /> Create music
          </Link>
          <Link className="btn btn-ghost" href="/library">Open library</Link>
        </div>
      </div>

      {error ? (
        <p className="fine" style={{ color: "#f87171", marginBottom: 16 }} role="alert">{error}</p>
      ) : null}

      <div className="dash-stats">
        <div className="dash-stat"><b>{generations.length.toLocaleString()}</b><span>Total tracks</span></div>
        <div className="dash-stat"><b>{ready.toLocaleString()}</b><span>Ready to play</span></div>
        <div className="dash-stat"><b>{inProgress.toLocaleString()}</b><span>In progress</span></div>
        <div className="dash-stat"><b>{(credits ?? user.credit_balance ?? 0).toLocaleString()}</b><span>Credits left</span></div>
      </div>

      <section className="panel dash-panel">
        <div className="sec-head">
          <h2>Recent generations</h2>
          <Link href="/library">View all</Link>
        </div>
        {loading ? (
          <p className="fine" style={{ textAlign: "left" }}>Loading your catalog…</p>
        ) : !generations.length ? (
          <div className="invite-empty">
            <p>No tracks yet. Your first generation will appear here.</p>
            <Link className="btn btn-primary" href="/create">Create your first track</Link>
          </div>
        ) : (
          <div className="invite-table-wrap">
            <table className="invite-table dash-table">
              <thead>
                <tr>
                  <th>Track</th>
                  <th>Style</th>
                  <th>Status</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {generations.slice(0, 10).map((generation) => (
                  <tr key={generation.id}>
                    <td>{generation.title || "Untitled"}</td>
                    <td>{generation.style || generation.model || "—"}</td>
                    <td>
                      <span className={`invite-status ${isReady(generation) ? "rewarded" : "pending"}`}>
                        {isReady(generation) ? "Ready" : generation.status.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td>{formatDate(generation.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
