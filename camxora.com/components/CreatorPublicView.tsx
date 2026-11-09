"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { CreatorMetrics } from "@/components/CreatorMetrics";
import {
  CreatorButton,
  CreatorButtonLink,
  CreatorHeader,
  CreatorPage,
  CreatorPanel,
  creatorButtonClass,
} from "@/components/CreatorUI";
import styles from "@/components/creator-ui.module.css";
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
    return (
      <CreatorPage>
        <CreatorHeader meta="Creator" title={`@${handle}`} />
        <div className={styles.skeletonPanel}>
          <div className={styles.skeleton} style={{ width: "100%", height: 190 }} />
          <div className={styles.skeleton} style={{ width: 260, height: 28 }} />
          <div className={styles.skeleton} style={{ width: "100%", height: 120 }} />
        </div>
      </CreatorPage>
    );
  }

  if (notFound) {
    return (
      <CreatorPage>
        <CreatorHeader meta="Creators" title="Creator not found" />
        <CreatorPanel>
          <div className={styles.empty}>
            <p className={styles.emptyTitle}>This creator is not available</p>
            <p className={styles.emptyBody}>The page may have been removed, renamed, or unpublished.</p>
            <div>
              <CreatorButtonLink href="/creators" variant="primary">Browse creators</CreatorButtonLink>
            </div>
          </div>
        </CreatorPanel>
      </CreatorPage>
    );
  }

  if (error || !creator) {
    return (
      <CreatorPage>
        <CreatorHeader meta="Creators" title={creator?.display_name ?? "Creator"} />
        <CreatorPanel>
          <p className={styles.error} role="alert">{error || "Creator unavailable"}</p>
          <div className={styles.actions} style={{ marginTop: 16 }}>
            <CreatorButtonLink href="/creators" variant="secondary">Back to creators</CreatorButtonLink>
          </div>
        </CreatorPanel>
      </CreatorPage>
    );
  }

  return (
    <CreatorPage>
      <CreatorHeader
        meta={`Creator / @${creator.handle}`}
        title={creator.display_name}
        description={creator.tagline || "Creator on Camxora."}
        actions={
          <>
            <CreatorButton variant="secondary" type="button" disabled title="Follows ship in Phase 2">
              <Icon name="fa-user-plus" /> Follow
            </CreatorButton>
            {creator.support_enabled ? (
              <CreatorButton variant="ghost" type="button" disabled title="Tips ship in Phase 3">
                <Icon name="fa-heart" /> Support
              </CreatorButton>
            ) : null}
            <CreatorButtonLink href="/creators" variant="ghost">
              <Icon name="fa-users" /> All creators
            </CreatorButtonLink>
          </>
        }
      />

      <section
        className={styles.panel}
        style={{ padding: 0, overflow: "hidden", marginBottom: 24 }}
      >
        <div
          style={{
            height: creator.banner_url ? 190 : 120,
            background: creator.banner_url
              ? `center / cover no-repeat url(${creator.banner_url})`
              : "var(--panel2)",
            borderBottom: "1px solid var(--line)",
          }}
        />
        <div style={{ padding: "0 24px 24px", marginTop: -52 }}>
          {creator.avatar_url ? (
            <img
              src={creator.avatar_url}
              alt=""
              className={styles.avatar}
              style={{ width: 112, height: 112, border: "4px solid var(--bg)" }}
            />
          ) : (
            <span
              className={styles.avatarFallback}
              style={{ width: 112, height: 112, border: "4px solid var(--bg)", fontSize: 34 }}
            >
              {creator.display_name.slice(0, 1).toUpperCase()}
            </span>
          )}
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 16 }}>
            <div>
              <h2 style={{ margin: "12px 0 2px", fontSize: 24, fontWeight: 600, letterSpacing: "-0.02em" }}>
                {creator.display_name}
                {creator.badges.includes("verified") ? (
                  <span title="Verified creator" style={{ color: "var(--lav)", marginLeft: 8 }}>✓</span>
                ) : null}
              </h2>
              <p className={styles.rowMeta} style={{ marginTop: 2 }}>
                @{creator.handle} · {creator.city || creator.country_code || "Cambodia"}
              </p>
            </div>
            <div className={styles.chipRow}>
              {creator.genres.map((genre) => (
                <span className={styles.genreChip} key={genre}>{genre}</span>
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

      <CreatorPanel title="About">
        <p className={styles.emptyBody} style={{ maxWidth: "72ch" }}>
          {creator.bio || "This creator has not added a bio yet."}
        </p>
        <p className={styles.rowMeta} style={{ marginTop: 16 }}>
          AI disclosure: {creator.ai_disclosure.replace("_", " ")} · Tier: {creator.tier}
        </p>
        {creator.influences.length ? (
          <p className={styles.rowMeta}>Influences: {creator.influences.join(", ")}</p>
        ) : null}
        {creator.links.length ? (
          <div className={styles.actions} style={{ marginTop: 16 }}>
            {creator.links.map((link) => (
              <a
                className={creatorButtonClass("secondary")}
                href={link.url}
                key={link.url}
                target="_blank"
                rel="noreferrer"
              >
                {link.label}
              </a>
            ))}
          </div>
        ) : null}
      </CreatorPanel>

      <CreatorPanel title="Releases" meta="0 published" className={styles.sectionGap}>
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>No published releases yet</p>
          <p className={styles.emptyBody}>
            Release management ships in Phase 2. Published releases will appear here and in the catalog.
          </p>
        </div>
      </CreatorPanel>
    </CreatorPage>
  );
}
