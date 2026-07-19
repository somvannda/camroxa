import Link from "next/link";
import {
  ArrowRight,
  Download,
  Image as ImageIcon,
  Music,
  Radio,
  Sparkles,
  Users,
  Video,
  Workflow,
} from "lucide-react";

import {
  MarketingFooter,
  MarketingHeader,
  getUserPortalBaseUrl,
} from "@/components/marketing/site-chrome";

export const revalidate = 300;
const STATS_REVALIDATE_SECONDS = revalidate;

type PublicStatsResponse = {
  updated_at: string;
  users_total: number;
  profiles_total: number;
  batches_total: number;
  songs_total: number;
  images_total: number;
  videos_total: number;
};

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function formatRelativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "just now";
  const minutes = Math.floor(ms / 60000);
  if (minutes <= 0) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default async function Home() {
  const userPortalBaseUrl = getUserPortalBaseUrl();

  const platformApiBaseUrl =
    process.env.NEXT_PUBLIC_PLATFORM_API_BASE_URL ??
    (process.env.NODE_ENV === "development"
      ? "http://localhost:8000/api/v1"
      : "https://api.camxora.com/api/v1");

  let publicStats: PublicStatsResponse | null = null;
  try {
    const response = await fetch(`${platformApiBaseUrl}/stats/public`, {
      next: { revalidate: STATS_REVALIDATE_SECONDS },
    });
    if (response.ok) {
      publicStats = (await response.json()) as PublicStatsResponse;
    }
  } catch {}

  return (
    <div className="relative flex flex-1 flex-col overflow-hidden">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-camxora-hero opacity-35" />
        <div className="absolute inset-0 bg-[radial-gradient(1100px_circle_at_14%_0%,rgba(168,85,247,0.14),transparent_34%),radial-gradient(1000px_circle_at_88%_14%,rgba(139,92,246,0.18),transparent_30%),radial-gradient(720px_circle_at_78%_82%,rgba(217,70,239,0.08),transparent_22%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(6,10,18,0.74),rgba(2,4,10,0.96))]" />
      </div>

      <MarketingHeader userPortalBaseUrl={userPortalBaseUrl} />

      <main className="relative mx-auto flex w-full max-w-7xl flex-1 flex-col gap-20 px-6 py-14 md:px-10 md:py-20">
        <section className="grid gap-12 border-b border-white/8 pb-16 lg:grid-cols-[minmax(0,1fr)_420px] lg:items-end">
          <div className="max-w-4xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs uppercase tracking-[0.18em] text-slate-100/80">
              <Sparkles className="h-3.5 w-3.5 text-fuchsia-200" />
              Windows desktop app
            </div>
            <h1 className="mt-6 font-display text-5xl font-semibold leading-[0.92] tracking-[-0.07em] text-white md:text-7xl">
              Produce branded music channels with one desktop studio.
            </h1>
            <p className="mt-6 max-w-3xl text-base leading-8 text-slate-200/72 md:text-lg">
              Camxora is the Windows app for generating songs, preparing images, building video
              templates, exporting MP4s, and publishing to YouTube — with progress tracking across
              every channel profile.
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <a
                className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-5 text-sm font-medium text-white shadow-[0_22px_54px_rgba(118,77,255,0.34)] transition hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400"
                href={`${userPortalBaseUrl}/register`}
              >
                Create account
                <ArrowRight className="h-4 w-4" />
              </a>
              <Link
                className="inline-flex h-12 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] px-5 text-sm font-medium text-white transition hover:bg-white/[0.06]"
                href="/pricing"
              >
                View pricing
              </Link>
              <Link
                className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-5 text-sm font-medium text-white transition hover:bg-white/[0.06]"
                href="/download"
              >
                <Download className="h-4 w-4" />
                Download for Windows
              </Link>
            </div>
          </div>

          <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5 ring-1 ring-white/6">
            <div className="border-b border-white/8 pb-4">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Inside the app</div>
                <div className="mt-2 font-display text-2xl font-semibold text-white">
                  Built for daily production.
                </div>
              </div>
            </div>

            <div className="mt-5 space-y-3">
              {[
                { label: "Music", value: "Batch songs & drafts" },
                { label: "Video", value: "Templates, preview, export" },
                { label: "Publish", value: "Progress & YouTube upload" },
              ].map((item) => (
                <div key={item.label} className="flex items-start justify-between gap-4 border-b border-white/6 pb-3 last:border-b-0 last:pb-0">
                  <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
                    {item.label}
                  </div>
                  <div className="text-right text-sm font-medium text-slate-100">{item.value}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="grid gap-8 border-y border-white/8 py-12">
          <div className="max-w-2xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Get started</div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
              From account to first export in three steps.
            </h2>
            <p className="mt-4 text-sm leading-7 text-slate-200/70 md:text-base">
              Sign up, pick a plan, then install Camxora and open your channel profiles in the
              desktop studio.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            {[
              { label: "Create account", detail: "Register and sign in to unlock your workspace." },
              { label: "Choose a plan", detail: "Match credits and channel capacity to your schedule." },
              { label: "Open Camxora", detail: "Install the Windows app and start a production run." },
            ].map((item, index) => (
              <div key={item.label} className="rounded-[24px] border border-white/10 bg-white/[0.03] p-6">
                <div className="text-[11px] uppercase tracking-[0.24em] text-slate-400">
                  Step {index + 1}
                </div>
                <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.04em] text-white">
                  {item.label}
                </div>
                <div className="mt-3 text-sm leading-7 text-slate-200/68">{item.detail}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="grid gap-8">
          <div className="max-w-3xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
              Desktop pipeline
            </div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
              One pipeline from song idea to published video.
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-200/70 md:text-base">
              Camxora walks each batch through music, images, video, merge, and upload so you can
              monitor every channel without juggling separate tools.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {[
              {
                step: "01",
                title: "Music",
                detail: "Generate drafts and Suno tracks in controlled batches.",
              },
              {
                step: "02",
                title: "Images",
                detail: "Create backgrounds and thumbnails for each song.",
              },
              {
                step: "03",
                title: "Video",
                detail: "Preview spectrum templates and export branded MP4s.",
              },
              {
                step: "04",
                title: "Merge",
                detail: "Combine outputs into final deliverables for the run.",
              },
              {
                step: "05",
                title: "Upload",
                detail: "Send finished videos to connected YouTube channels.",
              },
            ].map((item) => (
              <div
                key={item.step}
                className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 ring-1 ring-white/6"
              >
                <div className="text-[11px] uppercase tracking-[0.24em] text-slate-400">
                  Step {item.step}
                </div>
                <div className="mt-3 font-display text-2xl font-semibold text-white">
                  {item.title}
                </div>
                <div className="mt-3 text-sm leading-7 text-slate-200/70">{item.detail}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="grid gap-8">
          <div className="max-w-2xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">App workspace</div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
              Everything you need lives in the Camxora desktop app.
            </h2>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            {[
              {
                icon: Music,
                title: "Music workspace",
                detail: "Compose batches, manage channel pairs, and automate drafts through Suno.",
              },
              {
                icon: ImageIcon,
                title: "Image workspace",
                detail: "Generate and organize backgrounds and thumbnails for each track.",
              },
              {
                icon: Video,
                title: "Video studio",
                detail: "Design templates with spectrum, particles, logo, and text — then export.",
              },
              {
                icon: Workflow,
                title: "Progress & workflow",
                detail: "Watch every run stage, retry failed steps, and keep channels on schedule.",
              },
            ].map(({ icon: Icon, title, detail }) => (
              <div
                key={title}
                className="rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-6 ring-1 ring-white/6"
              >
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[linear-gradient(180deg,rgba(168,85,247,0.2),rgba(217,70,239,0.14))] text-white ring-1 ring-white/10">
                  <Icon className="h-4 w-4" />
                </div>
                <div className="mt-5 font-display text-2xl font-semibold text-white">{title}</div>
                <p className="mt-3 text-sm leading-7 text-slate-200/70">{detail}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-[32px] border border-white/10 bg-[linear-gradient(180deg,rgba(22,34,74,0.34),rgba(255,255,255,0.03))] px-6 py-7 ring-1 ring-white/6 md:px-8 md:py-8">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div className="max-w-2xl">
              <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Live platform activity</div>
              <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-4xl">
                Creators already shipping with Camxora.
              </div>
            </div>
            <div className="text-xs text-slate-300/60">
              {publicStats?.updated_at
                ? `Updated ${formatRelativeTime(publicStats.updated_at)}`
                : "Stats currently unavailable"}
            </div>
          </div>

          <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[
              { label: "Users", value: publicStats?.users_total ?? null, icon: Users },
              { label: "Profiles", value: publicStats?.profiles_total ?? null, icon: Radio },
              { label: "Songs", value: publicStats?.songs_total ?? null, icon: Music },
              { label: "Videos", value: publicStats?.videos_total ?? null, icon: Video },
            ].map((item) => {
              const Icon = item.icon;
              return (
                <div
                  key={item.label}
                  className="rounded-[24px] border border-white/10 bg-black/20 px-4 py-5"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="text-xs font-medium uppercase tracking-[0.22em] text-slate-300/60">
                      {item.label}
                    </div>
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.05] text-white">
                      <Icon className="h-4 w-4" />
                    </div>
                  </div>
                  <div className="mt-4 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-4xl">
                    {item.value === null ? "—" : formatCompactNumber(item.value)}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="grid gap-10 border-t border-white/8 pt-8 lg:grid-cols-[minmax(0,1fr)_420px]">
          <div className="max-w-2xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Ready when you are</div>
            <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-4xl">
              Install Camxora and start your next channel run.
            </div>
            <p className="mt-4 text-sm leading-7 text-slate-200/70 md:text-base">
              Create an account, download the Windows app, and keep music, video, and YouTube
              publishing in one place.
            </p>
          </div>

          <div className="rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] p-6 ring-1 ring-white/6 md:p-7">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Start now</div>
            <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white">
              Open the desktop studio.
            </div>
            <p className="mt-4 text-sm leading-7 text-slate-200/72">
              Your profiles, credits, and production tools are waiting in Camxora.
            </p>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              <a
                className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-5 text-sm font-medium text-white shadow-[0_18px_44px_rgba(118,77,255,0.3)] transition hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400"
                href={`${userPortalBaseUrl}/register`}
              >
                Create account
                <ArrowRight className="h-4 w-4" />
              </a>
              <Link
                className="inline-flex h-12 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] px-5 text-sm font-medium text-white transition hover:bg-white/[0.06]"
                href="/features"
              >
                Explore features
              </Link>
            </div>
          </div>
        </section>
      </main>

      <MarketingFooter userPortalBaseUrl={userPortalBaseUrl} />
    </div>
  );
}
