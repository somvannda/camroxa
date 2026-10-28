import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";

export const metadata: Metadata = {
  title: "Features",
};

const features = [
  {
    icon: "fa-pen-nib",
    title: "Write better lyrics & songs",
    body: "Plan batches by date and channel, draft lyrics, polish them, and generate music when you are ready.",
    points: ["Batch planning by channel", "Draft, polish, and music generation"],
  },
  {
    icon: "fa-image",
    title: "Create matching artwork",
    body: "Generate backgrounds and thumbnails that stay consistent with each song and channel profile.",
    points: ["Backgrounds & thumbnails", "Profile-aligned visuals"],
  },
  {
    icon: "fa-video",
    title: "Build music videos",
    body: "Design reusable templates with spectrum, particles, logo, and text, then preview and export MP4s.",
    points: ["Live preview", "Templates & export"],
  },
  {
    icon: "fa-store",
    title: "Marketplace templates",
    body: "Download ready video templates and set them up in your workspace with one click.",
    points: ["One-click download & setup", "Free + premium marketplace"],
  },
  {
    icon: "fa-chart-line",
    title: "Track every stage",
    body: "Follow each run from music through merge, with clear status and recovery when something stalls.",
    points: ["Stage-by-stage progress", "Retry and recovery tools"],
  },
  {
    icon: "fa-tower-broadcast",
    title: "Run multiple channels",
    body: "Manage several channel profiles under one account, each with its own templates and output paths.",
    points: ["Per-channel templates", "YouTube connect ready for upcoming upload"],
  },
];

export default function FeaturesPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Features</div>
          <h1>Everything you need to ship faceless music videos.</h1>
          <p>
            Camxora is a desktop studio for dual-channel lyrics, music, artwork,
            video templates, and export — with auto YouTube upload coming soon.
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-primary" href="/download">Download Camxora</Link>
          <Link className="btn btn-ghost" href="/pricing">View pricing</Link>
        </div>
      </div>

      <div className="feature-6">
        {features.map((feature) => (
          <article className="feature" key={feature.title}>
            <span className="feature-ico"><Icon name={feature.icon} /></span>
            <h3>{feature.title}</h3>
            <p>{feature.body}</p>
            <ul className="feature-points">
              {feature.points.map((point) => (
                <li key={point}><Icon name="fa-check" /> {point}</li>
              ))}
            </ul>
          </article>
        ))}
      </div>

      <section className="download-panel">
        <div>
          <div className="eyebrow">Coming soon</div>
          <h2>Auto YouTube upload</h2>
          <p>
            This release exports YouTube-ready videos. Connecting channels and
            uploading automatically ships in a later update.
          </p>
        </div>
        <Link className="btn btn-primary" href="/download">Get the desktop app</Link>
      </section>
    </div>
  );
}
