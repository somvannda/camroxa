"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import type { SlideMock } from "./deck";

function MockChrome(props: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(8,14,36,0.96),rgba(4,8,22,0.98))] shadow-[0_24px_60px_rgba(2,6,23,0.45)]",
        props.className,
      )}
    >
      <div className="flex items-center gap-2 border-b border-white/8 bg-white/[0.03] px-4 py-2.5">
        <span className="h-2 w-2 rounded-full bg-rose-400/80" />
        <span className="h-2 w-2 rounded-full bg-amber-300/80" />
        <span className="h-2 w-2 rounded-full bg-emerald-400/80" />
        <span className="ml-2 text-[11px] uppercase tracking-[0.18em] text-slate-400">{props.title}</span>
      </div>
      <div className="p-4">{props.children}</div>
    </div>
  );
}

function Bar(props: { label: string; value: number; tone?: "cyan" | "emerald" | "violet" }) {
  const tone =
    props.tone === "emerald"
      ? "from-emerald-400 to-cyan-300"
      : props.tone === "violet"
        ? "from-violet-400 to-fuchsia-300"
        : "from-cyan-400 to-sky-300";
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-[11px] text-slate-400">
        <span>{props.label}</span>
        <span className="text-slate-300">{props.value}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/5">
        <div
          className={cn("h-full rounded-full bg-gradient-to-r", tone)}
          style={{ width: `${Math.max(8, Math.min(100, props.value))}%` }}
        />
      </div>
    </div>
  );
}

function PipelineMock() {
  const stages = ["Niche", "Assets", "Music", "Images", "Export", "Upload"];
  return (
    <MockChrome title="Automation loop">
      <div className="grid gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {stages.map((stage, index) => (
            <React.Fragment key={stage}>
              <div className="rounded-xl border border-cyan-400/20 bg-cyan-400/10 px-3 py-2 text-xs font-medium text-cyan-100">
                {stage}
              </div>
              {index < stages.length - 1 ? (
                <span className="text-slate-600" aria-hidden>
                  →
                </span>
              ) : null}
            </React.Fragment>
          ))}
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="rounded-xl border border-white/8 bg-white/[0.03] p-3">
            <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Primary</div>
            <div className="mt-1 text-sm text-white">Night Drive Radio</div>
          </div>
          <div className="rounded-xl border border-white/8 bg-white/[0.03] p-3">
            <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Secondary</div>
            <div className="mt-1 text-sm text-white">Velvet Afterhours</div>
          </div>
        </div>
      </div>
    </MockChrome>
  );
}

function OnboardingMock() {
  const steps = ["Genre", "Names", "Logos", "Covers", "SEO"];
  return (
    <MockChrome title="Onboarding board">
      <div className="flex flex-wrap gap-2">
        {steps.map((step, index) => (
          <div
            key={step}
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs",
              index <= 2
                ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-100"
                : "border-white/10 bg-white/[0.03] text-slate-400",
            )}
          >
            {index + 1}. {step}
          </div>
        ))}
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <div className="rounded-xl border border-violet-400/20 bg-violet-500/10 p-3">
          <div className="text-[10px] uppercase tracking-[0.16em] text-violet-200/70">Primary</div>
          <div className="mt-2 h-10 rounded-lg bg-gradient-to-br from-violet-500/40 to-cyan-400/20" />
        </div>
        <div className="rounded-xl border border-sky-400/20 bg-sky-500/10 p-3">
          <div className="text-[10px] uppercase tracking-[0.16em] text-sky-200/70">Secondary</div>
          <div className="mt-2 h-10 rounded-lg bg-gradient-to-br from-sky-500/40 to-emerald-400/20" />
        </div>
      </div>
    </MockChrome>
  );
}

function SettingsMock() {
  return (
    <MockChrome title="Settings · Channel profile">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-2 rounded-xl border border-white/8 bg-white/[0.03] p-3">
          <div className="text-xs text-slate-400">Active profile</div>
          <div className="text-sm font-medium text-white">Primary · Synthwave</div>
          <div className="text-[11px] text-slate-500">Preferences synced</div>
        </div>
        <div className="space-y-2 rounded-xl border border-white/8 bg-white/[0.03] p-3">
          <Bar label="Daily song quota" value={42} />
          <Bar label="Image quota" value={28} tone="violet" />
        </div>
      </div>
    </MockChrome>
  );
}

function TemplatesMock() {
  return (
    <MockChrome title="Video templates">
      <div className="grid grid-cols-3 gap-2">
        {["Cinematic", "Waveform", "Minimal"].map((name, index) => (
          <div
            key={name}
            className={cn(
              "rounded-xl border p-2",
              index === 0 ? "border-cyan-400/30 bg-cyan-400/10" : "border-white/8 bg-white/[0.03]",
            )}
          >
            <div className="aspect-video rounded-lg bg-gradient-to-br from-slate-700/80 to-slate-900" />
            <div className="mt-2 text-[11px] text-slate-300">{name}</div>
          </div>
        ))}
      </div>
    </MockChrome>
  );
}

function MusicMock() {
  return (
    <MockChrome title="Music · Batch pipeline">
      <div className="space-y-3">
        {["Track 01 · Neon Harbor", "Track 02 · Soft Static", "Track 03 · Afterglow"].map(
          (title, index) => (
            <div
              key={title}
              className="flex items-center justify-between rounded-xl border border-white/8 bg-white/[0.03] px-3 py-2"
            >
              <span className="text-xs text-slate-200">{title}</span>
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide",
                  index === 0
                    ? "bg-emerald-400/15 text-emerald-200"
                    : index === 1
                      ? "bg-cyan-400/15 text-cyan-200"
                      : "bg-white/5 text-slate-400",
                )}
              >
                {index === 0 ? "Ready" : index === 1 ? "Running" : "Queued"}
              </span>
            </div>
          ),
        )}
      </div>
    </MockChrome>
  );
}

function ProgressMock() {
  return (
    <MockChrome title="Progress">
      <div className="space-y-3">
        <Bar label="Music" value={100} tone="emerald" />
        <Bar label="Images" value={100} tone="emerald" />
        <Bar label="Converter / merge" value={72} />
        <Bar label="Upload" value={18} tone="violet" />
      </div>
    </MockChrome>
  );
}

function ImagesMock() {
  return (
    <MockChrome title="Images">
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-xl border border-white/8 bg-white/[0.03] p-2">
          <div className="aspect-video rounded-lg bg-[radial-gradient(circle_at_30%_20%,rgba(34,211,238,0.35),transparent_55%),linear-gradient(160deg,#0f172a,#020617)]" />
          <div className="mt-2 text-[11px] text-slate-400">Background · 16:9</div>
        </div>
        <div className="rounded-xl border border-white/8 bg-white/[0.03] p-2">
          <div className="aspect-video rounded-lg bg-[radial-gradient(circle_at_70%_30%,rgba(16,185,129,0.35),transparent_50%),linear-gradient(160deg,#1e1b4b,#020617)]" />
          <div className="mt-2 text-[11px] text-slate-400">Thumbnail · Ready</div>
        </div>
      </div>
    </MockChrome>
  );
}

function UploadMock() {
  return (
    <MockChrome title="Upload">
      <div className="space-y-3">
        <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/10 px-3 py-2 text-xs text-emerald-100">
          Connected channel · Primary
        </div>
        <Bar label="Uploading final MP4" value={64} tone="emerald" />
        <div className="text-[11px] text-slate-500">Title, description, and tags applied from profile SEO.</div>
      </div>
    </MockChrome>
  );
}

function YoutubeMock() {
  return (
    <MockChrome title="YouTube Studio checklist">
      <ul className="space-y-2 text-xs text-slate-300">
        {[
          "Channel created + avatar / banner",
          "About description saved",
          "Keywords added",
          "Country set",
          "Playlists ready",
        ].map((item) => (
          <li
            key={item}
            className="flex items-center gap-2 rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            {item}
          </li>
        ))}
      </ul>
    </MockChrome>
  );
}

function GrowthMock() {
  return (
    <MockChrome title="Audience growth">
      <div className="space-y-2 text-xs text-slate-300">
        {[
          "Reply to every comment",
          "Upload every day",
          "Comment on larger niche channels",
          "Invite viewers back — no spam",
        ].map((item) => (
          <div
            key={item}
            className="flex items-center gap-2 rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            {item}
          </div>
        ))}
      </div>
    </MockChrome>
  );
}

function RoadmapMock() {
  return (
    <MockChrome title="Coming soon">
      <div className="grid gap-2 sm:grid-cols-3">
        {[
          { label: "DistroKid", hint: "WAV · releases" },
          { label: "YouTube", hint: "Auto upload" },
          { label: "Facebook Reels", hint: "Auto publish" },
        ].map((item) => (
          <div
            key={item.label}
            className="rounded-xl border border-cyan-400/20 bg-cyan-400/10 px-3 py-3 text-center"
          >
            <div className="text-xs font-medium text-cyan-100">{item.label}</div>
            <div className="mt-1 text-[10px] text-slate-400">{item.hint}</div>
          </div>
        ))}
      </div>
      <div className="mt-3 text-center text-[11px] text-slate-500">No fixed release dates — shipping when ready.</div>
    </MockChrome>
  );
}

function PublishEverywhereMock() {
  const steps = ["Music", "Artwork", "Video", "Thumbnail", "Metadata", "Publish"];
  return (
    <MockChrome title="Unified publishing">
      <div className="flex flex-wrap items-center justify-center gap-1.5">
        {steps.map((step, index) => (
          <React.Fragment key={step}>
            <div className="rounded-lg border border-emerald-400/25 bg-emerald-400/10 px-2.5 py-1.5 text-[11px] text-emerald-100">
              {step}
            </div>
            {index < steps.length - 1 ? <span className="text-slate-600">↓</span> : null}
          </React.Fragment>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap justify-center gap-2 text-[11px] text-slate-400">
        <span className="rounded-full border border-white/10 px-2.5 py-1">YouTube</span>
        <span className="rounded-full border border-white/10 px-2.5 py-1">Facebook Reels</span>
        <span className="rounded-full border border-white/10 px-2.5 py-1">DistroKid</span>
        <span className="rounded-full border border-white/10 px-2.5 py-1">More soon</span>
      </div>
    </MockChrome>
  );
}

export function SlideMockPanel(props: { mock: SlideMock }) {
  switch (props.mock) {
    case "pipeline":
      return <PipelineMock />;
    case "onboarding":
      return <OnboardingMock />;
    case "settings":
      return <SettingsMock />;
    case "templates":
      return <TemplatesMock />;
    case "music":
      return <MusicMock />;
    case "progress":
      return <ProgressMock />;
    case "images":
      return <ImagesMock />;
    case "upload":
      return <UploadMock />;
    case "youtube":
      return <YoutubeMock />;
    case "growth":
      return <GrowthMock />;
    case "roadmap":
      return <RoadmapMock />;
    case "publishEverywhere":
      return <PublishEverywhereMock />;
    default:
      return null;
  }
}
