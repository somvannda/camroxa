import type { Metadata } from "next";
import {
  Boxes,
  Image as ImageIcon,
  Music,
  ShieldCheck,
  Sparkles,
  Video,
  Workflow,
} from "lucide-react";

import { ContentPageShell } from "@/components/marketing/content-page-shell";

export const metadata: Metadata = {
  title: "Features",
  description:
    "Explore CAMXORA features across music generation, image creation, video workflow, production control, and export-ready desktop workflows.",
};

export default function FeaturesPage() {
  return (
    <ContentPageShell
      eyebrow="Features"
      title="Core surfaces of the CAMXORA desktop studio."
      description="Each feature maps to a real part of the workflow, so the website explains the same product structure users see when they move into production."
      aside={
        <div className="space-y-5">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Product focus</div>
            <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
              Desktop workflow, not generic AI marketing.
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            CAMXORA is strongest when the public story matches the real studio surfaces.
          </p>
        </div>
      }
    >
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        {[
          {
            icon: Music,
            title: "Music generation",
            detail:
              "Generate and refine tracks with repeatable control.",
            bullets: ["Prompt-led output", "Iteration-ready workflow"],
          },
          {
            icon: ImageIcon,
            title: "Image workflow",
            detail:
              "Create channel artwork and supporting visual assets.",
            bullets: ["Artwork support", "Profile alignment"],
          },
          {
            icon: Video,
            title: "Video output",
            detail:
              "Handle preview, render, and export from one flow.",
            bullets: ["Preview and render", "Export-ready delivery"],
          },
          {
            icon: Workflow,
            title: "Workflow control",
            detail:
              "Keep runs, statuses, and longer sessions organized.",
            bullets: ["Progress visibility", "Session structure"],
          },
          {
            icon: Boxes,
            title: "Channel-scale system",
            detail:
              "Work at channel level instead of isolated one-off tasks.",
            bullets: ["Multi-profile setup", "Organized outputs"],
          },
          {
            icon: ShieldCheck,
            title: "Product layer",
            detail:
              "Website, pricing, account, and desktop feel like one system.",
            bullets: ["Live pricing alignment", "Cleaner entry flow"],
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
