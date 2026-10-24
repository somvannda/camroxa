"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";
import { useAuth } from "./AuthProvider";

export function Topbar() {
  const { user, logout } = useAuth();
  const [accountOpen, setAccountOpen] = useState(false);
  const accountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (accountRef.current && !accountRef.current.contains(event.target as Node)) {
        setAccountOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setAccountOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  return (
    <header className="topbar">
      <Link className="mobile-brand" href="/">
        <img
          src="/camxora-logo.svg"
          alt=""
          style={{ width: 24, height: 24, borderRadius: 6 }}
        />
        Camxora
      </Link>

      <form className="search" action="/search" role="search">
        <Icon name="fa-magnifying-glass" />
        <input
          type="search"
          name="q"
          placeholder="Search songs, artists, genres..."
          aria-label="Search"
        />
      </form>

      <div className="top-actions">
        {user ? (
          <>
            <button className="icon-btn bell" type="button" aria-label="Notifications">
              <Icon name="fa-bell" />
              <span className="badge-dot" />
            </button>

            <Link className="btn-create signed-in-only" href="/create">
              <Icon name="fa-plus" />
              Create Music
            </Link>

            <div className="menu-wrap" ref={accountRef}>
              <button
                className={`account${accountOpen ? " open" : ""}`}
                type="button"
                aria-haspopup="menu"
                aria-expanded={accountOpen}
                onClick={() => setAccountOpen((value) => !value)}
              >
                <img src={user.avatar_url || "/hero.png"} alt={user.display_name} />
                <span className="account-text">
                  <strong>{user.display_name}</strong>
                </span>
                <Icon name="fa-chevron-down" className="chev" />
              </button>

              <div
                className={`menu account-menu${accountOpen ? " open" : ""}`}
                role="menu"
              >
                <div className="menu-head">
                  <strong>{user.display_name}</strong>
                </div>
                <Link href="/account" role="menuitem" onClick={() => setAccountOpen(false)}>
                  <Icon name="fa-user" /> Profile &amp; plan
                </Link>
                <Link href="/create" role="menuitem" onClick={() => setAccountOpen(false)}>
                  <Icon name="fa-plus" /> Create a song
                </Link>
                <Link href="/discover" role="menuitem" onClick={() => setAccountOpen(false)}>
                  <Icon name="fa-compass" /> Discover music
                </Link>
                {user.email_confirmed === false ? (
                  <Link
                    href={`/verify-email?email=${encodeURIComponent(user.email)}`}
                    role="menuitem"
                    onClick={() => setAccountOpen(false)}
                  >
                    <Icon name="fa-envelope" /> Verify email
                  </Link>
                ) : null}
                <button
                  className="menu-signout"
                  type="button"
                  role="menuitem"
                  onClick={async () => {
                    setAccountOpen(false);
                    await logout();
                    window.location.href = "/";
                  }}
                >
                  <Icon name="fa-arrow-right-from-bracket" /> Sign out
                </button>
              </div>
            </div>
          </>
        ) : (
          <>
            <Link className="btn btn-ghost guest-signin header-auth" href="/login">
              <Icon name="fa-arrow-right-to-bracket" /> Sign in
            </Link>
            <Link className="btn-create btn-signup header-auth" href="/signup">
              <Icon name="fa-user-plus" /> Sign up
            </Link>
          </>
        )}
      </div>
    </header>
  );
}
