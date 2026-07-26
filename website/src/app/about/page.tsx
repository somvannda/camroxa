import type { Metadata } from "next";
import Image from "next/image";

import { ContentPageShell } from "@/components/marketing/content-page-shell";

export const metadata: Metadata = {
  title: "About",
  description:
    "Meet Kong Somvannda, founder of Camxora — a faceless desktop studio built from real dual-channel YouTube music results.",
};

export default function AboutPage() {
  return (
    <ContentPageShell
      eyebrow="About"
      title="Camxora exists to help people start dual YouTube channels without showing their face."
      description="We believe creators should be able to turn ideas into music videos across dual channels — and eventually publish them — without a camera, studio, or five disconnected AI tools."
      aside={
        <div className="space-y-5">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Mission</div>
            <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
              Dual-channel faceless creation, end to end.
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            Start with dual YouTube music channels. Expand toward a fuller social publishing platform
            over time.
          </p>
        </div>
      }
    >
      <section className="grid gap-10 border-b border-white/8 pb-14 lg:grid-cols-[minmax(280px,360px)_minmax(0,1fr)] lg:items-start">
        <div className="overflow-hidden rounded-[28px] border border-white/10 bg-white/[0.03] ring-1 ring-white/6">
          <Image
            src="/founder.jpg"
            alt="Kong Somvannda, founder of Camxora"
            width={720}
            height={900}
            className="h-full w-full object-cover object-top"
            priority
          />
        </div>

        <div className="space-y-6">
          <div>
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
              Founder &amp; creator
            </div>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
              Kong Somvannda
            </h2>
            <p className="mt-2 text-sm font-medium text-fuchsia-100/80 md:text-base">
              Founder of Camxora · Faceless YouTube creator
            </p>
          </div>

          <div className="space-y-4 text-sm leading-7 text-slate-200/78 md:text-base md:leading-8">
            <p>
              Camxora wasn&apos;t built from a pitch deck. It was built from the same grind creators
              face every week: turn ideas into music, visuals, and videos — without ever appearing on
              camera.
            </p>
            <p>
              Kong Somvannda started running faceless YouTube music channels in{" "}
              <strong className="text-white">February 2026</strong>. By{" "}
              <strong className="text-white">April 2026</strong> — about two months later — those
              channels were monetized. In the last four months alone, he has earned{" "}
              <strong className="text-white">more than $8,000 USD</strong> from faceless YouTube
              content, and the income is still growing.
            </p>
            <p>
              He isn&apos;t only building the product — he&apos;s living the workflow Camxora is
              designed to accelerate: lyrics, music, artwork, video, and publish-ready output,
              repeated until the channel compounds.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            {[
              { label: "Started", value: "Feb 2026" },
              { label: "Monetized", value: "~2 months" },
              { label: "Earned", value: "$8,000+" },
            ].map((item) => (
              <div
                key={item.label}
                className="rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-4 ring-1 ring-white/6"
              >
                <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">{item.label}</div>
                <div className="mt-2 font-display text-xl font-semibold text-white">{item.value}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-8 border-b border-white/8 pb-14">
        <div className="max-w-3xl">
          <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Proof it transfers</div>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-4xl">
            The first customer monetized in 1.5 months.
          </h2>
          <p className="mt-4 text-sm leading-7 text-slate-200/78 md:text-base md:leading-8">
            This isn&apos;t a theory. Camxora&apos;s first customer followed the same faceless music
            path and reached monetization in only{" "}
            <strong className="text-white">1.5 months</strong> — then went on to earn up to{" "}
            <strong className="text-white">$2,000 USD</strong> in the next two months. When the
            founder and the first customer both move that fast, the opportunity is real: you
            don&apos;t need a face on camera to build a YouTube income stream.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-6 ring-1 ring-white/6">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Founder results</div>
            <div className="mt-3 font-display text-3xl font-semibold text-white">$8,000+</div>
            <p className="mt-3 text-sm leading-7 text-slate-200/72">
              Faceless YouTube earnings in the last 4 months — started February 2026, monetized by
              April, still compounding.
            </p>
          </div>
          <div className="rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-6 ring-1 ring-white/6">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">First customer</div>
            <div className="mt-3 font-display text-3xl font-semibold text-white">$2,000</div>
            <p className="mt-3 text-sm leading-7 text-slate-200/72">
              Monetized in 1.5 months, then earned up to $2,000 USD across the following 2 months.
            </p>
          </div>
        </div>
      </section>

      <section className="grid gap-8 border-b border-white/8 pb-14">
        <div className="max-w-3xl">
          <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Important note</div>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white md:text-4xl">
            Manual faceless work eats your day. Camxora gives it back.
          </h2>
          <p className="mt-4 text-sm leading-7 text-slate-200/78 md:text-base md:leading-8">
            Running channels by hand means juggling lyrics, music, artwork, editing, and exports —
            with{" "}
            <strong className="text-white">at least 2 hours of high-effort work per channel, every
            day</strong>
            . Scale to a few channels and you are suddenly spending{" "}
            <strong className="text-white">10 hours a day</strong> just keeping production alive.
          </p>
          <p className="mt-4 text-sm leading-7 text-slate-200/78 md:text-base md:leading-8">
            With Camxora, that same workload collapses to roughly{" "}
            <strong className="text-white">one hour</strong>: set it up, click once, then sit back
            and watch the pipeline run — music, visuals, and video moving without you babysitting
            five separate tools.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6">
            <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Doing it manually</div>
            <div className="mt-3 font-display text-3xl font-semibold text-white">10 hrs / day</div>
            <p className="mt-3 text-sm leading-7 text-slate-200/72">
              ~2 hours of high effort per channel. Multiple channels turn into a full-time grind —
              every day.
            </p>
          </div>
          <div className="rounded-[28px] border border-fuchsia-400/20 bg-[linear-gradient(180deg,rgba(168,85,247,0.12),rgba(255,255,255,0.03))] p-6 ring-1 ring-fuchsia-400/15">
            <div className="text-[11px] uppercase tracking-[0.22em] text-fuchsia-100/70">
              With Camxora
            </div>
            <div className="mt-3 font-display text-3xl font-semibold text-white">~1 hr / day</div>
            <p className="mt-3 text-sm leading-7 text-slate-200/72">
              One click. Sit and watch the pipeline run — instead of spending your whole day
              managing production by hand.
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-6 md:grid-cols-3">
        {[
          {
            title: "Outcome over tools",
            detail:
              "We sell finished, branded music videos — not a pile of disconnected generators.",
          },
          {
            title: "Desktop where the work happens",
            detail:
              "Heavy creation, preview, export, and merge stay in the Windows app for speed and control.",
          },
          {
            title: "Honest roadmap",
            detail:
              "Export is available now. Auto YouTube upload is next. Broader social publishing comes later.",
          },
        ].map((item) => (
          <div
            key={item.title}
            className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6"
          >
            <h2 className="font-display text-2xl font-semibold text-white">{item.title}</h2>
            <p className="mt-3 text-sm leading-7 text-slate-200/72">{item.detail}</p>
          </div>
        ))}
      </div>

      <section className="grid gap-6 border-t border-white/8 pt-10 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div>
          <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Why it matters</div>
          <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white">
            A YouTube business shouldn&apos;t require a face on camera.
          </div>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-200/72 md:text-base">
            Camxora packages the workflow Kong used to build and monetize dual faceless channels — so
            more creators can move from idea to YouTube-ready video without juggling five tools.
          </p>
        </div>
        <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Focus</div>
          <div className="mt-3 text-sm leading-7 text-slate-200/72">
            Lyrics. Music. Artwork. Video. Merge. Then upload — when that release ships.
          </div>
        </div>
      </section>
    </ContentPageShell>
  );
}
