import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";

export const metadata: Metadata = {
  title: "Artist Program",
};

const benefits = [
  {
    icon: "fa-chart-line",
    title: "Creator analytics",
    body: "See plays, saves, and audience growth for every track you publish.",
  },
  {
    icon: "fa-star",
    title: "Editorial features",
    body: "Get considered for home page shelves, charts, and community playlists.",
  },
  {
    icon: "fa-coins",
    title: "Credit rewards",
    body: "Earn bonus credits for releases that bring new listeners to Camxora.",
  },
  {
    icon: "fa-users",
    title: "Creator community",
    body: "Join challenges, feedback threads, and collaborative projects.",
  },
];

const steps = [
  { number: "01", title: "Publish a track", body: "Share at least one original track publicly on Camxora." },
  { number: "02", title: "Apply", body: "Tell us about your sound, your audience, and what you want to build." },
  { number: "03", title: "Get verified", body: "We review your profile and add the artist badge to your account." },
  { number: "04", title: "Release with support", body: "Get editorial consideration, challenges, and creator tools." },
];

export default function ArtistProgramPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Creators</div>
          <h1>Artist Program.</h1>
          <p>
            For creators who are building an audience on Camxora. Get verified,
            featured, and supported as you release.
          </p>
        </div>
        <div className="page-actions">
          <a className="btn btn-primary" href="mailto:support@camxora.com?subject=Camxora%20Artist%20Program">
            <Icon name="fa-star" /> Apply now
          </a>
          <Link className="btn btn-ghost" href="/community">Meet the community</Link>
        </div>
      </div>

      <section className="artist-band">
        <div className="artist-band-copy">
          <div className="eyebrow">Built for release</div>
          <h2>More than a profile.</h2>
          <p>
            The Artist Program connects your music to listeners, editorial shelves,
            and the people building the next wave of Cambodian AI music.
          </p>
          <div className="artist-band-meta">
            <span><b>Free</b> to join</span>
            <span><b>1</b> public track required</span>
            <span><b>Manual</b> review</span>
          </div>
        </div>
        <div className="artist-band-art">
          <img src="/hero.png" alt="Camxora artist" />
        </div>
      </section>

      <div className="sec-head">
        <h2>What you get</h2>
      </div>
      <div className="feature-4">
        {benefits.map((benefit) => (
          <article className="feature" key={benefit.title}>
            <span className="feature-ico"><Icon name={benefit.icon} /></span>
            <h3>{benefit.title}</h3>
            <p>{benefit.body}</p>
          </article>
        ))}
      </div>

      <div className="sec-head">
        <h2>How it works</h2>
      </div>
      <div className="artist-steps">
        {steps.map((step) => (
          <article key={step.number}>
            <span>{step.number}</span>
            <h3>{step.title}</h3>
            <p>{step.body}</p>
          </article>
        ))}
      </div>

      <section className="download-panel">
        <div>
          <h2>Ready to apply?</h2>
          <p>
            Publish your first track, then email us your profile link and a short
            introduction. We review applications weekly.
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-primary" href="/create">Publish a track</Link>
          <a className="btn btn-ghost" href="mailto:support@camxora.com?subject=Camxora%20Artist%20Program">
            Apply by email
          </a>
        </div>
      </section>
    </div>
  );
}
