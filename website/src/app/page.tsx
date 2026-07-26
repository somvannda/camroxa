import Link from "next/link";
import {
  ArrowRight,
  Download,
  Image as ImageIcon,
  Music,
  Package,
  Sparkles,
  Video,
  Workflow,
} from "lucide-react";

import {
  MarketingFooter,
  MarketingHeader,
  getUserPortalBaseUrl,
} from "@/components/marketing/site-chrome";

export default async function Home() {
  const userPortalBaseUrl = getUserPortalBaseUrl();

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
              Faceless YouTube music
            </div>
            <h1 className="mt-6 font-display text-5xl font-semibold leading-[0.92] tracking-[-0.07em] text-white md:text-7xl">
              Build a faceless YouTube music channel with AI.
            </h1>
            <p className="mt-6 max-w-3xl text-base leading-8 text-slate-200/72 md:text-lg">
              No camera. No face. No studio. Write lyrics, create music, generate artwork, build
              videos, and export YouTube-ready MP4s — all in one Windows app.
            </p>

            <div className="mt-8 flex flex-col gap-3">
              <div className="flex flex-col gap-3 sm:flex-row">
                <a
                  className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-5 text-sm font-medium text-white shadow-[0_22px_54px_rgba(118,77,255,0.34)] transition hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400"
                  href={`${userPortalBaseUrl}/register`}
                >
                  Create account
                  <ArrowRight className="h-4 w-4" />
                </a>
                <Link
                  className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-5 text-sm font-medium text-white transition hover:bg-white/[0.06]"
                  href="/download"
                >
                  <Download className="h-4 w-4" />
                  Download for Windows
                </Link>
              </div>
              <p className="text-sm text-slate-300/70">
                <Link className="text-fuchsia-100/90 underline-offset-2 hover:underline" href="/compare">
                  Why Camxora
                </Link>
                <span className="mx-2 text-slate-500">·</span>
                <Link className="text-fuchsia-100/90 underline-offset-2 hover:underline" href="/pricing">
                  View pricing
                </Link>
              </p>
            </div>
          </div>

          <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5 ring-1 ring-white/6">
            <div className="border-b border-white/8 pb-4">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-slate-400">What you get</div>
                <div className="mt-2 font-display text-2xl font-semibold text-white">
                  One workflow. Ready for YouTube.
                </div>
              </div>
            </div>

            <div className="mt-5 space-y-3">
              {[
                { label: "Music", value: "Lyrics, drafts & songs" },
                { label: "Visuals", value: "Images, templates & export" },
                { label: "Progress", value: "Track every batch stage" },
              ].map((item) => (
                <div
                  key={item.label}
                  className="flex items-start justify-between gap-4 border-b border-white/6 pb-3 last:border-b-0 last:pb-0"
                >
                  <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
                    {item.label}
                  </div>
                  <div className="text-right text-sm font-medium text-slate-100">{item.value}</div>
                </div>
              ))}
            </div>
            <p className="mt-5 text-xs leading-6 text-slate-400">
              Auto YouTube upload is coming soon. Export finished videos today.
            </p>
          </div>
        </section>

        <section className="grid gap-8">
          <div className="max-w-3xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
              How it works
            </div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
              From idea to YouTube-ready video in one pipeline.
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-200/70 md:text-base">
              Stop jumping between lyric tools, music generators, image apps, and editors. Camxora
              keeps the full music-to-video path in one desktop studio.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {[
              {
                step: "01",
                title: "Lyrics",
                detail: "Draft and polish song lyrics from your ideas.",
              },
              {
                step: "02",
                title: "Music",
                detail: "Turn lyrics into complete songs in batches.",
              },
              {
                step: "03",
                title: "Images",
                detail: "Create artwork and thumbnails that match each track.",
              },
              {
                step: "04",
                title: "Video",
                detail: "Build branded templates, export, and merge MP4s.",
              },
              {
                step: "05",
                title: "YouTube-ready",
                detail: "Download finished videos. Auto-upload is coming soon.",
                soon: true,
              },
            ].map((item) => (
              <div
                key={item.step}
                className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 ring-1 ring-white/6"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="text-[11px] uppercase tracking-[0.24em] text-slate-400">
                    Step {item.step}
                  </div>
                  {"soon" in item && item.soon ? (
                    <span className="rounded-full border border-amber-400/30 bg-amber-500/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] text-amber-100">
                      Soon
                    </span>
                  ) : null}
                </div>
                <div className="mt-3 font-display text-2xl font-semibold text-white">
                  {item.title}
                </div>
                <div className="mt-3 text-sm leading-7 text-slate-200/70">{item.detail}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-[32px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] px-6 py-8 ring-1 ring-white/6 md:px-8">
          <div className="max-w-3xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
              Why creators switch
            </div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-4xl">
              From 10 hours a day to one hour — with one click.
            </h2>
            <p className="mt-4 text-sm leading-7 text-slate-200/70 md:text-base">
              Managing faceless channels by hand takes{" "}
              <strong className="text-white">at least 2 hours of high-effort work per channel,
              every day</strong>
              . Run a few channels and you can burn{" "}
              <strong className="text-white">10 hours a day</strong> just keeping content flowing.
              Camxora cuts that down to about{" "}
              <strong className="text-white">one hour</strong>: start the run, then sit back and
              watch the pipeline work.
            </p>
          </div>
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            <div className="rounded-[24px] border border-white/10 bg-black/20 px-5 py-6">
              <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Manual grind</div>
              <div className="mt-3 font-display text-3xl font-semibold text-white">~2 hrs / channel</div>
              <p className="mt-3 text-sm leading-7 text-slate-200/70">
                Lyrics, music, artwork, editing, and exports — repeated by hand across every
                channel you manage.
              </p>
            </div>
            <div className="rounded-[24px] border border-fuchsia-400/20 bg-[linear-gradient(180deg,rgba(168,85,247,0.14),rgba(0,0,0,0.2))] px-5 py-6">
              <div className="text-[11px] uppercase tracking-[0.22em] text-fuchsia-100/70">
                Camxora pipeline
              </div>
              <div className="mt-3 font-display text-3xl font-semibold text-white">~1 hr total</div>
              <p className="mt-3 text-sm leading-7 text-slate-200/70">
                One click. Sit and watch music, visuals, and video move through the pipeline —
                without babysitting five tools all day.
              </p>
            </div>
          </div>
        </section>

        <section className="rounded-[32px] border border-white/10 bg-[linear-gradient(180deg,rgba(22,34,74,0.34),rgba(255,255,255,0.03))] px-6 py-8 ring-1 ring-white/6 md:px-8">
          <div className="max-w-3xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Roadmap</div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-4xl">
              Shipping the full faceless channel system.
            </h2>
          </div>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {[
              {
                label: "Today",
                title: "Export YouTube-ready videos",
                detail: "Lyrics, music, images, templates, export, and merge — in the Windows app.",
              },
              {
                label: "Next",
                title: "Auto YouTube upload",
                detail: "Connect channels and publish finished videos without leaving Camxora.",
              },
              {
                label: "Later",
                title: "Broader social publishing",
                detail: "Expand beyond YouTube as the faceless social platform grows.",
              },
            ].map((item) => (
              <div
                key={item.label}
                className="rounded-[24px] border border-white/10 bg-black/20 px-5 py-6"
              >
                <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
                  {item.label}
                </div>
                <div className="mt-3 font-display text-xl font-semibold text-white">{item.title}</div>
                <p className="mt-3 text-sm leading-7 text-slate-200/70">{item.detail}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="grid gap-8 border-y border-white/8 py-12">
          <div className="max-w-2xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Get started</div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
              Account, plan, then open the app.
            </h2>
            <p className="mt-4 text-sm leading-7 text-slate-200/70 md:text-base">
              Sign up, choose a plan, install Camxora, and start your first song-to-video run.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            {[
              {
                label: "Create account",
                detail: "Register and sign in to unlock your workspace.",
              },
              {
                label: "Choose a plan",
                detail: "Pick the channel capacity that matches your schedule.",
              },
              {
                label: "Open Camxora",
                detail: "Install the Windows app and create your first batch.",
              },
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
          <div className="max-w-2xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Inside the app</div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
              Outcomes, not another AI demo.
            </h2>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            {[
              {
                icon: Music,
                title: "Turn ideas into songs",
                detail: "Draft lyrics, polish them, and generate music in controlled batches.",
              },
              {
                icon: ImageIcon,
                title: "Create matching artwork",
                detail: "Generate backgrounds and thumbnails that fit every track and channel.",
              },
              {
                icon: Video,
                title: "Build music videos",
                detail: "Design templates with spectrum, logo, and text — then export branded MP4s.",
              },
              {
                icon: Package,
                title: "One-click marketplace templates",
                detail:
                  "Download ready video templates and set them up in one click. Free and premium packs.",
              },
              {
                icon: Workflow,
                title: "Track every stage",
                detail: "Follow progress from music through merge, retry stalls, and stay on schedule.",
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

        <section className="grid gap-8">
          <div className="max-w-2xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Who it&apos;s for</div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
              Built for faceless creators.
            </h2>
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            {[
              {
                title: "YouTube creators",
                detail: "Publish more music videos without showing your face or hiring an editor.",
              },
              {
                title: "Multi-channel creators",
                detail: "Run multiple channel profiles from one account with consistent branding.",
              },
            ].map((item) => (
              <div
                key={item.title}
                className="rounded-[24px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6"
              >
                <div className="font-display text-2xl font-semibold text-white">{item.title}</div>
                <p className="mt-3 text-sm leading-7 text-slate-200/70">{item.detail}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="grid gap-10 border-t border-white/8 pt-8 lg:grid-cols-[minmax(0,1fr)_420px]">
          <div className="max-w-2xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Ready when you are</div>
            <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-4xl">
              Start a YouTube channel without a camera.
            </div>
            <p className="mt-4 text-sm leading-7 text-slate-200/70 md:text-base">
              Create an account, download the Windows app, and export your next music video —
              auto-upload arrives in a later release.
            </p>
          </div>

          <div className="rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] p-6 ring-1 ring-white/6 md:p-7">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Start now</div>
            <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white">
              Open Camxora.
            </div>
            <p className="mt-4 text-sm leading-7 text-slate-200/72">
              Your channels, credits, and production tools are waiting in the desktop app.
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
