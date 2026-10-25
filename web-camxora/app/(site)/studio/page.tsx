import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";

export const metadata: Metadata = {
  title: "Camxora Studio",
};

const features = [
  {
    icon: "fa-file-lines",
    title: "Text to Song",
    body: "Describe a mood, a scene, or a story. Studio turns it into a finished track with vocals.",
  },
  {
    icon: "fa-comment-dots",
    title: "Lyrics to Song",
    body: "Bring your own lyrics and let Studio build the melody, arrangement, and vocal performance.",
  },
  {
    icon: "fa-wand-magic-sparkles",
    title: "Style Remix",
    body: "Reimagine a track in a new genre without losing the hook that made it yours.",
  },
  {
    icon: "fa-microphone",
    title: "Vocal Generate",
    body: "Shape the voice, language, and delivery for every track from one workspace.",
  },
];

export default function StudioPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Product</div>
          <h1>Camxora Studio.</h1>
          <p>
            A desktop workspace for creators who want more control over every
            generation, channel, and export.
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-primary" href="/studio/editor">
            <Icon name="fa-table-columns" /> Open Studio editor
          </Link>
          <a className="btn btn-ghost" href="mailto:support@camxora.com?subject=Camxora%20Studio%20access">
            Get desktop access
          </a>
        </div>
      </div>

      <section className="studio-mock">
        <div className="mock-bar">
          <i /><i /><i />
          <span>Camxora Studio · Untitled project</span>
        </div>
        <div className="mock-body">
          <aside className="mock-side">
            <div className="side-label">Channels</div>
            <div className="mock-channel on"><span>01</span> Lead vocal <b>V6</b></div>
            <div className="mock-channel"><span>02</span> Harmony <b>V6</b></div>
            <div className="mock-channel"><span>03</span> Bass <b>V5</b></div>
            <div className="mock-channel"><span>04</span> Drums <b>V5</b></div>
            <div className="side-label" style={{ marginTop: 16 }}>Session</div>
            <div className="mock-channel"><span>↺</span> 24-bit / 48 kHz</div>
            <div className="mock-channel"><span>◎</span> Auto-save on</div>
          </aside>
          <div className="mock-main">
            <div className="mock-preview">
              <img src="/hero.png" alt="Camxora Studio session preview" />
              <span className="badge">Preview · Bassac Moon</span>
            </div>
            <div className="mock-timeline" aria-hidden="true">
              {Array.from({ length: 44 }).map((_, index) => <i key={index} />)}
            </div>
            <div className="mock-footer">
              <span>Bassac Moon · Khmer pop · 3:24</span>
              <span>Rendered locally · 12 stems</span>
              <Link className="btn btn-primary" href="/create">Open in web studio</Link>
            </div>
          </div>
        </div>
      </section>

      <div className="sec-head">
        <h2>Everything in one session</h2>
        <Link href="/create">Try it in the browser</Link>
      </div>
      <div className="feature-4">
        {features.map((feature) => (
          <article className="feature" key={feature.title}>
            <span className="feature-ico"><Icon name={feature.icon} /></span>
            <h3>{feature.title}</h3>
            <p>{feature.body}</p>
          </article>
        ))}
      </div>

      <section className="download-panel">
        <div>
          <h2>Take the studio with you.</h2>
          <p>
            Desktop access is rolling out to creators. Join the list and we’ll send
            the build for your platform.
          </p>
        </div>
        <div className="page-actions">
          <a className="btn btn-primary" href="mailto:support@camxora.com?subject=Camxora%20Studio%20access">
            Request access
          </a>
          <Link className="btn btn-ghost" href="/developers">
            Music API
          </Link>
        </div>
      </section>

      <div className="req">
        <div><b>Platform</b>Windows 10/11, macOS 13+</div>
        <div><b>Session</b>24-bit / 48 kHz, stem export</div>
        <div><b>Account</b>Camxora account with credits</div>
      </div>
    </div>
  );
}
