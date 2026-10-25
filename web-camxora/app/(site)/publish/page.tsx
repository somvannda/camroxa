import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";

export const metadata: Metadata = {
  title: "Publish a track",
};

const checklist = [
  {
    title: "Finish the master",
    body: "Pick the final generation, check the vocal and mix, and download the audio you want to release.",
  },
  {
    title: "Write the release copy",
    body: "Add a title, a short description, and the genre or mood listeners should expect.",
  },
  {
    title: "Choose visibility",
    body: "Keep it in your library, add it to a playlist, or share it with the community.",
  },
  {
    title: "Credit collaborators",
    body: "Name anyone who wrote lyrics, produced, or performed on the track.",
  },
];

export default function PublishPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Creators</div>
          <h1>Publish a track.</h1>
          <p>
            Turn a finished generation into something listeners can find. Start in
            the studio, then add it to your library or a playlist.
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-primary" href="/create">
            <Icon name="fa-plus" /> Create a track
          </Link>
          <Link className="btn btn-ghost" href="/library">
            Open library
          </Link>
        </div>
      </div>

      <div className="publish-steps">
        {checklist.map((item, index) => (
          <article key={item.title} className="panel">
            <span>{String(index + 1).padStart(2, "0")}</span>
            <h2>{item.title}</h2>
            <p>{item.body}</p>
          </article>
        ))}
      </div>

      <section className="publish-band">
        <div>
          <div className="eyebrow">Release checklist</div>
          <h2>Ready to be heard?</h2>
          <p>
            Publishing is optional. You can keep every track private, share a private
            link, or publish it to your public profile.
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-primary" href="/create">Start creating</Link>
          <Link className="btn btn-ghost" href="/community">Share with the community</Link>
        </div>
      </section>

      <section className="panel publish-note">
        <h2>What happens after publishing</h2>
        <p>
          Published tracks can appear on your artist profile, in public playlists,
          and in Camxora charts as listeners play them. You can unpublish at any time
          from your library.
        </p>
        <p>
          Only publish audio you have the rights to use. For copyright questions, see
          the <Link href="/legal#copyright">copyright policy</Link>.
        </p>
      </section>
    </div>
  );
}
