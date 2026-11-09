"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { CreatorMetrics } from "@/components/CreatorMetrics";
import { CreatorApiError, fetchCreator, type CreatorProfile } from "@/lib/creator-api";

function formatCount(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString();
}

export function CreatorPublicView({ handle }: { handle: string }) {
  const [creator, setCreator] = useState<CreatorProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setNotFound(false);
    fetchCreator(handle)
      .then((data) => {
        if (active) setCreator(data);
      })
      .catch((cause) => {
        if (!active) return;
        if (cause instanceof CreatorApiError && cause.status === 404) {
          setNotFound(true);
        } else {
          setError(cause instanceof Error ? cause.message : "Could not load creator");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [handle]);

  if (loading) {
    return <div className="page"><p className="fine" style={{ textAlign: "left" }}>Loading creator…</p></div>;
  }

  if (notFound) {
    return (
      <div className="page">
        <div className="invite-signin panel">
          <span className="invite-hero-icon"><Icon name="fa-user-slash" /></span>
          <h1>Creator not found</h1>
          <p>This creator page does not exist or is no longer available.</p>
          <Link className="btn btn-primary" href="/creators">Browse creators</Link>
        </div>
      </div>
    );
  }

  if (error || !creator) {
    return (
      <div className="page">
        <p className="fine" style={{ color: "#f87171" }} role="alert">{error || "Creator unavailable"}</p>
        <Link className="btn btn-ghost" href="/creators">Back to creators</Link>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <p className="fine" style={{ margin: 0 }}>
            <Link href="/creators">Creators</Link> / {creator.handle}
          </p>
          <h1>{creator.display_name}</h1>
          <p>{creator.tagline || "Creator on Camxora."}</p>
        </div>
        <div className="page-actions">
          <button className="btn btn-primary" type="button" disabled title="Follows ship in Phase 2">
            <Icon name="fa-user-plus" /> Follow
          </button>
          {creator.support_enabled ? (
            <button className="btn btn-ghost" type="button" disabled title="Tips ship in Phase 3">
              <Icon name="fa-heart" /> Support
            </button>
          ) : null}
        </div>
      </div>

      <section className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <div
          style={{
            height: 190,
            background: creator.banner_url
              ? `center / cover no-repeat url(${creator.banner_url})`
              : "#15161d",
            borderBottom: "1px solid rgba(255,255,255,0.08)",
          }}
        />
        <div style={{ padding: "0 24px 24px", marginTop: -52 }}>
          {creator.avatar_url ? (
            <img
              src={creator.avatar_url}
              alt=""
              style={{ width: 112, height: 112, borderRadius: "50%", border: "4px solid #0a0e27", objectFit: "cover" }}
            />
          ) : (
            <span
              style={{
                display: "inline-flex", width: 112, height: 112, borderRadius: "50%",
                border: "4px solid #0a0e27", background: "#1b2a41", alignItems: "center",
                justifyContent: "center", fontSize: 40, fontWeight: 700,
              }}
            >
              {creator.display_name.slice(0, 1).toUpperCase()}
            </span>
          )}
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 16 }}>
            <div>
              <h2 style={{ margin: "10px 0 2px" }}>
                {creator.display_name}
                {creator.badges.includes("verified") ? (
                  <span title="Verified creator" style={{ color: "#60a5fa", marginLeft: 8 }}>✓</span>
                ) : null}
              </h2>
              <p className="fine" style={{ margin: 0 }}>@{creator.handle} · {creator.city || creator.country_code || "Cambodia"}</p>
            </div>
            <div className="chip-row" style={{ margin: 0 }}>
              {creator.genres.map((genre) => (
                <span className="chip2" key={genre}>{genre}</span>
              ))}
            </div>
          </div>
        </div>
      </section>

      <CreatorMetrics
        items={[
          { label: "Monthly listeners", value: formatCount(creator.stats.monthly_listeners) },
          { label: "Followers", value: formatCount(creator.stats.followers) },
          { label: "Releases", value: creator.stats.releases },
          { label: "Valid streams", value: formatCount(creator.stats.valid_streams) },
        ]}
      />

      <section className="panel">
        <div className="sec-head"><h2>About</h2></div>
        <p>{creator.bio || "This creator has not added a bio yet."}</p>
        <div className="chip-row" style={{ marginTop: 12 }}>
          <span className="chip2">AI: {creator.ai_disclosure.replace("_", " ")}</span>
          <span className="chip2">Tier: {creator.tier}</span>
          {creator.influences.map((influence) => (
            <span className="chip2" key={influence}>{influence}</span>
          ))}
        </div>
        {creator.links.length ? (
          <div className="page-actions" style={{ marginTop: 16 }}>
            {creator.links.map((link) => (
              <a className="btn btn-ghost" href={link.url} key={link.url} target="_blank" rel="noreferrer">
                {link.label}
              </a>
            ))}
          </div>
        ) : null}
      </section>

      <section className="panel">
        <div className="sec-head"><h2>Releases</h2></div>
        <p className="fine" style={{ textAlign: "left" }}>
          Release management ships in Phase 2. This creator has no published releases in the preview.
        </p>
      </section>
    </div>
  );
}
