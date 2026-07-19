import type { Metadata } from "next";
import { ContentPageShell } from "@/components/marketing/content-page-shell";

export const metadata: Metadata = {
  title: "Services",
  description:
    "How Camxora supports your channel production: account access, the Windows desktop studio, and publishing workflow.",
};

export default function ServicesPage() {
  return (
    <ContentPageShell
      eyebrow="Services"
      title="How Camxora supports your music channel workflow."
      description="Camxora combines account access, the Windows desktop studio, and publishing tools so you can produce and ship branded videos at channel scale."
      aside={
        <div className="space-y-5">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-400">How it fits together</div>
            <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
              Account for access. Desktop for production.
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            Billing and plans live in your portal. Day-to-day generation, preview, export, and upload
            happen in the Camxora app.
          </p>
        </div>
      }
    >
      <div className="grid gap-6 md:grid-cols-3">
        {[
          {
            title: "Account & plans",
            detail:
              "Create your Camxora account, choose a plan, and manage credits for music, images, and video work.",
          },
          {
            title: "Desktop studio",
            detail:
              "Install the Windows app to generate songs, prepare assets, design video templates, and export MP4s locally.",
          },
          {
            title: "Publish & monitor",
            detail:
              "Connect YouTube channels, set publication defaults, and track each batch from draft to upload.",
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
          <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Why creators use Camxora</div>
          <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white">
            Less tool-switching. More finished videos.
          </div>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-200/72 md:text-base">
            Instead of stitching together separate generators, editors, and uploaders, Camxora keeps
            the full music-to-YouTube pipeline in one desktop application with clear progress for
            every channel.
          </p>
        </div>
        <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Outcome</div>
          <div className="mt-3 text-sm leading-7 text-slate-200/72">
            Repeatable daily or weekly runs, consistent branding, and fewer missed steps between
            song and publish.
          </div>
        </div>
      </section>
    </ContentPageShell>
  );
}
