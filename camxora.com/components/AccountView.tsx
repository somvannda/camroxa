"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";

export function AccountView() {
  const { user, credits, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) {
      window.location.href = "/login?next=/account";
    }
  }, [loading, user]);

  if (loading) {
    return (
      <div className="page">
        <div className="page-head">
          <div>
            <div className="eyebrow">Your account</div>
            <h1>Account</h1>
            <p>Loading your profile…</p>
          </div>
        </div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Your account</div>
          <h1>{user.display_name}</h1>
          <p>{user.email}</p>
        </div>
      </div>

      <div className="stats-row">
        <div className="stat-card">
          <b>{(credits ?? user.credit_balance ?? 0).toLocaleString()}</b>
          <span>Credits remaining</span>
        </div>
        <div className="stat-card">
          <b>{user.plan_name || "Free"}</b>
          <span>Current plan</span>
        </div>
        <div className="stat-card">
          <b>{user.email_confirmed === false ? "Pending" : "Verified"}</b>
          <span>Email status</span>
        </div>
        <div className="stat-card">
          <b>{user.products?.length ? user.products.length : 1}</b>
          <span>Products</span>
        </div>
      </div>

      <section className="panel" style={{ padding: 22 }}>
        <div className="sec-head">
          <h2>Profile</h2>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <img
            src={user.avatar_url || "/hero.png"}
            alt={user.display_name}
            style={{ width: 64, height: 64, borderRadius: "50%", objectFit: "cover" }}
          />
          <div style={{ minWidth: 0 }}>
            <strong style={{ display: "block", fontSize: 16 }}>{user.display_name}</strong>
            <span style={{ display: "block", color: "var(--muted)", fontSize: 12, marginTop: 3 }}>
              {user.email}
            </span>
          </div>
          {user.email_confirmed === false ? (
            <Link
              className="btn btn-ghost"
              href={`/verify-email?email=${encodeURIComponent(user.email)}`}
              style={{ marginLeft: "auto" }}
            >
              Verify email
            </Link>
          ) : null}
        </div>
      </section>

      <section className="panel" style={{ padding: 22, marginTop: 16 }}>
        <div className="sec-head">
          <h2>Account</h2>
        </div>
        <div style={{ display: "grid", gap: 10 }}>
          <Link className="member-profile" href="/discover">
            <span className="member-profile-main">
              <span className="guest-signin-ico"><Icon name="fa-compass" /></span>
              <span className="member-copy">
                <strong>Discover music</strong>
                <small>Browse new releases and moods</small>
              </span>
            </span>
          </Link>
          <Link className="member-profile" href="/create">
            <span className="member-profile-main">
              <span className="guest-signin-ico"><Icon name="fa-plus" /></span>
              <span className="member-copy">
                <strong>Create a song</strong>
                <small>Open the studio</small>
              </span>
            </span>
          </Link>
        </div>
      </section>
    </div>
  );
}
