import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Blog",
};

const posts = [
  {
    tag: "Product",
    title: "Why Camxora is packs-only",
    body: "One-time credits instead of another subscription. Here is the reasoning behind the change.",
    date: "October 2026",
  },
  {
    tag: "Creators",
    title: "How to write a prompt that keeps its hook",
    body: "A practical guide to structure, style tags, and giving the model enough room to surprise you.",
    date: "October 2026",
  },
  {
    tag: "Community",
    title: "Inside the Khmer Love challenge",
    body: "What the first community challenge taught us about traditional instruments and AI vocals.",
    date: "October 2026",
  },
];

export default function BlogPage() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Blog</div>
          <h1>Notes from Camxora.</h1>
          <p>Product decisions, creator guides, and what we are learning from the community.</p>
        </div>
        <Link className="btn btn-ghost" href="/changelog">View changelog</Link>
      </div>

      <div className="blog-grid">
        {posts.map((post) => (
          <article className="blog-card panel" key={post.title}>
            <span className="blog-tag">{post.tag}</span>
            <h2>{post.title}</h2>
            <p>{post.body}</p>
            <span className="blog-date">{post.date}</span>
          </article>
        ))}
      </div>
    </div>
  );
}
