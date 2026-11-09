"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { fetchCreators, type CreatorProfile } from "@/lib/creator-api";

export function CreatorDirectoryView() {
  const [items, setItems] = useState<CreatorProfile[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError("");
      fetchCreators({ q: query.trim() || undefined, limit: 24 })
        .then((data) => {
          if (active) setItems(data.items);
        })
        .catch((cause) => {
          if (active) setError(cause instanceof Error ? cause.message : "Could not load creators");
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [query]);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <p className="fine" style={{ margin: 0 }}>Creators</p>
          <h1>Creator directory</h1>
          <p>Verified and emerging creators building Khmer music on Camxora.</p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-primary" href="/creator">
            <Icon name="fa-microphone-lines" /> Open Creator Studio
          </Link>
        </div>
      </div>

      <form className="search search-page-form" role="search" onSubmit={(event) => event.preventDefault()}>
        <Icon name="fa-magnifying-glass" />
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search creators by name or handle..."
          aria-label="Search creators"
        />
      </form>

      {error ? (
        <p className="fine" style={{ color: "#f87171", marginBottom: 16 }} role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="fine" style={{ textAlign: "left" }}>Loading creators…</p>
      ) : items.length === 0 ? (
        <div className="invite-empty panel">
          <p>No creators match “{query}”.</p>
          <Link className="btn btn-ghost" href="/creator">Claim your creator page</Link>
        </div>
      ) : (
        <>
          <div className="sec-head">
            <h2>{query ? `Results for “${query}”` : "Creators to follow"}</h2>
            <span className="fine">{items.length} shown</span>
          </div>
          <div className="creator-grid">
            {items.map((creator) => (
              <Link className="creator-card" href={`/creators/${creator.handle}`} key={creator.handle}>
                {creator.avatar_url ? (
                  <img src={creator.avatar_url} alt="" />
                ) : (
                  <span
                    style={{
                      width: 72,
                      height: 72,
                      borderRadius: "50%",
                      background: "#1b2a41",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 24,
                      fontWeight: 700,
                      flex: "0 0 auto",
                    }}
                    aria-hidden="true"
                  >
                    {creator.display_name.slice(0, 1).toUpperCase()}
                  </span>
                )}
                <div>
                  <strong>
                    {creator.display_name}
                    {creator.badges.includes("verified") ? (
                      <span title="Verified creator" style={{ color: "#60a5fa", marginLeft: 6 }}>✓</span>
                    ) : null}
                  </strong>
                  <span>
                    {creator.genres[0] ?? "Creator"} · {creator.stats.followers.toLocaleString()} followers
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
