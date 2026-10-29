"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Icon } from "./Icon";
import { useAuth } from "./AuthProvider";

const nav = [
  { href: "/", icon: "fa-house", label: "Home" },
  { href: "/discover", icon: "fa-compass", label: "Discover" },
  { href: "/create", icon: "fa-plus", label: "Create" },
  { href: "/studio/editor", icon: "fa-table-columns", label: "Studio" },
  { href: "/charts", icon: "fa-chart-simple", label: "Charts" },
  { href: "/library", icon: "fa-rectangle-list", label: "Library" },
  { href: "/community", icon: "fa-users", label: "Community" },
];

const playlists = [
  { href: "/library", icon: "fa-heart", label: "Liked Songs" },
  { href: "/playlists/chill-vibes", icon: "fa-music", label: "Chill Vibes" },
  { href: "/playlists/edm-party", icon: "fa-list-ul", label: "EDM Party" },
  { href: "/playlists/khmer-hits", icon: "fa-folder", label: "Khmer Hits" },
  { href: "/playlists/my-playlist", icon: "fa-folder", label: "My Playlist" },
];

const products = [
  { href: "/developers", icon: "fa-list-ul", label: "Music API" },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const inStudio =
    pathname === "/studio" || pathname.startsWith("/studio/");

  useEffect(() => {
    const root = document.documentElement;
    const stored = window.localStorage.getItem("camxora.sidebar.collapsed") === "1";
    const next = inStudio ? true : stored;
    setCollapsed(next);
    if (next) root.style.setProperty("--side", "76px");
    else root.style.removeProperty("--side");
    return () => {
      root.style.removeProperty("--side");
    };
  }, [inStudio]);

  function toggleSidebar() {
    const next = !collapsed;
    setCollapsed(next);
    window.localStorage.setItem("camxora.sidebar.collapsed", next ? "1" : "0");
    document.documentElement.style.setProperty("--side", next ? "76px" : "264px");
  }
  const { user, credits, creditExpiry, creditAllowance, creditIsFree, logout } = useAuth();
  const allowance =
    creditAllowance && creditAllowance > 0
      ? creditAllowance
      : Math.max(credits ?? 0, 1);
  const creditPercent = Math.min(
    100,
    Math.max(0, ((credits ?? 0) / allowance) * 100)
  );
  const expiryLabel = creditExpiry
    ? `${creditIsFree ? "Resets" : "Expires"} ${new Date(creditExpiry).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })}`
    : "No expiry";

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <aside className={`sidebar${collapsed ? " collapsed" : ""}`}>
      <Link className="brand" href="/">
        <img className="brand-mark" src="/camxora-logo.svg" alt="Camxora" />
        <span className="brand-name">Camxora</span>
      </Link>

      <button
        type="button"
        className="side-collapse"
        onClick={toggleSidebar}
        aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
        title={collapsed ? "Expand navigation" : "Collapse navigation"}
      >
        <Icon name={collapsed ? "fa-angles-right" : "fa-angles-left"} />
      </button>

      <div className="side-scroll">
        <nav className="nav" aria-label="Main navigation">
          {nav.map((item) => (
            <Link
              key={item.href}
              className={isActive(item.href) ? "active" : ""}
              href={item.href}
              aria-current={isActive(item.href) ? "page" : undefined}
            >
              <Icon name={item.icon} />
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="nav-divider" />
        <div className="side-label">Playlists</div>
        <div className="playlists">
          {playlists.map((item) => (
            <Link key={item.href} href={item.href}>
              <Icon name={item.icon} />
              {item.label}
            </Link>
          ))}
        </div>

        <div className="side-label" style={{ marginTop: 10 }}>
          Products
        </div>
        <div className="side-grid">
          {products.map((item) => (
            <Link key={item.href} href={item.href}>
              <Icon name={item.icon} />
              {item.label}
            </Link>
          ))}
        </div>

        <div className="side-label" style={{ marginTop: 10 }}>
          Rewards
        </div>
        <div className="side-grid">
          <Link href="/invite">
            <Icon name="fa-users" /> Invite friends
          </Link>
          <Link href="/redeem">
            <Icon name="fa-plus" /> Redeem code
          </Link>
        </div>
      </div>

      {user ? (
        <div className="side-account">
          <div className="guest-offer member-credit">
            <div className="guest-offer-head">
              <span className="guest-kicker">Your credits</span>
              <span className="guest-price member-tier">{user.plan_name || "Free"}</span>
            </div>
            <strong className="guest-amount member-amount">
              {(credits ?? user.credit_balance ?? 0).toLocaleString()} <small>credits</small>
            </strong>
            <div className="credit-bar">
              <i style={{ width: `${creditPercent}%` }} />
            </div>
            <div className="credit-meta">
              <span>1,000 = $5</span>
              <span>{user.email_confirmed === false ? "Verify email" : expiryLabel}</span>
            </div>
            <Link className="btn btn-primary" href="/pricing">
              <Icon name="fa-plus" /> Buy packs
            </Link>
          </div>
          <div className="member-profile">
            <Link className="member-profile-main" href="/account">
              <img src={user.avatar_url || "/hero.png"} alt={user.display_name} />
              <span className="member-copy">
                <strong>{user.display_name}</strong>
              </span>
            </Link>
            <button
              className="member-signout"
              type="button"
              aria-label="Sign out"
              title="Sign out"
              onClick={async () => {
                await logout();
                window.location.href = "/";
              }}
            >
              <Icon name="fa-arrow-right-from-bracket" />
            </button>
          </div>
        </div>
      ) : (
        <div className="side-account">
          <div className="guest-offer">
            <div className="guest-offer-head">
              <span className="guest-kicker">Start creating</span>
              <span className="guest-price">$5</span>
            </div>
            <strong className="guest-amount">1,000 credits</strong>
            <p>Make your first song. Listening is free.</p>
            <Link className="btn btn-primary" href="/signup">
              <Icon name="fa-user-plus" /> Create account
            </Link>
          </div>
          <Link className="guest-signin-row" href="/login">
            <span className="guest-signin-ico">
              <Icon name="fa-arrow-right-to-bracket" />
            </span>
            <span className="guest-signin-copy">
              <strong>Sign in</strong>
              <small>Already have an account?</small>
            </span>
            <Icon name="fa-arrow-right" className="guest-signin-arrow" />
          </Link>
        </div>
      )}
    </aside>
  );
}
