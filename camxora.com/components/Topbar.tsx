"use client";

import Link from "next/link";
import { Icon } from "./Icon";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import { useAuth } from "./AuthProvider";

export function Topbar() {
  const { user, logout } = useAuth();

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
            <Link className="icon-btn bell" href="/notifications" aria-label="Notifications">
              <Icon name="fa-bell" />
              <span className="badge-dot" />
            </Link>

            <Link className="btn-create signed-in-only" href="/create">
              <Icon name="fa-plus" />
              Create Music
            </Link>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="account" type="button">
                  <img src={user.avatar_url || "/hero.png"} alt={user.display_name} />
                  <span className="account-text">
                    <strong>{user.display_name}</strong>
                  </span>
                  <Icon name="fa-chevron-down" className="chev" />
                </button>
              </DropdownMenuTrigger>

              <DropdownMenuContent
                className="account-menu"
                align="end"
                sideOffset={10}
              >
                <div className="menu-head">
                  <strong>{user.display_name}</strong>
                </div>

                <DropdownMenuItem asChild>
                  <Link href="/account">
                    <Icon name="fa-user" /> Profile &amp; plan
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link href="/artist-dashboard">
                    <Icon name="fa-chart-line" /> Creator dashboard
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link href="/create">
                    <Icon name="fa-plus" /> Create a song
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link href="/discover">
                    <Icon name="fa-compass" /> Discover music
                  </Link>
                </DropdownMenuItem>
                {user.email_confirmed === false ? (
                  <DropdownMenuItem asChild>
                    <Link
                      href={`/verify-email?email=${encodeURIComponent(user.email)}`}
                    >
                      <Icon name="fa-envelope" /> Verify email
                    </Link>
                  </DropdownMenuItem>
                ) : null}

                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="menu-signout"
                  onSelect={async () => {
                    await logout();
                    window.location.href = "/";
                  }}
                >
                  <Icon name="fa-arrow-right-from-bracket" /> Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
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
