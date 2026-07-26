import type { Metadata } from "next";
import {
  Boxes,
  Image as ImageIcon,
  Music,
  Package,
  ShieldCheck,
  Video,
  Workflow,
} from "lucide-react";

import { ContentPageShell } from "@/components/marketing/content-page-shell";

export const metadata: Metadata = {
  title: "Features",
  description:
    "Camxora helps you write lyrics, create music, generate artwork, build videos, and export YouTube-ready MP4s — without showing your face.",
};

export default function FeaturesPage() {
  return (
    <ContentPageShell
      eyebrow="Features"
      title="Everything you need to ship faceless music videos across dual channels."
      description="Camxora is a Windows desktop studio for dual-channel lyrics, music, artwork, video templates, and export — with auto YouTube upload coming soon."
      aside={
        <div className="space-y-5">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Built for creators</div>
            <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
              Dual channels first. Scale next.
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            Start with dual channel profiles, finish more videos each week, and keep branding
            consistent — without a camera or a stack of separate AI apps.
          </p>
        </div>
      }
    >
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        {[
          {
            icon: Music,
            title: "Write better lyrics & songs",
            detail:
              "Plan batches by date and channel, draft lyrics, polish them, and generate music when you are ready.",
            bullets: ["Batch planning by channel", "Draft, polish, and music generation"],
          },
          {
            icon: ImageIcon,
            title: "Create matching artwork",
            detail:
              "Generate backgrounds and thumbnails that stay consistent with each song and channel profile.",
            bullets: ["Backgrounds & thumbnails", "Profile-aligned visuals"],
          },
          {
            icon: Video,
            title: "Build music videos",
            detail:
              "Design reusable templates with spectrum, particles, logo, and text — then preview and export MP4s.",
            bullets: ["Live preview", "Templates & export"],
          },
          {
            icon: Package,
            title: "Marketplace templates",
            detail:
              "Download ready video templates and set them up in your workspace with one click. Free packs and premium packs available.",
            bullets: ["One-click download & setup", "Free + premium marketplace"],
          },
          {
            icon: Workflow,
            title: "Track every stage",
            detail:
              "Follow each run from music through merge, with clear status and recovery when something stalls.",
            bullets: ["Stage-by-stage progress", "Retry and recovery tools"],
          },
          {
            icon: Boxes,
            title: "Run multiple channels",
            detail:
              "Manage several channel profiles under one account, each with its own templates and output paths.",
            bullets: ["Per-channel templates", "YouTube connect ready for upcoming upload"],
          },
          {
            icon: ShieldCheck,
            title: "Account & credits",
            detail:
              "Sign in once, use plan credits for generation, and keep settings synced between portal and desktop.",
            bullets: ["Plan-based access", "Desktop preferences synced"],
          },
        ].map(({ icon: Icon, title, detail, bullets }) => (
          <div
            key={title}
            className="rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-6 ring-1 ring-white/6"
          >
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[linear-gradient(180deg,rgba(168,85,247,0.18),rgba(139,92,246,0.14),rgba(244,114,182,0.1))] text-white ring-1 ring-white/10">
              <Icon className="h-4 w-4" />
            </div>
            <h2 className="mt-5 font-display text-2xl font-semibold text-white">{title}</h2>
            <p className="mt-3 text-sm leading-7 text-slate-200/72">{detail}</p>
            <ul className="mt-5 space-y-3">
              {bullets.map((bullet) => (
                <li key={bullet} className="flex items-start gap-3 text-sm leading-6 text-slate-200/78">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-gradient-to-r from-violet-300 via-purple-300 to-fuchsia-300" />
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <section className="mt-4 rounded-[28px] border border-amber-400/20 bg-amber-500/10 p-6 ring-1 ring-amber-400/10">
        <div className="text-[11px] uppercase tracking-[0.22em] text-amber-100/80">Coming soon</div>
        <div className="mt-3 font-display text-2xl font-semibold text-white">
          Auto YouTube upload
        </div>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-200/80">
          This release exports YouTube-ready videos. Connecting channels and uploading automatically
          ships in a later update — so you can invest in the pipeline now without overpromising
          publish automation.
        </p>
      </section>
    </ContentPageShell>
  );
}
