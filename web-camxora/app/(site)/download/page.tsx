import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";

export const metadata: Metadata = {
  title: "Download",
};

const installer =
  "https://api.camxora.com/api/v3/public/desktop-release/files/Camxora-1.4.9.exe";

export default function DownloadPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Download</div>
          <h1>Install Camxora and start your first run.</h1>
          <p>
            Create an account, choose a plan, then download the Windows app — where
            lyrics, music, artwork, and video export live.
          </p>
        </div>
        <a className="btn btn-primary" href={installer}>
          <Icon name="fa-download" /> Download for Windows
        </a>
      </div>

      <section className="artist-band">
        <div className="artist-band-copy">
          <div className="eyebrow">Desktop focus</div>
          <h2>The app is where creation happens.</h2>
          <p>
            Billing stays in the portal. Preview, export, and merge stay in Camxora.
            Auto YouTube upload is coming soon.
          </p>
          <div className="artist-band-meta">
            <span><b>v1.4.9</b> latest release</span>
            <span><b>Windows</b> 10/11</span>
            <span><b>MP4</b> export ready</span>
          </div>
        </div>
        <div className="artist-band-art">
          <img src="/hero.png" alt="Camxora desktop studio" />
        </div>
      </section>

      <div className="download-grid">
        <section className="panel download-card">
          <div className="eyebrow">Latest release</div>
          <h2>Camxora Desktop v1.4.9</h2>
          <p>Published Oct 23, 2026 · 7 downloads for v1.4.9 · 401 total</p>
          <a className="btn btn-primary" href={installer}>
            <Icon name="fa-download" /> Download for Windows
          </a>
          <Link className="btn btn-ghost" href="/changelog">View changelog</Link>
        </section>

        <section className="panel download-card">
          <div className="eyebrow">What&apos;s new</div>
          <h2>Create, buy, and profile.</h2>
          <ul className="download-list">
            <li>Create channel profiles directly in Settings.</li>
            <li>Buy credit packs instead of subscriptions.</li>
            <li>No profile-count limit.</li>
            <li>Requires live pack credits.</li>
          </ul>
          <Link className="btn btn-ghost" href="/changelog">Full release notes</Link>
        </section>
      </div>

      <section className="download-panel">
        <div>
          <h2>Recommended path</h2>
          <p>
            Create your account → choose a plan → download Camxora → sign in on
            desktop and start a batch.
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-primary" href="/signup">Create account</Link>
          <Link className="btn btn-ghost" href="/pricing">View pricing</Link>
        </div>
      </section>

      <div className="req">
        <div><b>Platform</b>Windows 10/11</div>
        <div><b>Account</b>Camxora account with credits</div>
        <div><b>Output</b>YouTube-ready MP4</div>
      </div>
    </div>
  );
}
