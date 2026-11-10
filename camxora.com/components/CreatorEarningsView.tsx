"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { CreatorMetrics } from "@/components/CreatorMetrics";
import {
  CreatorButtonLink,
  CREATOR_NAV_ITEMS,
  CreatorHeader,
  CreatorPage,
  CreatorPanel,
  CreatorSubnav,
  CreatorStatus,
} from "@/components/CreatorUI";
import styles from "@/components/creator-ui.module.css";
import {
  CreatorApiError,
  fetchEligibility,
  refreshEligibility,
  type CreatorEligibilityItem,
  type CreatorEligibilityResponse,
} from "@/lib/creator-api";

function percent(value: number, target: number): number {
  return Math.max(0, Math.min(100, Math.round((value / Math.max(1, target)) * 100)));
}

function statusTone(status: CreatorEligibilityItem["status"]): "neutral" | "review" | "live" | "danger" {
  if (status === "earning") return "live";
  if (status === "eligible" || status === "pending_verification") return "review";
  if (status === "suspended") return "danger";
  return "neutral";
}

function statusLabel(status: CreatorEligibilityItem["status"]): string {
  if (status === "eligible") return "Eligible to earn";
  if (status === "pending_verification") return "Pending verification";
  if (status === "earning") return "Earning";
  if (status === "suspended") return "Suspended";
  return "Not eligible";
}

export function CreatorEarningsView() {
  const [data, setData] = useState<CreatorEligibilityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [unauthorized, setUnauthorized] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    refreshEligibility()
      .then((payload) => {
        if (active) setData(payload);
      })
      .catch((cause) => {
        if (!active) return;
        if (cause instanceof CreatorApiError && cause.status === 401) {
          setUnauthorized(true);
          return;
        }
        // Refresh can fail while the table is being deployed; read what exists.
        fetchEligibility()
          .then((payload) => {
            if (active) setData(payload);
          })
          .catch((fallback) => {
            if (active) setError(fallback instanceof Error ? fallback.message : "Could not load eligibility");
          });
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <CreatorPage>
        <CreatorHeader meta="Your music" title="Earnings" />
        <div className={styles.skeletonPanel}>
          <div className={styles.skeleton} style={{ width: 220, height: 28 }} />
          <div className={styles.skeleton} style={{ width: "100%", height: 72 }} />
          <div className={styles.skeleton} style={{ width: "100%", height: 260 }} />
        </div>
      </CreatorPage>
    );
  }

  if (unauthorized) {
    return (
      <CreatorPage>
        <CreatorHeader meta="Your music" title="Earnings" />
        <CreatorPanel>
          <div className={styles.empty}>
            <p className={styles.emptyTitle}>Sign in to track earnings</p>
            <p className={styles.emptyBody}>See which tracks are eligible to earn and what is left to unlock.</p>
            <div>
              <CreatorButtonLink href="/login?next=/creator/earnings" variant="primary">
                <Icon name="fa-right-to-bracket" /> Sign in
              </CreatorButtonLink>
            </div>
          </div>
        </CreatorPanel>
      </CreatorPage>
    );
  }

  const items = data?.items ?? [];
  const summary = data?.summary ?? { tracks: 0, eligible: 0, earning: 0, valid_streams: 0 };

  return (
    <CreatorPage>
      <CreatorHeader
        meta="Your music"
        title="Earnings"
        description="Track which songs are eligible to earn. Payout verification is only required when you request a payout."
        actions={
          <>
            <CreatorButtonLink href="/creator" variant="ghost">
              <Icon name="fa-arrow-left" /> Back to Studio
            </CreatorButtonLink>
            <CreatorButtonLink href="/creator/payouts" variant="ghost">
              <Icon name="fa-shield-halved" /> Payout verification
            </CreatorButtonLink>
          </>
        }
      />

      <CreatorSubnav items={CREATOR_NAV_ITEMS} />

      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      <CreatorMetrics
        items={[
          { label: "Tracks", value: summary.tracks },
          { label: "Eligible", value: summary.eligible },
          { label: "Earning", value: summary.earning },
          { label: "Valid streams", value: summary.valid_streams.toLocaleString() },
        ]}
      />

      <CreatorPanel title="Track eligibility">
        {items.length === 0 ? (
          <div className={styles.empty}>
            <p className={styles.emptyTitle}>No eligible tracks yet</p>
            <p className={styles.emptyBody}>
              Publish a release and share it. Once a track reaches the threshold, it appears here
              and you get a notification.
            </p>
            <div>
              <CreatorButtonLink href="/creator/releases" variant="secondary">
                <Icon name="fa-record-vinyl" /> Open releases
              </CreatorButtonLink>
            </div>
          </div>
        ) : (
          <div className={styles.list}>
            {items.map((item) => {
              const canVerify = item.status === "eligible" || item.status === "pending_verification";
              return (
                <article className={styles.row} key={item.track_id}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: 10 }}>
                      <p className={styles.rowTitle}>{item.title || "Untitled"}</p>
                      <CreatorStatus label={statusLabel(item.status)} tone={statusTone(item.status)} />
                    </div>
                    <p className={styles.rowMeta}>
                      {item.origin === "original" ? "Original" : item.origin === "ai_assisted" ? "AI-assisted" : "AI-generated"}
                    </p>
                    <div className={styles.progressRow}>
                      <div className={styles.progressHead}>
                        <span>Valid streams</span>
                        <span>{item.valid_streams.toLocaleString()} / {item.threshold_streams.toLocaleString()}</span>
                      </div>
                      <div className={styles.progressTrack}>
                        <div className={styles.progressFill} style={{ width: `${percent(item.valid_streams, item.threshold_streams)}%` }} />
                      </div>
                    </div>
                    <div className={styles.progressRow}>
                      <div className={styles.progressHead}>
                        <span>Unique listeners</span>
                        <span>{item.unique_listeners.toLocaleString()} / {item.threshold_listeners.toLocaleString()}</span>
                      </div>
                      <div className={styles.progressTrack}>
                        <div className={styles.progressFill} style={{ width: `${percent(item.unique_listeners, item.threshold_listeners)}%` }} />
                      </div>
                    </div>
                  </div>
                  <div className={styles.rowActions}>
                    {canVerify ? (
                      <CreatorButtonLink href="/creator/payouts" variant="secondary">
                        <Icon name="fa-shield-halved" /> Complete verification
                      </CreatorButtonLink>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </CreatorPanel>

      <CreatorPanel title="How earning works" meta="Automatic" className={styles.sectionGap}>
        <div className={styles.guideGrid}>
          <div className={styles.guideStep}>
            <p className={styles.guideNumber}>01</p>
            <p className={styles.guideTitle}>Publish a track</p>
            <p className={styles.guideBody}>It goes live immediately after automated checks.</p>
          </div>
          <div className={styles.guideStep}>
            <p className={styles.guideNumber}>02</p>
            <p className={styles.guideTitle}>Reach the threshold</p>
            <p className={styles.guideBody}>Valid streams and unique listeners are counted automatically.</p>
          </div>
          <div className={styles.guideStep}>
            <p className={styles.guideNumber}>03</p>
            <p className={styles.guideTitle}>Verify once, earn monthly</p>
            <p className={styles.guideBody}>Complete payout verification when you are eligible; earnings accrue from that point.</p>
          </div>
        </div>
      </CreatorPanel>
    </CreatorPage>
  );
}
