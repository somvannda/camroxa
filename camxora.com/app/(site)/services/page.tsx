import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";

export const metadata: Metadata = {
  title: "Who it's for",
};

export default function ServicesPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Who it&apos;s for</div>
          <h1>Built for creators who want channels without showing their face.</h1>
          <p>
            Camxora turns ideas into music videos in one desktop workflow — so
            creators can run channels and scale without juggling five tools.
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-primary" href="/download">Download Camxora</Link>
          <Link className="btn btn-ghost" href="/features">See features</Link>
        </div>
      </div>

      <section className="artist-band">
        <div className="artist-band-copy">
          <div className="eyebrow">The promise</div>
          <h2>No camera. No face. Channels from day one.</h2>
          <p>
            Account and billing stay in the portal. Day-to-day creation, export, and
            progress live in the Camxora Windows app. Auto YouTube upload is coming
            soon.
          </p>
          <div className="artist-band-meta">
            <span><b>Dual</b> channels first</span>
            <span><b>One</b> shared credit balance</span>
            <span><b>MP4</b> export ready</span>
          </div>
        </div>
        <div className="artist-band-art">
          <img src="/hero.png" alt="Camxora creator" />
        </div>
      </section>

      <div className="sec-head">
        <h2>Made for two kinds of creators</h2>
      </div>
      <div className="feature-4">
        <article className="feature">
          <span className="feature-ico"><Icon name="fa-video" /></span>
          <h3>YouTube creators</h3>
          <p>
            Start with dual music channels — no camera, microphone, studio, or editing
            team required.
          </p>
        </article>
        <article className="feature">
          <span className="feature-ico"><Icon name="fa-layer-group" /></span>
          <h3>Multi-channel operators</h3>
          <p>
            Grow from dual toward 10+ channel profiles on one account with shared
            credits and consistent branding.
          </p>
        </article>
      </div>

      <section className="panel about-story">
        <div>
          <div className="eyebrow">Why Camxora</div>
          <h2>Less tool-switching. More finished videos.</h2>
          <p>
            Instead of stitching together lyric tools, music generators, image apps,
            and editors, Camxora keeps lyrics → music → images → video → merge in one
            desktop application.
          </p>
        </div>
        <div className="about-stats">
          <div><b>1</b><span>Desktop workspace</span></div>
          <div><b>1</b><span>Shared credit balance</span></div>
          <div><b>0</b><span>Cameras required</span></div>
        </div>
      </section>

      <section className="download-panel">
        <div>
          <h2>What ships now</h2>
          <p>
            Export YouTube-ready MP4s today. Auto YouTube upload arrives in a later
            release.
          </p>
        </div>
        <Link className="btn btn-primary" href="/download">Download for Windows</Link>
      </section>
    </div>
  );
}
