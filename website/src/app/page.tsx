import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  Check,
  Download,
  Layers,
  Music,
  ShieldCheck,
  Sparkles,
  Video,
  Workflow,
  X,
} from "lucide-react";

import {
  MarketingFooter,
  MarketingHeader,
  getUserPortalBaseUrl,
} from "@/components/marketing/site-chrome";
import { formatPlanPrice } from "@/lib/plan-pricing";
import { resolvePlatformApiBaseUrl } from "@/lib/platform-api-base";

export const metadata: Metadata = {
  title: "Camxora — Dual faceless YouTube channels in one studio",
  description:
    "Camxora replaces ChatGPT + Suno + CapCut/Vizzy hopping with one Windows studio: dual channels, marketplace templates with one-click setup, and a monetization-path refund.",
};

type PublicPlan = {
  id: string;
  name: string;
  effective_price_cents: number;
  profile_allowance: number;
};

async function getPublicPlans(): Promise<PublicPlan[]> {
  const base = resolvePlatformApiBaseUrl();
  try {
    const response = await fetch(`${base}/plans/public`, { next: { revalidate: 60 } });
    if (!response.ok) return [];
    return (await response.json()) as PublicPlan[];
  } catch {
    return [];
  }
}

function lowestPaidPlan(plans: PublicPlan[]): PublicPlan | null {
  const paid = plans
    .filter((plan) => plan.effective_price_cents > 0)
    .sort((a, b) => a.effective_price_cents - b.effective_price_cents);
  return paid[0] ?? null;
}

function CtaRow({
  userPortalBaseUrl,
  priceLabel,
  compact = false,
}: {
  userPortalBaseUrl: string;
  priceLabel: string | null;
  /** Two equal buttons in one row + centered price line — for narrow cards. */
  compact?: boolean;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div
        className={
          compact
            ? "flex flex-row items-stretch gap-3"
            : "flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center"
        }
      >
        <a
          className={`inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-4 text-sm font-medium text-white shadow-[0_22px_54px_rgba(118,77,255,0.34)] transition hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400 ${
            compact ? "min-w-0 flex-1" : "shrink-0 px-5"
          }`}
          href={`${userPortalBaseUrl}/register`}
        >
          Create account
          <ArrowRight className="h-4 w-4 shrink-0" />
        </a>
        <Link
          className={`inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-4 text-sm font-medium text-white transition hover:bg-white/[0.06] ${
            compact ? "min-w-0 flex-1" : "shrink-0 px-5"
          }`}
          href="/download"
        >
          <Download className="h-4 w-4 shrink-0" />
          {compact ? "Download" : "Download for Windows"}
        </Link>
        {!compact ? (
          <Link
            className="inline-flex h-12 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] px-5 text-sm font-medium text-white transition hover:bg-white/[0.06]"
            href="/pricing"
          >
            View plans
          </Link>
        ) : null}
      </div>
      <p
        className={`text-sm leading-6 text-slate-300/70 ${compact ? "text-center" : ""}`}
      >
        {priceLabel ? (
          <>
            Plans from <span className="font-medium text-white">{priceLabel}/mo</span>
            <span className="mx-2 text-slate-500">·</span>
          </>
        ) : null}
        <Link className="text-fuchsia-100/90 underline-offset-2 hover:underline" href="/pricing">
          {compact ? "View plans" : "See pricing & guarantee"}
        </Link>
      </p>
    </div>
  );
}

export default async function Home() {
  const userPortalBaseUrl = getUserPortalBaseUrl();
  const plans = await getPublicPlans();
  const entry = lowestPaidPlan(plans);
  const priceLabel = entry ? formatPlanPrice(entry.effective_price_cents) : null;
  const dualPlan =
    plans.find((plan) => plan.profile_allowance >= 2 && plan.effective_price_cents > 0) ?? entry;

  const oldStack = [
    { tool: "ChatGPT (or similar)", job: "Write lyrics & titles" },
    { tool: "Suno / music AI", job: "Generate tracks" },
    { tool: "Image AI", job: "Backgrounds & thumbnails" },
    { tool: "CapCut / Vizzy / editor", job: "Spectrum video + exports" },
    { tool: "Manual merge & upload prep", job: "Combine clips, rename, schedule" },
  ];

  const camxoraWins = [
    {
      icon: Workflow,
      title: "One pipeline, not six tabs",
      detail:
        "Lyrics → music → artwork → spectrum video → merge stays inside Camxora. Start the run; the studio does the handoffs.",
    },
    {
      icon: Layers,
      title: "Dual channels by default",
      detail:
        "Plans are built for parallel channels — more shots at monetization and viral hits than betting on a single upload calendar.",
    },
    {
      icon: Video,
      title: "Marketplace templates, one-click setup",
      detail:
        "Download a ready video template and install it into your workspace in one click. Free packs and premium packs — pick what fits your brand.",
    },
    {
      icon: ShieldCheck,
      title: "AI routing built for production",
      detail:
        "Multiple providers and models behind a routing table with rate limits — so generation keeps moving instead of dying on one vendor outage.",
    },
    {
      icon: Music,
      title: "Scale to 10+ channels",
      detail:
        "Add channel profiles and reuse templates/workflows. The hard part stays in the app — not in your browser bookmarks.",
    },
    {
      icon: Sparkles,
      title: "Monetization-path refund",
      detail:
        "Use Camxora as instructed. If you still don't reach YouTube monetization, we refund the plan fee in full (conditions apply).",
    },
  ];

  const faqs = [
    {
      q: "Is Camxora cheaper than buying Suno + ChatGPT + CapCut separately?",
      a: "Not always on raw API sticker price — and that’s intentional. You’re paying for the production system: orchestration, dual/multi-channel profiles, marketplace templates with one-click setup, routing/uptime, and desktop export — not a single model at cost.",
    },
    {
      q: "Can I cancel anytime?",
      a: "We don’t market a casual cancel-anytime promise. We stand behind a monetization guarantee: follow Camxora’s full workflow and YouTube policies; if your dual channels still don’t reach monetization, request a full plan refund via support@camxora.com.",
    },
    {
      q: "What’s included in marketplace templates?",
      a: "Ready video templates you can download and set up in one click inside Camxora. The marketplace includes free and premium packs — premium isn’t implied free.",
    },
    {
      q: "How is this different from ChatGPT or Suno alone?",
      a: "Those tools each do one step. Camxora connects lyrics, music, images, spectrum video, merge, and multi-channel ops in one Windows studio so you’re not copy-pasting between apps all day.",
    },
    {
      q: "Do I need to be a video editor?",
      a: "No. Install a marketplace template with one click, run the pipeline, and export. You’re steering channels — not rebuilding spectrum timelines from scratch.",
    },
    {
      q: "How many channels can I run?",
      a: "Start with dual-channel capacity on core plans, then grow with profile add-ons toward 10+ channels per account as you scale.",
    },
  ];

  const workflowSteps = [
    { step: "01", title: "Idea", detail: "Channel brief & batch" },
    { step: "02", title: "Lyrics", detail: "Draft & polish" },
    { step: "03", title: "Music", detail: "Generate tracks" },
    { step: "04", title: "Art", detail: "Backgrounds & thumbs" },
    { step: "05", title: "Video", detail: "Template, spectrum, merge" },
    {
      step: "06",
      title: "YouTube-ready",
      detail: "Export finished videos today.",
      soon: "Auto-upload soon",
    },
  ] as const;

  return (
    <div className="relative flex flex-1 flex-col overflow-hidden">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-camxora-hero opacity-35" />
        <div className="absolute inset-0 bg-[radial-gradient(1100px_circle_at_14%_0%,rgba(168,85,247,0.14),transparent_34%),radial-gradient(1000px_circle_at_88%_14%,rgba(139,92,246,0.18),transparent_30%),radial-gradient(720px_circle_at_78%_82%,rgba(217,70,239,0.08),transparent_22%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(6,10,18,0.74),rgba(2,4,10,0.96))]" />
      </div>

      <MarketingHeader userPortalBaseUrl={userPortalBaseUrl} />

      <main className="relative mx-auto flex w-full max-w-7xl flex-1 flex-col gap-20 px-6 py-14 md:px-10 md:py-20">
        {/* Hero + 100% money-back guarantee */}
        <section className="grid gap-10 border-b border-white/8 pb-16 lg:grid-cols-[minmax(0,1.15fr)_minmax(280px,0.85fr)] lg:items-end">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs uppercase tracking-[0.18em] text-slate-100/80">
              <Sparkles className="h-3.5 w-3.5 text-fuchsia-200" />
              Stop the ChatGPT + Suno + CapCut grind
            </div>
            <h1 className="mt-6 font-display text-5xl font-semibold leading-[0.92] tracking-[-0.07em] text-white md:text-7xl">
              Faceless YouTube music. One studio. Dual channels. One click.
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-8 text-slate-200/72 md:text-lg">
              Camxora replaces the manual stack — lyrics, music, artwork, spectrum video, merge —
              with a Windows desktop pipeline. Marketplace templates install in one click. Scale
              from dual channels toward 10+.
            </p>
            <div className="mt-8">
              <CtaRow userPortalBaseUrl={userPortalBaseUrl} priceLabel={priceLabel} />
            </div>
            <div className="mt-6 rounded-[22px] border border-emerald-400/25 bg-[linear-gradient(180deg,rgba(16,185,129,0.14),rgba(255,255,255,0.03))] p-5 ring-1 ring-emerald-400/15">
              <div className="flex items-start gap-3">
                <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-400/15 text-emerald-200 ring-1 ring-emerald-400/25">
                  <ShieldCheck className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-[11px] uppercase tracking-[0.22em] text-emerald-100/70">
                    Monetization guarantee
                  </div>
                  <div className="mt-1 font-display text-xl font-semibold tracking-[-0.03em] text-white md:text-2xl">
                    Get monetized — or we refund 100%.
                  </div>
                  <p className="mt-2 text-sm leading-7 text-slate-200/78">
                    Follow Camxora&apos;s full workflow and YouTube policies for dual faceless music
                    channels. If you still don&apos;t reach YouTube monetization, we refund your
                    plan payment in full. Contact{" "}
                    <a
                      className="text-emerald-100 underline-offset-2 hover:underline"
                      href="mailto:support@camxora.com"
                    >
                      support@camxora.com
                    </a>
                    . We refund the plan fee — not lost AdSense earnings.{" "}
                    <Link
                      className="text-emerald-100 underline-offset-2 hover:underline"
                      href="/pricing"
                    >
                      Details
                    </Link>
                    ,{" "}
                    <Link
                      className="text-emerald-100 underline-offset-2 hover:underline"
                      href="/terms"
                    >
                      Terms
                    </Link>
                    , and{" "}
                    <Link
                      className="text-emerald-100 underline-offset-2 hover:underline"
                      href="/support"
                    >
                      Help Center
                    </Link>
                    .
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5 ring-1 ring-white/6">
            <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">What you buy</div>
            <div className="mt-2 font-display text-2xl font-semibold text-white">
              The factory — not a single AI tab
            </div>
            <ul className="mt-5 space-y-3 text-sm leading-6 text-slate-200/75">
              {[
                "End-to-end faceless music pipeline",
                dualPlan
                  ? `Dual-channel capacity (${dualPlan.profile_allowance}+ profiles on paid plans)`
                  : "Dual-channel capacity on paid plans",
                "Free + premium marketplace templates (one-click setup)",
                "Multi-provider AI routing for continuous production",
                "Path to 10+ channels with less manual work",
                "100% plan refund if dual channels don’t monetize*",
              ].map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            {priceLabel ? (
              <p className="mt-5 border-t border-white/8 pt-4 text-sm text-slate-200/70">
                Plans from{" "}
                <span className="font-medium text-white">{priceLabel}/mo</span>
                {entry ? ` · ${entry.name}` : null}
              </p>
            ) : null}
            <p className="mt-3 text-xs leading-5 text-slate-400">
              *Conditions apply — see pricing, terms, and Help Center.
            </p>
          </div>
        </section>

        {/* Old way vs Camxora */}
        <section id="why-switch" className="scroll-mt-28">
          <div className="max-w-3xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Why switch</div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
              Five tools and a long night — or one pipeline.
            </h2>
            <p className="mt-4 text-sm leading-7 text-slate-200/70 md:text-base">
              Manual faceless production burns hours every day across separate AI bills and editors.
              Camxora is built so you start the run once and let the studio carry the handoffs.
            </p>
          </div>

          <div className="mt-8 grid gap-4 lg:grid-cols-2">
            <div className="rounded-[28px] border border-white/10 bg-black/25 p-6">
              <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">The old way</div>
              <div className="mt-3 font-display text-2xl font-semibold text-white">
                Separate tools · separate costs · slow
              </div>
              <ul className="mt-6 space-y-4">
                {oldStack.map((row) => (
                  <li key={row.tool} className="flex items-start gap-3 text-sm leading-6 text-slate-200/72">
                    <X className="mt-0.5 h-4 w-4 shrink-0 text-rose-300/80" />
                    <span>
                      <span className="font-medium text-white">{row.tool}</span>
                      <span className="text-slate-400"> — {row.job}</span>
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-6 text-sm leading-7 text-slate-200/65">
                Plus: one channel at a time, blank-canvas editing, and no shared production system.
              </p>
            </div>

            <div className="rounded-[28px] border border-fuchsia-400/25 bg-[linear-gradient(180deg,rgba(168,85,247,0.16),rgba(0,0,0,0.22))] p-6 ring-1 ring-fuchsia-400/15">
              <div className="text-[11px] uppercase tracking-[0.22em] text-fuchsia-100/70">
                Camxora
              </div>
              <div className="mt-3 font-display text-2xl font-semibold text-white">
                One click · sit back · ship channels
              </div>
              <ul className="mt-6 space-y-4">
                {[
                  "Lyrics, music, images, video, merge in one desktop app",
                  "Dual channels for more monetization chances",
                  "Marketplace templates: one-click download & setup",
                  "Routing across AI providers so work keeps moving",
                  "Grow toward 10+ channels without rebuilding the stack",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-3 text-sm leading-6 text-slate-100/85">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-8">
                <CtaRow userPortalBaseUrl={userPortalBaseUrl} priceLabel={priceLabel} compact />
              </div>
            </div>
          </div>
        </section>

        {/* Why creators switch — time math from original home */}
        <section
          id="why-creators-switch"
          className="scroll-mt-28 rounded-[32px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] px-6 py-8 ring-1 ring-white/6 md:px-8"
        >
          <div className="max-w-3xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
              Why creators switch
            </div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-4xl">
              From 10 hours a day to one hour — with one click.
            </h2>
            <p className="mt-4 text-sm leading-7 text-slate-200/70 md:text-base">
              Managing faceless channels by hand takes{" "}
              <strong className="text-white">
                at least 2 hours of high-effort work per channel, every day
              </strong>
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

        {/* Pipeline / workflow — open step rail, no card frames */}
        <section id="pipeline" className="scroll-mt-28">
          <div className="max-w-3xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">The workflow</div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
              Complicated steps. Simple start.
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-200/70 md:text-base">
              You&apos;re not exporting from one site and re-uploading to the next. Camxora keeps
              the handoffs inside the studio after you start the run.
            </p>
          </div>

          {/* Desktop: single rail */}
          <div className="relative mt-12 hidden lg:block">
            <div
              aria-hidden
              className="absolute left-[1.125rem] right-[1.125rem] top-4 h-px bg-gradient-to-r from-white/5 via-white/20 to-white/5"
            />
            <ol className="relative grid list-none grid-cols-6 gap-8">
              {workflowSteps.map((item) => (
                <li key={item.step} className="relative min-w-0">
                  <div className="relative z-10 mb-5 flex h-8 w-8 items-center justify-center rounded-full bg-[#060a12] text-[11px] font-medium tracking-[0.08em] text-fuchsia-100/90 ring-1 ring-white/15">
                    {item.step}
                  </div>
                  <div className="font-display text-xl font-semibold tracking-[-0.03em] text-white">
                    {item.title}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-400">{item.detail}</p>
                  {"soon" in item && item.soon ? (
                    <span className="mt-3 inline-flex text-[10px] uppercase tracking-[0.16em] text-amber-100/80">
                      {item.soon}
                    </span>
                  ) : null}
                </li>
              ))}
            </ol>
          </div>

          {/* Mobile / tablet: vertical timeline */}
          <ol className="relative mt-10 list-none space-y-0 border-l border-white/12 pl-6 lg:hidden">
            {workflowSteps.map((item) => (
              <li key={item.step} className="relative pb-8 last:pb-0">
                <span
                  aria-hidden
                  className="absolute -left-[1.9rem] top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-[#060a12] text-[9px] font-medium text-fuchsia-100/90 ring-1 ring-white/15"
                >
                  {item.step.replace(/^0/, "")}
                </span>
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span className="font-display text-xl font-semibold text-white">{item.title}</span>
                  {"soon" in item && item.soon ? (
                    <span className="text-[10px] uppercase tracking-[0.16em] text-amber-100/80">
                      {item.soon}
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-sm leading-6 text-slate-400">{item.detail}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* Wins grid */}
        <section id="capabilities" className="scroll-mt-28">
          <div className="max-w-3xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Capabilities</div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
              Built for channel operators — not demo chats.
            </h2>
          </div>
          <div className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {camxoraWins.map(({ icon: Icon, title, detail }) => (
              <div
                key={title}
                className="rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-6 ring-1 ring-white/6"
              >
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[linear-gradient(180deg,rgba(168,85,247,0.18),rgba(139,92,246,0.14),rgba(244,114,182,0.1))] text-white ring-1 ring-white/10">
                  <Icon className="h-4 w-4" />
                </div>
                <h3 className="mt-5 font-display text-2xl font-semibold text-white">{title}</h3>
                <p className="mt-3 text-sm leading-7 text-slate-200/72">{detail}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Marketplace + pricing honesty — open two-column, no empty full-width frames */}
        <section
          id="marketplace"
          className="scroll-mt-28 grid gap-12 border-y border-white/8 py-12 lg:grid-cols-2 lg:gap-16"
        >
          <div>
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
              Marketplace
            </div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-4xl">
              Ready video templates — download & set up in one click.
            </h2>
            <p className="mt-4 text-sm leading-7 text-slate-200/70 md:text-base">
              Skip blank-canvas editing. Install a template into your Camxora workspace in one
              click, then run music through it. Browse{" "}
              <strong className="text-white">free and premium</strong> packs — premium packs are
              paid; we don&apos;t pretend everything is free.
            </p>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
              Pricing honesty
            </div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-4xl">
              We&apos;re not the cheapest raw AI bill — we&apos;re the system.
            </h2>
            <p className="mt-4 text-sm leading-7 text-slate-200/70 md:text-base">
              Buying model access piece by piece can look cheaper on paper. It still leaves you
              doing the glue work: tabs, exports, templates, and channel ops. Camxora charges for
              the factory that ships faceless music videos across dual (and later many) channels.
            </p>
          </div>
        </section>

        {/* FAQ */}
        <section id="faq" className="scroll-mt-28">
          <div className="max-w-3xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">FAQ</div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
              Questions? Answered honestly.
            </h2>
          </div>
          <div className="mt-8 space-y-4">
            {faqs.map((item) => (
              <details
                key={item.q}
                className="group rounded-[24px] border border-white/10 bg-white/[0.03] p-5 ring-1 ring-white/6 open:bg-white/[0.04]"
              >
                <summary className="cursor-pointer list-none font-display text-lg font-semibold text-white marker:content-none [&::-webkit-details-marker]:hidden">
                  <span className="flex items-start justify-between gap-4">
                    {item.q}
                    <span className="mt-1 text-slate-400 transition group-open:rotate-45">+</span>
                  </span>
                </summary>
                <p className="mt-4 text-sm leading-7 text-slate-200/72">{item.a}</p>
              </details>
            ))}
          </div>
        </section>

        {/* Final CTA — copy + actions side by side */}
        <section className="grid gap-10 border-t border-white/8 pt-12 lg:grid-cols-[minmax(0,1.15fr)_minmax(280px,0.85fr)] lg:items-end">
          <div>
            <h2 className="font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
              Cheap APIs still leave you doing the work.
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-200/75 md:text-base">
              Camxora is the work system: dual channels, one-click templates, and a pipeline that
              replaces the six-tab grind — with a 100% plan refund if dual channels don&apos;t
              monetize under our playbook.
            </p>
          </div>
          <div>
            <CtaRow userPortalBaseUrl={userPortalBaseUrl} priceLabel={priceLabel} compact />
            <p className="mt-4 text-sm leading-7 text-slate-200/65">
              <Link className="text-fuchsia-100/90 underline-offset-2 hover:underline" href="/pricing">
                See guarantee details
              </Link>
            </p>
          </div>
        </section>
      </main>

      <MarketingFooter userPortalBaseUrl={userPortalBaseUrl} />
    </div>
  );
}
