import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { ContentPageShell } from "@/components/marketing/content-page-shell";
import { getPublicBlogPosts, type PublicBlogPostSummary } from "@/lib/blog";
import { displayPostExcerpt } from "@/lib/release-notes";
export const metadata: Metadata = {
  title: "Blog",
  description: "Product updates, guides, and release notes for Camxora.",
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

export default async function BlogPage() {
  let posts: PublicBlogPostSummary[] = [];
  try {
    posts = await getPublicBlogPosts();
  } catch {
    posts = [];
  }

  const featuredPost = posts[0] ?? null;
  const secondaryPosts = posts.slice(1);

  return (
    <ContentPageShell
      eyebrow="Updates"
      title="Guides and stories for building faceless YouTube music channels."
      description="Product updates, workflow tips, and release notes as Camxora grows from export-ready videos to full publishing."
      aside={
        <div className="space-y-5">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-400">From the team</div>
            <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
              Learn the faceless workflow.
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            Tips for lyrics-to-video production, channel operations, and what&apos;s shipping next.
          </p>
        </div>
      }
    >
      {featuredPost ? (
        <section className="rounded-[32px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] p-6 ring-1 ring-white/6">
          <div className="flex flex-wrap items-center gap-3 text-xs uppercase tracking-[0.18em] text-slate-400">
            <span>{featuredPost.category ?? "Latest update"}</span>
            <span>{formatDate(featuredPost.published_at)}</span>
            <span>{featuredPost.author_name ?? "Camxora Team"}</span>
          </div>
          <h2 className="mt-5 font-display text-4xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
            {featuredPost.title}
          </h2>
          <p className="mt-4 max-w-3xl text-base leading-8 text-slate-200/72">
            {displayPostExcerpt(featuredPost.excerpt)}
          </p>
          <Link
            className="mt-6 inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-5 text-sm font-medium text-white shadow-[0_18px_44px_rgba(118,77,255,0.32)] transition hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400"
            href={`/blog/${featuredPost.slug}`}
          >
            Read article
            <ArrowRight className="h-4 w-4" />
          </Link>
        </section>
      ) : (
        <section className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6">
          <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Coming soon</div>
          <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white">
            No published articles yet.
          </div>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-200/72 md:text-base">
            We&apos;ll share guides and product stories here as Camxora grows. Meanwhile, check
            Download for the latest desktop release.
          </p>
        </section>
      )}

      {secondaryPosts.length > 0 ? (
        <section className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          {secondaryPosts.map((post) => (
            <article
              key={post.slug}
              className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6"
            >
              <div className="flex flex-wrap items-center gap-3 text-[11px] uppercase tracking-[0.18em] text-slate-400">
                <span>{post.category ?? "Editorial"}</span>
                <span>{formatDate(post.published_at)}</span>
              </div>
              <h2 className="mt-4 font-display text-2xl font-semibold text-white">{post.title}</h2>
              <p className="mt-3 text-sm leading-7 text-slate-200/72">{displayPostExcerpt(post.excerpt)}</p>
              <div className="mt-4 text-xs text-slate-400">{post.author_name ?? "Camxora Team"}</div>
              <Link
                className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-violet-200 transition hover:text-fuchsia-200"
                href={`/blog/${post.slug}`}
              >
                Read more
                <ArrowRight className="h-4 w-4" />
              </Link>
            </article>
          ))}
        </section>
      ) : null}
    </ContentPageShell>
  );
}
