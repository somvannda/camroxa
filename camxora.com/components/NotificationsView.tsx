"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";
import {
  fetchNotifications,
  markNotificationsRead,
  type NotificationCenter,
  type NotificationItem,
} from "@/lib/notifications-api";

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function categoryIcon(category: string): string {
  if (category === "billing") return "fa-credit-card";
  if (category === "security") return "fa-shield-halved";
  if (category === "generation") return "fa-music";
  return "fa-bell";
}

export function NotificationsView() {
  const { user, loading: authLoading } = useAuth();
  const [data, setData] = useState<NotificationCenter | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setData(await fetchNotifications());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load notifications");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (authLoading || !user) return;
    void load();
  }, [authLoading, user]);

  async function markAllRead() {
    if (!data?.unread_count) return;
    setBusy(true);
    setError("");
    try {
      await markNotificationsRead(true);
      setData({ ...data, unread_count: 0 });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update notifications");
    } finally {
      setBusy(false);
    }
  }

  if (authLoading) {
    return <p className="fine" style={{ textAlign: "left" }}>Loading…</p>;
  }

  if (!user) {
    return (
      <div className="page">
        <div className="invite-signin panel">
          <span className="invite-hero-icon"><Icon name="fa-bell" /></span>
          <h1>Notifications</h1>
          <p>Sign in to see generation, billing, and account updates.</p>
          <Link className="btn btn-primary" href="/login?next=/notifications">Sign in</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Inbox</div>
          <h1>Notifications.</h1>
          <p>Generation results, billing updates, and account activity.</p>
        </div>
        <button
          className="btn btn-ghost"
          type="button"
          onClick={markAllRead}
          disabled={busy || !data?.unread_count}
        >
          <Icon name="fa-check" /> {busy ? "Updating…" : "Mark all read"}
        </button>
      </div>

      {error ? (
        <p className="fine" style={{ color: "#f87171", marginBottom: 16 }} role="alert">{error}</p>
      ) : null}

      {loading ? (
        <p className="fine" style={{ textAlign: "left" }}>Loading notifications…</p>
      ) : !data?.items.length ? (
        <div className="search-empty">
          <span className="search-empty-icon"><Icon name="fa-bell" /></span>
          <h2>You’re all caught up</h2>
          <p>New generation and account updates will appear here.</p>
        </div>
      ) : (
        <div className="notification-list">
          {data.items.map((item: NotificationItem) => (
            <article className={`notification-row${item.delivered ? "" : " unread"}`} key={item.id}>
              <span className="notification-icon">
                <Icon name={categoryIcon(item.category)} />
              </span>
              <div className="notification-copy">
                <div className="notification-top">
                  <span className="notification-category">{item.category}</span>
                  <span className="notification-time">{formatTime(item.created_at)}</span>
                </div>
                <h3>{item.title}</h3>
                <p>{item.message}</p>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
