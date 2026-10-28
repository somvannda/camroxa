import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";

export const metadata: Metadata = {
  title: "About",
};

const principles = [
  {
    title: "Creators first",
    body: "The people making music should keep control of their work, their credits, and their audience.",
  },
  {
    title: "Simple by default",
    body: "One credit balance, one workspace, and no hidden plan maze. Start free, add credits when you need them.",
  },
  {
    title: "Built in Cambodia",
    body: "Camxora is made for Khmer creators and listeners, with a catalog that can travel anywhere.",
  },
];

const team = [
  { name: "Somvannda", role: "Founder & product" },
  { name: "Engineering", role: "Platform & generation" },
  { name: "Design", role: "Studio & listening" },
];

const roles = [
  { title: "Product engineer", meta: "Full-time · Phnom Penh or remote" },
  { title: "Creator partnerships", meta: "Full-time · Phnom Penh" },
  { title: "Music community lead", meta: "Contract · Remote" },
];

export default function AboutPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Company</div>
          <h1>Music, made by more people.</h1>
          <p>
            Camxora is building the home of AI music in Cambodia: a place to listen,
            create, and share without needing a studio or a record label.
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-primary" href="/create">
            <Icon name="fa-plus" /> Start creating
          </Link>
          <Link className="btn btn-ghost" href="/contact">Talk to us</Link>
        </div>
      </div>

      <section className="panel about-story">
        <div>
          <div className="eyebrow">Our story</div>
          <h2>From a small experiment to a creator platform.</h2>
          <p>
            Camxora started with a simple question: what happens when a good idea no
            longer needs a full studio to become a song? We built a workspace around
            that answer, then added a listening experience so the music has somewhere
            to live.
          </p>
          <p>
            Today the platform covers generation, discovery, charts, playlists, and
            the Music API. The goal is not to replace artists. It is to give more
            people the tools to become one.
          </p>
        </div>
        <div className="about-stats">
          <div><b>2026</b><span>Camxora launched</span></div>
          <div><b>KH</b><span>Built in Cambodia</span></div>
          <div><b>1</b><span>Shared credit wallet</span></div>
        </div>
      </section>

      <div className="sec-head">
        <h2>What we believe</h2>
      </div>
      <div className="about-principles">
        {principles.map((item) => (
          <article key={item.title} className="feature">
            <span className="feature-ico"><Icon name="fa-check" /></span>
            <h3>{item.title}</h3>
            <p>{item.body}</p>
          </article>
        ))}
      </div>

      <div className="sec-head">
        <h2>The team</h2>
      </div>
      <div className="team-grid">
        {team.map((member) => (
          <article className="team" key={member.name}>
            <div className="team-mark">{member.name.slice(0, 1)}</div>
            <h3>{member.name}</h3>
            <p>{member.role}</p>
          </article>
        ))}
      </div>

      <section className="panel about-jobs">
        <div className="sec-head">
          <h2>Build the next chapter</h2>
          <a href="mailto:support@camxora.com?subject=Camxora%20careers">Get in touch</a>
        </div>
        {roles.map((role) => (
          <div className="job" key={role.title}>
            <div>
              <b>{role.title}</b>
              <span>{role.meta}</span>
            </div>
            <a className="btn btn-ghost" href="mailto:support@camxora.com?subject=Camxora%20careers">
              Apply
            </a>
          </div>
        ))}
      </section>
    </div>
  );
}
