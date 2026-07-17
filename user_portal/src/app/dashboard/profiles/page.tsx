"use client";

import Link from "next/link";

import { useControlPanel } from "@/components/dashboard/control-panel-provider";
import {
  EmptyPanel,
  ProfileCard,
  SectionTitle,
  getCoverCount,
  hasYouTubeConnection,
} from "@/components/dashboard/control-panel-ui";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ProfileAddonPanel } from "@/components/dashboard/profile-addon-panel";

export default function DashboardProfilesPage() {
  const { state } = useControlPanel();
  const logoReadyCount = state.profiles.filter((profile) => Boolean(profile.logo_path)).length;
  const youtubeLinkedCount = state.profiles.filter((profile) => hasYouTubeConnection(profile.youtube_config)).length;
  const totalCoverCount = state.profiles.reduce((sum, profile) => sum + getCoverCount(profile.image_config), 0);

  return (
    <div className="grid gap-6">
      <SectionTitle
        title="Channel Profiles And Assets"
        description="Review your completed channel identities, generated assets, and profile readiness."
      />

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-[24px] border border-white/10 bg-[linear-gradient(180deg,rgba(18,28,70,0.96),rgba(10,14,34,0.98))] p-5">
          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Profiles</div>
          <div className="mt-3 text-2xl font-semibold text-white">{state.profiles.length}</div>
          <div className="mt-2 text-sm text-slate-300/72">Channel identities currently attached to this account.</div>
        </div>
        <div className="rounded-[24px] border border-white/10 bg-[linear-gradient(180deg,rgba(16,22,52,0.94),rgba(9,12,28,0.98))] p-5">
          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Logos ready</div>
          <div className="mt-3 text-2xl font-semibold text-white">{logoReadyCount}</div>
          <div className="mt-2 text-sm text-slate-300/72">Profiles with a saved logo asset ready for production.</div>
        </div>
        <div className="rounded-[24px] border border-white/10 bg-[linear-gradient(180deg,rgba(16,22,52,0.94),rgba(9,12,28,0.98))] p-5">
          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Asset coverage</div>
          <div className="mt-3 text-2xl font-semibold text-white">{totalCoverCount} covers</div>
          <div className="mt-2 text-sm text-slate-300/72">
            {youtubeLinkedCount} profiles are currently linked to YouTube.
          </div>
        </div>
      </div>

      {state.user ? (
        <ProfileAddonPanel user={state.user} profileCount={state.profiles.length} />
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        {state.profiles.length > 0 ? (
          state.profiles.map((profile) => (
            <Link
              key={profile.id}
              href={`/dashboard/profiles/${profile.id}`}
              className="block transition hover:-translate-y-0.5"
            >
              <ProfileCard profile={profile} />
            </Link>
          ))
        ) : (
          <EmptyPanel text="No profiles are available yet." />
        )}
      </div>

      <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(16,22,52,0.94),rgba(9,12,28,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.3)]">
        <CardHeader>
          <CardTitle className="font-display text-2xl text-white">Profile actions</CardTitle>
          <CardDescription className="text-slate-300/72">
            Operational guidance for keeping channel identities ready for production.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
            <div className="text-sm font-medium text-white">Audit branding assets</div>
            <div className="mt-2 text-sm text-slate-300/72">
              Confirm logo and cover readiness before pushing new production cycles.
            </div>
          </div>
          <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
            <div className="text-sm font-medium text-white">Verify YouTube linkage</div>
            <div className="mt-2 text-sm text-slate-300/72">
              Keep channel connection details current so upload jobs do not fail later.
            </div>
          </div>
          <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
            <div className="text-sm font-medium text-white">Check output settings</div>
            <div className="mt-2 text-sm text-slate-300/72">
              Review resolution, folder, and run-prefix settings for consistency across profiles.
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
