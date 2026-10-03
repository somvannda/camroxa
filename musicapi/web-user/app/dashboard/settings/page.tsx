"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, logout } from "@/lib/api";
import { getUser, setSession } from "@/lib/auth";

interface Profile {
  id: string;
  email: string;
  name: string | null;
  email_subscription?: boolean;
  created_at: string;
}

export default function SettingsPage() {
  const router = useRouter();
  const user = getUser();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [name, setName] = useState("");
  const [emailSub, setEmailSub] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    apiFetch<Profile>("/me/profile")
      .then((p) => {
        setProfile(p);
        setName(p.name ?? "");
        setEmailSub(p.email_subscription !== false);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const updated = await apiFetch<Profile>("/me/profile", {
        method: "PUT",
        body: JSON.stringify({ name: name || null }),
      });
      setProfile(updated);
      const current = getUser();
      if (current) setSession({ ...current, name: updated.name });
      setSuccess("Settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function toggleEmailSub(next: boolean) {
    const previous = emailSub;
    setEmailSub(next);
    setError("");
    try {
      const updated = await apiFetch<Profile>("/me/profile", {
        method: "PUT",
        body: JSON.stringify({ email_subscription: next }),
      });
      setProfile(updated);
    } catch (err) {
      setEmailSub(previous);
      setError(err instanceof Error ? err.message : "Failed to update preference");
    }
  }

  async function doDelete() {
    setDeleting(true);
    setError("");
    try {
      await apiFetch("/me/account", { method: "DELETE" });
      await logout();
      router.push("/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete account");
      setDeleting(false);
    }
  }

  async function doLogout() {
    setLoggingOut(true);
    await logout();
    router.push("/login");
  }

  const emailMatches = !!profile?.email && deleteConfirm.trim().toLowerCase() === profile.email.toLowerCase();

  return (
    <div className="pb-16">
      <h1 className="text-2xl font-bold text-white">Settings</h1>
      <p className="mt-1 text-sm text-white/50">Manage your account settings and preferences</p>

      {error && <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>}
      {success && <div className="mt-4 rounded-lg border border-[var(--emerald)]/30 bg-[var(--emerald)]/10 px-3 py-2 text-sm text-[var(--emerald)]">{success}</div>}

      <div className="mt-6 grid max-w-3xl gap-6">
        {/* Account */}
        <form onSubmit={save} className="glass space-y-5 rounded-2xl p-6">
          <h2 className="text-lg font-semibold text-white">Account</h2>
          <div className="space-y-1">
            <label className="text-xs text-white/50">Email</label>
            <input disabled value={profile?.email ?? user?.email ?? ""} className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white/60" />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-white/50">Display name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Optional"
              className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-[var(--violet)]"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-white/50">Member since</label>
            <input disabled value={profile?.created_at ? new Date(profile.created_at).toLocaleDateString() : "—"} className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white/60" />
          </div>
          <div className="flex justify-end">
            <button type="submit" disabled={saving} className="grad-bg rounded-lg px-5 py-2 text-sm font-semibold text-white disabled:opacity-60">
              {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>

        {/* Notification Settings */}
        <div className="glass rounded-2xl p-6">
          <h2 className="text-lg font-semibold text-white">Notification Settings</h2>
          <div className="mt-4 flex items-start justify-between gap-4">
            <div>
              <div className="text-sm font-medium text-white">Email Subscription</div>
              <p className="mt-0.5 text-sm text-white/50">Receive product updates, new features, and promotional information</p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={emailSub}
              aria-label="Email subscription"
              onClick={() => toggleEmailSub(!emailSub)}
              className={`flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border border-white/10 p-0.5 transition-all ${emailSub ? "bg-[var(--violet)]" : "bg-white/5"}`}
            >
              <span className={`h-5 w-5 rounded-full bg-white shadow transition-transform duration-200 ${emailSub ? "translate-x-[18px]" : "translate-x-0"}`} />
            </button>
          </div>
        </div>

        {/* Log out */}
        <div className="glass rounded-2xl p-6">
          <h2 className="text-lg font-semibold text-white">Log Out</h2>
          <p className="mt-0.5 text-sm text-white/50">Sign out from this account on this device</p>
          <div className="mt-4 flex justify-end">
            <button
              type="button"
              onClick={doLogout}
              disabled={loggingOut}
              className="rounded-lg border border-white/10 bg-white/[0.03] px-4 py-2 text-sm font-medium text-white/80 transition hover:bg-white/10 disabled:opacity-60"
            >
              {loggingOut ? "Signing out..." : "Log Out"}
            </button>
          </div>
        </div>

        {/* Danger Zone */}
        <div className="rounded-2xl border border-red-500/25 bg-red-500/[0.04] p-6">
          <h2 className="text-lg font-semibold text-red-300">Danger Zone</h2>
          <p className="mt-0.5 text-sm text-white/50">Once you delete your account, there is no going back. Please be certain.</p>
          <div className="mt-4 flex justify-end">
            <button
              type="button"
              onClick={() => { setDeleteConfirm(""); setError(""); setDeleteOpen(true); }}
              className="rounded-lg bg-red-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-400"
            >
              Delete Account
            </button>
          </div>
        </div>
      </div>

      {deleteOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => !deleting && setDeleteOpen(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-md rounded-2xl border border-white/10 bg-[#14141c] p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-base font-semibold text-white">Delete Account</h3>
            <p className="mt-2 text-sm text-white/70">Are you absolutely sure you want to delete your account? This action cannot be undone.</p>
            <p className="mt-4 text-xs text-white/50">Please type <span className="font-semibold text-white">{profile?.email}</span> to confirm.</p>
            <input
              autoFocus
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              placeholder="Enter your account email to confirm"
              className="mt-2 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white outline-none focus:border-red-400/70 placeholder:text-white/30"
            />
            {deleteConfirm && !emailMatches && (
              <p className="mt-1.5 text-xs text-red-300">Email does not match the current account</p>
            )}
            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeleteOpen(false)}
                disabled={deleting}
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-white/70 transition hover:bg-white/5 hover:text-white disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={doDelete}
                disabled={!emailMatches || deleting}
                className="rounded-lg bg-red-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-400 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {deleting ? "Deleting…" : "Delete Account"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
