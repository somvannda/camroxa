import type { Metadata } from "next";
import { ContentPageShell } from "@/components/marketing/content-page-shell";

export const metadata: Metadata = {
  title: "Who it's for",
  description:
    "Camxora is for faceless YouTube creators who start with dual channels — lyrics-to-video in one Windows app.",
};

export default function ServicesPage() {
  return (
    <ContentPageShell
      eyebrow="Who it's for"
      title="Built for people who want dual YouTube channels without showing their face."
      description="Camxora turns ideas into music videos in one desktop workflow — so creators can run dual channels (and scale) without juggling five tools."
      aside={
        <div className="space-y-5">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-400">The promise</div>
            <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
              No camera. No face. Dual channels from day one.
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            Account and billing stay in the portal. Day-to-day creation, export, and progress live
            in the Camxora Windows app. Auto YouTube upload is coming soon.
          </p>
        </div>
      }
    >
      <div className="grid gap-6 md:grid-cols-2">
        {[
          {
            title: "YouTube creators",
            detail:
              "Start with dual music channels — no camera, microphone, studio, or editing team required.",
          },
          {
            title: "Multi-channel operators",
            detail:
              "Grow from dual toward 10+ channel profiles on one account with shared credits and consistent branding.",
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
          <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Why Camxora</div>
          <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white">
            Less tool-switching. More finished videos.
          </div>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-200/72 md:text-base">
            Instead of stitching together lyric tools, music generators, image apps, and editors,
            Camxora keeps lyrics → music → images → video → merge in one desktop application.
          </p>
        </div>
        <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-400">What ships now</div>
          <div className="mt-3 text-sm leading-7 text-slate-200/72">
            Export YouTube-ready MP4s today. Auto YouTube upload arrives in a later release.
          </div>
        </div>
      </section>
    </ContentPageShell>
  );
}
