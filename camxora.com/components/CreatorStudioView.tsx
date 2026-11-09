"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import {
  checkHandle,
  claimCreator,
  CreatorApiError,
  fetchMyCreator,
  updateCreator,
  type CreatorStudioProfile,
  type CreatorStudioResponse,
} from "@/lib/creator-api";

type FormState = {
  handle: string;
  display_name: string;
  tagline: string;
  bio: string;
  city: string;
  genres: string;
  avatar_url: string;
  ai_disclosure: "none" | "ai_assisted" | "ai_artist";
};

const EMPTY_FORM: FormState = {
  handle: "",
  display_name: "",
  tagline: "",
  bio: "",
  city: "",
  genres: "",
  avatar_url: "",
  ai_disclosure: "none",
};

function formFromProfile(profile: CreatorStudioProfile): FormState {
  return {
    handle: profile.handle,
    display_name: profile.display_name,
    tagline: profile.tagline ?? "",
    bio: profile.bio ?? "",
    city: profile.city ?? "",
    genres: profile.genres.join(", "),
    avatar_url: profile.avatar_url ?? "",
    ai_disclosure: profile.ai_disclosure,
  };
}

function toPayload(form: FormState) {
  return {
    handle: form.handle.trim() || undefined,
    display_name: form.display_name.trim(),
    tagline: form.tagline.trim() || undefined,
    bio: form.bio.trim() || undefined,
    city: form.city.trim() || undefined,
    genres: form.genres.split(",").map((item) => item.trim()).filter(Boolean),
    avatar_url: form.avatar_url.trim() || undefined,
    ai_disclosure: form.ai_disclosure,
  };
}

export function CreatorStudioView() {
  const [studio, setStudio] = useState<CreatorStudioResponse | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [unauthorized, setUnauthorized] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [handleCheck, setHandleCheck] = useState<{ available: boolean; reason: string | null; suggestions: string[] } | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchMyCreator()
      .then((data) => {
        if (!active) return;
        setStudio(data);
        if (data.profile) setForm(formFromProfile(data.profile));
      })
      .catch((cause) => {
        if (!active) return;
        if (cause instanceof CreatorApiError && cause.status === 401) {
          setUnauthorized(true);
        } else {
          setError(cause instanceof Error ? cause.message : "Could not load Creator Studio");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function onCheckHandle() {
    if (!form.handle.trim()) return;
    setChecking(true);
    setHandleCheck(null);
    try {
      setHandleCheck(await checkHandle(form.handle.trim()));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not check handle");
    } finally {
      setChecking(false);
    }
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = toPayload(form);
      const data = studio?.profile
        ? await updateCreator(payload)
        : await claimCreator(payload);
      setStudio(data);
      if (data.profile) setForm(formFromProfile(data.profile));
      setSuccess(studio?.profile ? "Profile saved." : "Creator page created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save profile");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="page"><p className="fine" style={{ textAlign: "left" }}>Loading Creator Studio…</p></div>;
  }

  if (unauthorized) {
    return (
      <div className="page">
        <div className="invite-signin panel">
          <span className="invite-hero-icon"><Icon name="fa-microphone-lines" /></span>
          <h1>Creator Studio</h1>
          <p>Sign in to claim your creator page, edit your profile, and track your progress.</p>
          <Link className="btn btn-primary" href="/login?next=/creator">Sign in</Link>
        </div>
      </div>
    );
  }

  const profile = studio?.profile ?? null;
  const checklist = studio?.checklist ?? {};

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Creator Studio</div>
          <h1>{profile ? profile.display_name : "Claim your creator page"}</h1>
          <p>
            {profile
              ? `@${profile.handle} · ${profile.tier} · ${profile.status}`
              : "Pick a handle, add a short bio, and publish your public creator page."}
          </p>
        </div>
        <div className="page-actions">
          {profile ? (
            <Link className="btn btn-primary" href={`/creators/${profile.handle}`}>
              <Icon name="fa-arrow-up-right-from-square" /> View public page
            </Link>
          ) : null}
          <Link className="btn btn-ghost" href="/creators">Browse creators</Link>
        </div>
      </div>

      {error ? <p className="fine" style={{ color: "#f87171" }} role="alert">{error}</p> : null}
      {success ? <p className="fine" style={{ color: "#4ade80" }} role="status">{success}</p> : null}

      {profile ? (
        <div className="dash-stats">
          {[
            ["handle", "Handle"],
            ["display_name", "Name"],
            ["bio", "Bio"],
            ["avatar", "Avatar"],
            ["genre", "Genre"],
            ["first_release", "First release"],
            ["verified", "Verified"],
            ["payout_ready", "Payout ready"],
          ].map(([key, label]) => (
            <div className="dash-stat" key={key}>
              <b>{checklist[key] ? "✓" : "○"}</b>
              <span>{label}</span>
            </div>
          ))}
        </div>
      ) : null}

      <section className="panel">
        <div className="sec-head">
          <h2>{profile ? "Edit profile" : "Create your profile"}</h2>
          {profile ? <span className="fine">Changes appear on your public page.</span> : null}
        </div>

        <form onSubmit={onSubmit} style={{ display: "grid", gap: 16 }}>
          <div className="auth-field">
            <label htmlFor="creator-handle">Handle</label>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                id="creator-handle"
                className="auth-input"
                value={form.handle}
                onChange={(event) => setForm({ ...form, handle: event.target.value.toLowerCase() })}
                placeholder="sokha"
                minLength={3}
                maxLength={30}
                required
              />
              {!profile ? (
                <button className="btn btn-ghost" type="button" onClick={onCheckHandle} disabled={checking}>
                  {checking ? "Checking…" : "Check"}
                </button>
              ) : null}
            </div>
            {handleCheck ? (
              <span className="fine" style={{ color: handleCheck.available ? "#4ade80" : "#f87171" }}>
                {handleCheck.available
                  ? "Available"
                  : `Unavailable (${handleCheck.reason}). Try: ${handleCheck.suggestions.join(", ") || "another name"}`}
              </span>
            ) : null}
          </div>

          <div className="auth-field">
            <label htmlFor="creator-name">Display name</label>
            <input
              id="creator-name"
              className="auth-input"
              value={form.display_name}
              onChange={(event) => setForm({ ...form, display_name: event.target.value })}
              placeholder="Sokha Chan"
              maxLength={50}
              required
            />
          </div>

          <div className="auth-field">
            <label htmlFor="creator-tagline">Tagline</label>
            <input
              id="creator-tagline"
              className="auth-input"
              value={form.tagline}
              onChange={(event) => setForm({ ...form, tagline: event.target.value })}
              placeholder="Khmer pop for the ride home."
              maxLength={120}
            />
          </div>

          <div className="auth-field">
            <label htmlFor="creator-bio">Bio</label>
            <textarea
              id="creator-bio"
              className="auth-input"
              value={form.bio}
              onChange={(event) => setForm({ ...form, bio: event.target.value })}
              placeholder="Tell listeners who you are and what you make."
              maxLength={2000}
              rows={4}
              style={{ minHeight: 110, resize: "vertical" }}
            />
          </div>

          <div className="auth-field">
            <label htmlFor="creator-city">City</label>
            <input
              id="creator-city"
              className="auth-input"
              value={form.city}
              onChange={(event) => setForm({ ...form, city: event.target.value })}
              placeholder="Phnom Penh"
              maxLength={80}
            />
          </div>

          <div className="auth-field">
            <label htmlFor="creator-genres">Genres (comma-separated, max 3)</label>
            <input
              id="creator-genres"
              className="auth-input"
              value={form.genres}
              onChange={(event) => setForm({ ...form, genres: event.target.value })}
              placeholder="Khmer Pop, Synth Pop"
            />
          </div>

          <div className="auth-field">
            <label htmlFor="creator-avatar">Avatar URL</label>
            <input
              id="creator-avatar"
              className="auth-input"
              value={form.avatar_url}
              onChange={(event) => setForm({ ...form, avatar_url: event.target.value })}
              placeholder="https://..."
            />
          </div>

          <div className="auth-field">
            <label htmlFor="creator-ai">AI disclosure</label>
            <select
              id="creator-ai"
              className="auth-input"
              value={form.ai_disclosure}
              onChange={(event) => setForm({ ...form, ai_disclosure: event.target.value as FormState["ai_disclosure"] })}
            >
              <option value="none">None (human-led)</option>
              <option value="ai_assisted">AI-assisted</option>
              <option value="ai_artist">AI artist</option>
            </select>
          </div>

          <div className="page-actions">
            <button className="btn btn-primary" type="submit" disabled={saving}>
              {saving ? "Saving…" : profile ? "Save profile" : "Create creator page"}
            </button>
          </div>
        </form>
      </section>

      <section className="panel" style={{ marginTop: 16 }}>
        <div className="sec-head"><h2>Next steps</h2></div>
        <p className="fine" style={{ textAlign: "left" }}>
          Verification, releases, analytics, and payouts are the next phases. For now this page proves
          the identity flow: claim a handle, save a profile, and view the public creator page.
        </p>
      </section>
    </div>
  );
}
