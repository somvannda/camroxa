"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import {
  CreatorButton,
  CreatorButtonLink,
  CreatorField,
  CreatorHeader,
  CreatorInput,
  CreatorPage,
  CreatorPanel,
  CreatorSelect,
  CreatorTextarea,
  creatorButtonClass,
} from "@/components/CreatorUI";
import styles from "@/components/creator-ui.module.css";
import {
  checkHandle,
  claimCreator,
  CreatorApiError,
  fetchMyCreator,
  updateCreator,
  uploadCreatorMedia,
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
  banner_url: string;
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
  banner_url: "",
  ai_disclosure: "none",
};

const CHECKLIST_LABELS: Array<[string, string]> = [
  ["handle", "Handle"],
  ["display_name", "Name"],
  ["bio", "Bio"],
  ["avatar", "Avatar"],
  ["genre", "Genre"],
  ["first_release", "First release"],
  ["verified", "Verified"],
  ["payout_ready", "Payout ready"],
];

function formFromProfile(profile: CreatorStudioProfile): FormState {
  return {
    handle: profile.handle,
    display_name: profile.display_name,
    tagline: profile.tagline ?? "",
    bio: profile.bio ?? "",
    city: profile.city ?? "",
    genres: profile.genres.join(", "),
    avatar_url: profile.avatar_url ?? "",
    banner_url: profile.banner_url ?? "",
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
    banner_url: form.banner_url.trim() || undefined,
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
  const [uploading, setUploading] = useState<"avatar" | "banner" | null>(null);

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

  async function onUpload(kind: "avatar" | "banner", file: File) {
    setUploading(kind);
    setError("");
    setSuccess("");
    try {
      const { url } = await uploadCreatorMedia(kind, file);
      setForm((current) => ({
        ...current,
        [kind === "avatar" ? "avatar_url" : "banner_url"]: url,
      }));
      setSuccess(kind === "avatar" ? "Avatar uploaded." : "Banner uploaded.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not upload image");
    } finally {
      setUploading(null);
    }
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();    setSaving(true);
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
    return (
      <CreatorPage>
        <CreatorHeader meta="Creator Studio" title="Creator Studio" />
        <div className={styles.skeletonPanel}>
          <div className={styles.skeleton} style={{ width: 260, height: 28 }} />
          <div className={styles.skeleton} style={{ width: "100%", height: 120 }} />
          <div className={styles.skeleton} style={{ width: "100%", height: 320 }} />
        </div>
      </CreatorPage>
    );
  }

  if (unauthorized) {
    return (
      <CreatorPage>
        <CreatorHeader meta="Creator Studio" title="Creator Studio" />
        <CreatorPanel>
          <div className={styles.empty}>
            <p className={styles.emptyTitle}>Sign in to continue</p>
            <p className={styles.emptyBody}>Claim your creator page, edit your profile, and track readiness.</p>
            <div>
              <CreatorButtonLink href="/login?next=/creator" variant="primary">
                <Icon name="fa-right-to-bracket" /> Sign in
              </CreatorButtonLink>
            </div>
          </div>
        </CreatorPanel>
      </CreatorPage>
    );
  }

  const profile = studio?.profile ?? null;
  const checklist = studio?.checklist ?? {};
  const completed = Object.values(checklist).filter(Boolean).length;

  return (
    <CreatorPage>
      <CreatorHeader
        meta="Creator Studio"
        title={profile ? profile.display_name : "Claim your creator page"}
        description={
          profile
            ? `@${profile.handle} · ${profile.tier} · ${profile.status}`
            : "Pick a handle, add a short bio, and publish your public creator page."
        }
        actions={
          <>
            {profile ? (
              <CreatorButtonLink href={`/creators/${profile.handle}`} variant="secondary">
                <Icon name="fa-arrow-up-right-from-square" /> View public page
              </CreatorButtonLink>
            ) : null}
            <CreatorButtonLink href="/creator/releases" variant="ghost">
              <Icon name="fa-record-vinyl" /> Releases
            </CreatorButtonLink>
            <CreatorButtonLink href="/creator/earnings" variant="ghost">
              <Icon name="fa-chart-line" /> Earnings
            </CreatorButtonLink>
            <CreatorButtonLink href="/creator/payouts" variant="ghost">
              <Icon name="fa-wallet" /> Payouts
            </CreatorButtonLink>
            <CreatorButtonLink href="/creator/verification" variant="ghost">
              <Icon name="fa-circle-check" /> Verification
            </CreatorButtonLink>
            <CreatorButtonLink href="/creators" variant="ghost">
              <Icon name="fa-users" /> Browse creators
            </CreatorButtonLink>
          </>
        }
      />

      {error ? <p className={styles.error} role="alert">{error}</p> : null}
      {success ? <p className={styles.success} role="status">{success}</p> : null}

      {profile ? (
        <CreatorPanel title="Profile readiness" meta={`${completed} of 8 complete`}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0 24px" }}>
            {CHECKLIST_LABELS.map(([key, label]) => (
              <div
                key={key}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  padding: "8px 0",
                  borderBottom: "1px solid rgba(255,255,255,0.06)",
                }}
              >
                <span className={styles.hint}>{label}</span>
                <span style={{ color: checklist[key] ? "#74c69d" : "#7d818b", fontSize: 12 }}>
                  {checklist[key] ? "Done" : "Missing"}
                </span>
              </div>
            ))}
          </div>
        </CreatorPanel>
      ) : null}

      <CreatorPanel
        title={profile ? "Edit profile" : "Create your profile"}
        meta={profile ? "Changes appear on your public page." : undefined}
        className={profile ? styles.sectionGap : ""}
      >
        <form className={styles.form} onSubmit={onSubmit}>
          <CreatorField label="Handle" htmlFor="creator-handle">
            <div style={{ display: "flex", gap: 8 }}>
              <CreatorInput
                id="creator-handle"
                value={form.handle}
                onChange={(event) => setForm({ ...form, handle: event.target.value.toLowerCase() })}
                placeholder="sokha"
                minLength={3}
                maxLength={30}
                required
              />
              {!profile ? (
                <CreatorButton variant="secondary" type="button" onClick={onCheckHandle} disabled={checking}>
                  <Icon name="fa-check" /> {checking ? "Checking…" : "Check"}
                </CreatorButton>
              ) : null}
            </div>
            {handleCheck ? (
              <span className={handleCheck.available ? styles.success : styles.error}>
                {handleCheck.available
                  ? "Available"
                  : `Unavailable (${handleCheck.reason}). Try: ${handleCheck.suggestions.join(", ") || "another name"}`}
              </span>
            ) : null}
          </CreatorField>

          <CreatorField label="Display name" htmlFor="creator-name">
            <CreatorInput
              id="creator-name"
              value={form.display_name}
              onChange={(event) => setForm({ ...form, display_name: event.target.value })}
              placeholder="Sokha Chan"
              maxLength={50}
              required
            />
          </CreatorField>

          <CreatorField label="Tagline" htmlFor="creator-tagline">
            <CreatorInput
              id="creator-tagline"
              value={form.tagline}
              onChange={(event) => setForm({ ...form, tagline: event.target.value })}
              placeholder="Khmer pop for the ride home."
              maxLength={120}
            />
          </CreatorField>

          <CreatorField label="Bio" htmlFor="creator-bio">
            <CreatorTextarea
              id="creator-bio"
              value={form.bio}
              onChange={(event) => setForm({ ...form, bio: event.target.value })}
              placeholder="Tell listeners who you are and what you make."
              maxLength={2000}
              rows={4}
            />
          </CreatorField>

          <CreatorField label="City" htmlFor="creator-city">
            <CreatorInput
              id="creator-city"
              value={form.city}
              onChange={(event) => setForm({ ...form, city: event.target.value })}
              placeholder="Phnom Penh"
              maxLength={80}
            />
          </CreatorField>

          <CreatorField label="Genres (comma-separated, max 3)" htmlFor="creator-genres">
            <CreatorInput
              id="creator-genres"
              value={form.genres}
              onChange={(event) => setForm({ ...form, genres: event.target.value })}
              placeholder="Khmer Pop, Synth Pop"
            />
          </CreatorField>

          <CreatorField label="Avatar" htmlFor="creator-avatar-file" hint="Square image, at least 400×400px. JPG, PNG, or WebP.">
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 16 }}>
              {form.avatar_url ? (
                <img src={form.avatar_url} alt="" className={styles.avatar} />
              ) : (
                <span className={styles.avatarFallback} aria-hidden="true">
                  {form.display_name.slice(0, 1).toUpperCase() || "C"}
                </span>
              )}
              <label className={creatorButtonClass("secondary")} style={{ cursor: "pointer" }}>
                <Icon name="fa-upload" /> {uploading === "avatar" ? "Uploading…" : "Upload avatar"}
                <input
                  id="creator-avatar-file"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  hidden
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void onUpload("avatar", file);
                    event.currentTarget.value = "";
                  }}
                />
              </label>
            </div>
          </CreatorField>

          <CreatorField label="Banner" htmlFor="creator-banner-file" hint="Wide image, at least 1200×400px. The center is kept on mobile.">
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 16 }}>
              {form.banner_url ? (
                <img
                  src={form.banner_url}
                  alt=""
                  style={{ width: 220, height: 72, objectFit: "cover", borderRadius: 10, border: "1px solid var(--line)" }}
                />
              ) : (
                <span
                  style={{ width: 220, height: 72, borderRadius: 10, background: "var(--panel2)", border: "1px solid var(--line)" }}
                  aria-hidden="true"
                />
              )}
              <label className={creatorButtonClass("secondary")} style={{ cursor: "pointer" }}>
                <Icon name="fa-upload" /> {uploading === "banner" ? "Uploading…" : "Upload banner"}
                <input
                  id="creator-banner-file"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  hidden
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void onUpload("banner", file);
                    event.currentTarget.value = "";
                  }}
                />
              </label>
            </div>
          </CreatorField>

          <CreatorField label="AI disclosure" htmlFor="creator-ai">
            <CreatorSelect
              id="creator-ai"
              value={form.ai_disclosure}
              onValueChange={(value) =>
                setForm({ ...form, ai_disclosure: value as FormState["ai_disclosure"] })
              }
              options={[
                { value: "none", label: "None (human-led)" },
                { value: "ai_assisted", label: "AI-assisted" },
                { value: "ai_artist", label: "AI artist" },
              ]}
              ariaLabel="AI disclosure"
            />
          </CreatorField>

          <div>
            <CreatorButton type="submit" disabled={saving}>
              <Icon name={profile ? "fa-floppy-disk" : "fa-user-plus"} />
              {saving ? "Saving…" : profile ? "Save profile" : "Create creator page"}
            </CreatorButton>
          </div>
        </form>
      </CreatorPanel>

      <CreatorPanel title="Next steps" className={styles.sectionGap}>
        <p className={styles.emptyBody}>
          Verification is optional. You can claim a page and publish without it. Payout identity
          verification is separate and only required when you request a payout.
        </p>
        <div className={styles.actions} style={{ marginTop: 16 }}>
          <CreatorButtonLink href="/creator/releases" variant="secondary">
            <Icon name="fa-record-vinyl" /> Open releases
          </CreatorButtonLink>
          <CreatorButtonLink href="/creator/verification" variant="ghost">
            <Icon name="fa-circle-check" /> Request the badge
          </CreatorButtonLink>
        </div>
      </CreatorPanel>
    </CreatorPage>
  );
}
