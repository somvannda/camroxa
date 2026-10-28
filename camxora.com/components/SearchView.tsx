"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Icon } from "@/components/Icon";
import { TrackCard } from "@/components/TrackCard";
import { searchPublicTracks, type SearchTrack } from "@/lib/search-api";

function formatPlays(value?: number | null): string {
  const count = Number(value ?? 0);
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (count >= 1_000) return `${Math.round(count / 1_000)}K`;
  return count > 0 ? String(count) : "New";
}

function formatDuration(value?: number | null): string {
  const seconds = Math.max(0, Math.round(Number(value ?? 180)));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

const suggestions = ["Khmer pop", "EDM", "R&B", "Ballad", "Lo-fi", "Hip-hop"];

export function SearchView() {
  const params = useSearchParams();
  const query = (params.get("q") ?? "").trim();
  const [input, setInput] = useState(query);
  const [items, setItems] = useState<SearchTrack[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setInput(query);
    if (!query) {
      setItems([]);
      setTotal(0);
      setLoading(false);
      setError("");
      return;
    }
    let active = true;
    setLoading(true);
    setError("");
    searchPublicTracks(query)
      .then((result) => {
        if (!active) return;
        setItems(result.items);
        setTotal(result.total);
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Search failed");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [query]);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Search</div>
          <h1>{query ? `Results for “${query}”` : "Find your next track."}</h1>
          <p>
            Search songs, artists and genres across the Camxora catalog.
          </p>
        </div>
      </div>

      <form className="search search-page-form" action="/search" role="search">
        <Icon name="fa-magnifying-glass" />
        <input
          type="search"
          name="q"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Search songs, artists, genres..."
          aria-label="Search"
          autoFocus
        />
      </form>

      {!query ? (
        <section className="search-suggestions">
          <div className="eyebrow">Try a genre</div>
          <div className="chip-row">
            {suggestions.map((item) => (
              <a key={item} className="chip2" href={`/search?q=${encodeURIComponent(item)}`}>
                {item}
              </a>
            ))}
          </div>
        </section>
      ) : null}

      {error ? (
        <p className="fine" style={{ color: "#f87171", marginBottom: 16 }} role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="fine" style={{ textAlign: "left" }}>Searching…</p>
      ) : query && !items.length && !error ? (
        <div className="search-empty">
          <span className="search-empty-icon"><Icon name="fa-music" /></span>
          <h2>No tracks found</h2>
          <p>
            We couldn’t find anything for “{query}”. Try a different spelling,
            artist name, or genre.
          </p>
        </div>
      ) : items.length ? (
        <>
          <div className="sec-head">
            <h2>{total.toLocaleString()} result{total === 1 ? "" : "s"}</h2>
          </div>
          <div className="cards">
            {items.map((track) => (
              <TrackCard
                key={track.id}
                image={track.cover_url || "/hero.png"}
                title={track.title || "Untitled"}
                artist={track.artist_name || "Camxora"}
                plays={formatPlays(track.play_count)}
                time={formatDuration(track.duration_seconds)}
              />
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
