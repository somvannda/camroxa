import type { Metadata } from "next";
import {
  Boxes,
  Image as ImageIcon,
  Music,
  ShieldCheck,
  Video,
  Workflow,
} from "lucide-react";

import { ContentPageShell } from "@/components/marketing/content-page-shell";

export const metadata: Metadata = {
  title: "Features",
  description:
    "Explore Camxora desktop features: music batches, image generation, video templates, progress tracking, and YouTube publishing.",
};

export default function FeaturesPage() {
  return (
    <ContentPageShell
      eyebrow="Features"
      title="What you can do inside the Camxora desktop app."
      description="Every feature maps to a real workspace in Camxora — from song generation and image prep to video templates, exports, and channel uploads."
      aside={
        <div className="space-y-5">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Built for creators</div>
            <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
              A full studio, not a single AI demo.
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            Manage multiple channel profiles, run batches, and keep music-to-video production moving
            without leaving the app.
          </p>
        </div>
      }
    >
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        {[
          {
            icon: Music,
            title: "Music workspace",
            detail:
              "Plan batches by date and channel pair, generate drafts, polish lyrics, and automate Suno when you are ready.",
            bullets: ["Multi-day batch planning", "Draft, polish, and Suno automation"],
          },
          {
            icon: ImageIcon,
            title: "Image workspace",
            detail:
              "Create backgrounds and thumbnails that stay consistent with each song and profile.",
            bullets: ["Background & thumbnail jobs", "Profile-aligned visuals"],
          },
          {
            icon: Video,
            title: "Video studio",
            detail:
              "Build reusable templates with spectrum, particles, logo, and text — then preview and export MP4s.",
            bullets: ["Live GPU preview", "Template save & marketplace packs"],
          },
          {
            icon: Workflow,
            title: "Progress & workflow",
            detail:
              "Follow every run from music through upload, with stage filters and recovery actions when something stalls.",
            bullets: ["Stage-by-stage monitoring", "Retry and recovery tools"],
          },
          {
            icon: Boxes,
            title: "Channel profiles",
            detail:
              "Run multiple channels under one account, each with its own templates, YouTube connection, and output paths.",
            bullets: ["Per-channel templates", "YouTube connect & publish defaults"],
          },
          {
            icon: ShieldCheck,
            title: "Account & credits",
            detail:
              "Sign in once, use plan credits for generation, and keep settings synced between the portal and desktop.",
            bullets: ["Plan-based access", "Desktop preferences & readiness checks"],
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
    </ContentPageShell>
  );
}
