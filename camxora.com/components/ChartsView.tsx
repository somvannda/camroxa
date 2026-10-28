"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { usePlayer } from "@/components/PlayerProvider";
import { fetchChartTracks, type ChartTrack } from "@/lib/charts-api";

function formatPlays(value?: number | null): string {
  const count = Number(value ?? 0);
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (count >= 1_000) return `${Math.round(count / 1_000)}K`;
  return count > 0 ? String(count) : "New";
}

function trackImage(track: ChartTrack): string {
  return track.cover_url || "/hero.png";
}

export function ChartsView() {
  const { playTrack } = usePlayer();
  const [tracks, setTracks] = useState<ChartTrack[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetchChartTracks()
      .then((items) => {
        if (!active) return;
        const sorted = [...items].sort((a, b) => {
          const plays = Number(b.play_count ?? 0) - Number(a.play_count ?? 0);
          if (plays !== 0) return plays;
          return String(b.added_at ?? "").localeCompare(String(a.added_at ?? ""));
        });
        setTracks(sorted);
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Could not load charts");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const play = (track: ChartTrack) => {
    playTrack({
      title: track.title || "Untitled",
      artist: track.artist_name || "Camxora",
      cover: trackImage(track),
      duration: 180,
      elapsed: 0,
    });
  };

  const podium = tracks.slice(0, 3);
  const rest = tracks.slice(3);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Charts</div>
          <h1>What Camxora is playing.</h1>
          <p>
            The tracks getting the most plays right now, ranked from the public
            Camxora catalog.
          </p>
        </div>
        {tracks[0] ? (
          <button className="btn btn-primary" type="button" onClick={() => play(tracks[0])}>
            <Icon name="fa-play" /> Play #1
          </button>
        ) : null}
      </div>

      {error ? (
        <p className="fine" style={{ color: "#f87171", marginBottom: 16 }} role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="fine" style={{ textAlign: "left" }}>Loading charts…</p>
      ) : !tracks.length ? (
        <div className="search-empty">
          <span className="search-empty-icon"><Icon name="fa-chart-simple" /></span>
          <h2>No chart data yet</h2>
          <p>
            Published tracks will appear here as creators share music and listeners
            start playing.
          </p>
        </div>
      ) : (
        <>
          {podium.length === 3 ? (
            <section className="chart-podium">
              {podium.map((track, index) => (
                <article key={track.id} className={`chart-podium-card rank-${index + 1}`}>
                  <img src={trackImage(track)} alt="" />
                  <div className="chart-podium-copy">
                    <span className="chart-podium-rank">#{index + 1}</span>
                    <h3>{track.title || "Untitled"}</h3>
                    <p>{track.artist_name || "Camxora"}</p>
                    <span className="chart-podium-plays">
                      <Icon name="fa-play" /> {formatPlays(track.play_count)} plays
                    </span>
                  </div>
                  <button
                    className="chart-play"
                    type="button"
                    aria-label={`Play ${track.title || "track"}`}
                    onClick={() => play(track)}
                  >
                    <Icon name="fa-play" />
                  </button>
                </article>
              ))}
            </section>
          ) : null}

          <section className="panel chart-table">
            <div className="chart-table-head">
              <span>#</span>
              <span>Track</span>
              <span>Genre</span>
              <span>Plays</span>
              <span />
            </div>
            {(podium.length === 3 ? rest : tracks).map((track, index) => {
              const rank = (podium.length === 3 ? index + 3 : index) + 1;
              return (
                <div className="chart-row" key={track.id}>
                  <span className="rank">{rank}</span>
                  <div className="chart-track">
                    <img src={trackImage(track)} alt="" />
                    <div>
                      <h3>{track.title || "Untitled"}</h3>
                      <p>{track.artist_name || "Camxora"}</p>
                    </div>
                  </div>
                  <span className="cell">{track.genre || track.style || "Music"}</span>
                  <span className="plays">{formatPlays(track.play_count)}</span>
                  <button
                    className="chart-row-play"
                    type="button"
                    aria-label={`Play ${track.title || "track"}`}
                    onClick={() => play(track)}
                  >
                    <Icon name="fa-play" />
                  </button>
                </div>
              );
            })}
          </section>
        </>
      )}
    </div>
  );
}
