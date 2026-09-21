"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { getUser, setSession } from "@/lib/auth";

interface Profile {
  id: string;
  email: string;
  name: string | null;
  created_at: string;
}

export default function SettingsPage() {
  const user = getUser();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState("");

  useEffect(() => {
    apiFetch<Profile>("/me/profile")
      .then((p) => {
        setProfile(p);
        setName(p.name ?? "");
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
      if (current) setSession(localStorage.getItem("suno_token") ?? "", { ...current, name: updated.name });
      setSuccess("Settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-white">Settings</h1>
      <p className="mt-1 text-sm text-white/50">Manage your account preferences.</p>

      {error && <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>}
      {success && <div className="mt-4 rounded-lg border border-[var(--emerald)]/30 bg-[var(--emerald)]/10 px-3 py-2 text-sm text-[var(--emerald)]">{success}</div>}

      <form onSubmit={save} className="glass mt-6 max-w-xl space-y-5 rounded-2xl p-6">
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
            className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)] text-white"
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
    </div>
  );
}
