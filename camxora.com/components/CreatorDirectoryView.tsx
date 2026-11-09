"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import {
  CreatorButtonLink,
  CreatorHeader,
  CreatorInput,
  CreatorPage,
  CreatorPanel,
  CreatorStatus,
} from "@/components/CreatorUI";
import styles from "@/components/creator-ui.module.css";
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
    <CreatorPage>
      <CreatorHeader
        meta="Creators"
        title="Creator directory"
        description="Verified and emerging creators building Khmer music on Camxora."
        actions={
          <CreatorButtonLink href="/creator" variant="primary">
            <Icon name="fa-microphone-lines" /> Open Creator Studio
          </CreatorButtonLink>
        }
      />

      <div className={styles.toolbar}>
        <div className={styles.searchField}>
          <Icon name="fa-magnifying-glass" />
          <CreatorInput
            className={styles.searchInput}
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search creators by name or handle"
            aria-label="Search creators"
          />
        </div>
      </div>

      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      {loading ? (
        <div className={styles.creatorGrid}>
          {[0, 1, 2, 3, 4, 5].map((item) => (
            <div className={styles.creatorCard} key={item}>
              <div className={styles.skeleton} style={{ width: 56, height: 56, borderRadius: "50%" }} />
              <div style={{ flex: 1, display: "grid", gap: 8 }}>
                <div className={styles.skeleton} style={{ width: "60%" }} />
                <div className={styles.skeleton} style={{ width: "40%" }} />
              </div>
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <CreatorPanel>
          <div className={styles.empty}>
            <p className={styles.emptyTitle}>No creators match “{query}”</p>
            <p className={styles.emptyBody}>Try another name, or claim your own creator page.</p>
            <div>
              <CreatorButtonLink href="/creator" variant="secondary">
                <Icon name="fa-user-plus" /> Claim a creator page
              </CreatorButtonLink>
            </div>
          </div>
        </CreatorPanel>
      ) : (
        <>
          <p className={styles.meta} style={{ marginBottom: 12 }}>
            {query ? `Results for “${query}”` : "Creators to follow"} · {items.length} shown
          </p>
          <div className={styles.creatorGrid}>
            {items.map((creator) => (
              <Link className={styles.creatorCard} href={`/creators/${creator.handle}`} key={creator.handle}>
                {creator.avatar_url ? (
                  <img src={creator.avatar_url} alt="" className={styles.avatar} />
                ) : (
                  <span className={styles.avatarFallback} aria-hidden="true">
                    {creator.display_name.slice(0, 1).toUpperCase()}
                  </span>
                )}
                <div style={{ minWidth: 0, flex: 1 }}>
                  <p className={styles.rowTitle}>{creator.display_name}</p>
                  <p className={styles.rowMeta}>
                    {creator.genres[0] ?? "Creator"} · {creator.stats.followers.toLocaleString()} followers
                  </p>
                </div>
                {creator.badges.includes("verified") ? (
                  <CreatorStatus label="Verified" tone="live" />
                ) : null}
              </Link>
            ))}
          </div>
        </>
      )}
    </CreatorPage>
  );
}
