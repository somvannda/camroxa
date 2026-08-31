'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { Camera, Download, ExternalLink, Library, Loader2, LogOut } from 'lucide-react';

import { useAuth } from '@/components/auth-provider';
import CreditBalanceCard from '@/components/credit-balance-card';
import QuotaRenewalCard from '@/components/quota-renewal-card';
import SubscriptionSection from '@/components/subscription-section';
import { getUserAvatarUrl, uploadMusicUserAvatar } from '@/lib/auth-api';
import { fetchCreditBalance, fetchMySubscription } from '@/lib/subscription-api';
import { getDownloadAppUrl } from '@/lib/site-urls';

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return 'U';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] ?? ''}${parts[1][0] ?? ''}`.toUpperCase();
}

export default function ProfilePageClient() {
  const { user, logout, refresh } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [avatarVersion, setAvatarVersion] = useState(0);
  const [planLabel, setPlanLabel] = useState('Free');

  useEffect(() => {
    if (!user) return;
    void (async () => {
      try {
        const [subscription, balance] = await Promise.all([
          fetchMySubscription().catch(() => null),
          fetchCreditBalance().catch(() => null),
        ]);
        if (subscription?.status === 'active') {
          setPlanLabel(
            subscription.plan_name
              .replace(/[-_\s]+(monthly|yearly)$/i, '')
              .replace(/_/g, ' ')
              .replace(/\b\w/g, (char) => char.toUpperCase()) || 'Pro',
          );
        } else if (balance?.has_subscription) {
          setPlanLabel('Pro');
        } else {
          setPlanLabel('Free');
        }
      } catch {
        setPlanLabel('Free');
      }
    })();
  }, [user?.id]);

  if (!user) return null;

  const avatarSrc = user.avatar_url
    ? getUserAvatarUrl(user.id, avatarVersion || user.avatar_url)
    : null;

  async function refreshPlanLabel() {
    if (!user) return;
    try {
      const [subscription, balance] = await Promise.all([
        fetchMySubscription().catch(() => null),
        fetchCreditBalance().catch(() => null),
      ]);
      if (subscription?.status === 'active') {
        setPlanLabel(
          subscription.plan_name
            .replace(/[-_\s]+(monthly|yearly)$/i, '')
            .replace(/_/g, ' ')
            .replace(/\b\w/g, (char) => char.toUpperCase()) || 'Pro',
        );
      } else if (balance?.has_subscription) {
        setPlanLabel('Pro');
      } else {
        setPlanLabel('Free');
      }
    } catch {
      setPlanLabel('Free');
    }
  }

  async function onPhotoSelected(file: File | null) {
    if (!file) return;
    setUploadingPhoto(true);
    setPhotoError(null);
    try {
      await uploadMusicUserAvatar(file);
      setAvatarVersion(Date.now());
      await refresh();
      await refreshPlanLabel();
    } catch (err) {
      setPhotoError(err instanceof Error ? err.message : 'Could not upload photo');
    } finally {
      setUploadingPhoto(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="overflow-hidden rounded-3xl border border-white/8 bg-gradient-to-br from-violet-600/15 via-[rgba(8,10,20,0.72)] to-transparent">
        <div className="flex flex-col gap-6 p-8 md:flex-row md:items-center">
          <div className="relative shrink-0">
            <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded-full border border-white/10 bg-white/[0.06] text-2xl font-semibold text-violet-100">
              {avatarSrc ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={avatarSrc} alt="" className="h-full w-full object-cover" />
              ) : (
                initials(user.display_name)
              )}
            </div>
            <button
              type="button"
              disabled={uploadingPhoto}
              onClick={() => fileInputRef.current?.click()}
              className="absolute bottom-0 right-0 inline-flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-[rgba(8,10,20,0.95)] text-slate-200 hover:bg-white/10 disabled:opacity-50"
              title="Change profile photo"
              aria-label="Change profile photo"
            >
              {uploadingPhoto ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Camera className="h-4 w-4" />
              )}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              onChange={(event) => void onPhotoSelected(event.target.files?.[0] ?? null)}
            />
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-xs uppercase tracking-[0.2em] text-fuchsia-100/70">Account</p>
              <span className="rounded-full border border-white/10 bg-white/[0.05] px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide text-slate-300">
                {planLabel}
              </span>
            </div>
            <h1 className="mt-2 truncate font-display text-3xl font-semibold text-white md:text-4xl">
              {user.display_name}
            </h1>
            <p className="mt-1 truncate text-slate-400">{user.email}</p>
            {photoError ? <p className="mt-2 text-sm text-rose-300">{photoError}</p> : null}
          </div>
        </div>

        <div className="flex flex-wrap gap-3 border-t border-white/8 px-8 py-5">
          <Link
            href="/library"
            className="inline-flex h-10 items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 text-sm text-slate-100 hover:bg-white/[0.08]"
          >
            <Library className="h-4 w-4" />
            Your Library
          </Link>
          <a
            href={getDownloadAppUrl()}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-10 items-center gap-2 rounded-xl border border-violet-400/25 bg-violet-500/10 px-4 text-sm text-violet-100 hover:bg-violet-500/15"
          >
            <Download className="h-4 w-4" />
            Download App
            <ExternalLink className="h-3.5 w-3.5 opacity-70" />
          </a>
          <button
            type="button"
            onClick={() => void logout()}
            className="inline-flex h-10 items-center gap-2 rounded-xl border border-white/10 px-4 text-sm text-slate-300 hover:bg-white/[0.04] hover:text-white"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </div>

      <CreditBalanceCard />
      <QuotaRenewalCard />
      <SubscriptionSection />
    </div>
  );
}
