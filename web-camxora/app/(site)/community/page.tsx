import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";

export const metadata: Metadata = {
  title: "Community",
};

const creators = [
  {
    name: "Kanya",
    meta: "Khmer pop · 1.2M plays",
    image:
      "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&q=80",
  },
  {
    name: "Dara",
    meta: "R&B · 640K plays",
    image:
      "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=120&q=80",
  },
  {
    name: "Malis",
    meta: "Ballad · 310K plays",
    image:
      "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=120&q=80",
  },
  {
    name: "Rithy",
    meta: "EDM · 980K plays",
    image:
      "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=120&q=80",
  },
];

const guidelines = [
  {
    title: "Credit the people who made it",
    body: "If you remix a track, name the original creator and link back to their profile.",
  },
  {
    title: "Keep feedback useful",
    body: "Tell creators what worked and what could be stronger. No drive-by negativity.",
  },
  {
    title: "Share your process",
    body: "Prompts, styles, and behind-the-scenes notes help the next creator make something better.",
  },
];

export default function CommunityPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">People</div>
          <h1>Community</h1>
          <p>
            Follow Cambodian creators, join weekly challenges and get your tracks
            heard.
          </p>
        </div>
        <Link className="btn btn-primary" href="/create">
          <Icon name="fa-plus" /> Share a track
        </Link>
      </div>

      <section className="challenge">
        <div className="challenge-k">Weekly challenge · Week 42</div>
        <h2>Khmer Love — make a song about home.</h2>
        <p>
          Use a Khmer vocal and a traditional instrument. The top three entries get
          featured on the home page and 500 bonus credits.
        </p>
        <div className="challenge-meta">
          <span>Entries <b>128</b></span>
          <span>Deadline <b>Sunday 23:59</b></span>
          <span>Prize <b>500 credits</b></span>
        </div>
        <div className="page-actions" style={{ marginTop: 18 }}>
          <Link className="btn btn-primary" href="/create">
            Join the challenge
          </Link>
          <Link className="btn btn-ghost" href="/community#guidelines">
            Community rules
          </Link>
        </div>
      </section>

      <div className="sec-head">
        <h2>Creators to follow</h2>
        <Link href="/discover">Explore more</Link>
      </div>
      <div className="creator-grid">
        {creators.map((creator) => (
          <article className="creator-card" key={creator.name}>
            <img src={creator.image} alt={creator.name} />
            <div>
              <strong>{creator.name}</strong>
              <span>{creator.meta}</span>
            </div>
            <button className="follow" type="button">
              Follow
            </button>
          </article>
        ))}
      </div>

      <section className="panel community-guidelines" id="guidelines">
        <div className="sec-head">
          <h2>How we make music together</h2>
        </div>
        <div className="community-guideline-grid">
          {guidelines.map((item) => (
            <article key={item.title}>
              <span className="community-guideline-icon">
                <Icon name="fa-check" />
              </span>
              <div>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
