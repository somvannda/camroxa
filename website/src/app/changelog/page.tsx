import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { ContentPageShell } from "@/components/marketing/content-page-shell";
import { ReleaseNotesContent } from "@/components/marketing/release-notes-content";
import { getPublicBlogPosts, type PublicBlogPostSummary } from "@/lib/blog";
import { displayPostExcerpt } from "@/lib/release-notes";
export const metadata: Metadata = {
  title: "Changelog",
  description: "Release notes and desktop update history for Camxora.",
};

const RELEASE_NOTES_CATEGORY = "Release notes";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

export default async function ChangelogPage() {
  let posts: PublicBlogPostSummary[] = [];
  let loadError: string | null = null;

  try {
    posts = await getPublicBlogPosts(RELEASE_NOTES_CATEGORY);
  } catch (error) {
    loadError = error instanceof Error ? error.message : "Unable to load release notes.";
    posts = [];
  }

  const featuredPost = posts[0] ?? null;
  const secondaryPosts = posts.slice(1);

  return (
    <ContentPageShell
      eyebrow="Release notes"
      title="Changelog and desktop release history."
      description="What shipped in each Camxora desktop release — published from the admin portal."
      aside={
        <div className="space-y-5">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Stay current</div>
            <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
              What changed in each release.
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            Need the installer? Visit the download page for the latest published desktop build.
          </p>
          <Link
            className="inline-flex items-center gap-2 text-sm font-medium text-violet-200 transition hover:text-fuchsia-200"
            href="/download"
          >
            Go to download
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      }
    >
      {loadError ? (
        <section className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6">
          <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Changelog status</div>
          <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white">
            Release notes are temporarily unavailable.
          </div>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-200/72 md:text-base">{loadError}</p>
        </section>
      ) : featuredPost ? (
        <>
          <section className="rounded-[32px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] p-6 ring-1 ring-white/6">
            <div className="flex flex-wrap items-center gap-3 text-xs uppercase tracking-[0.18em] text-slate-400">
              <span>{featuredPost.category ?? RELEASE_NOTES_CATEGORY}</span>
              <span>{formatDate(featuredPost.published_at)}</span>
              <span>{featuredPost.author_name ?? "Camxora Team"}</span>
              <span className="rounded-full border border-emerald-400/30 bg-emerald-500/10 px-2.5 py-0.5 text-[10px] tracking-[0.14em] text-emerald-100">
                Latest
              </span>
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
              Read release notes
              <ArrowRight className="h-4 w-4" />
            </Link>
          </section>

          {secondaryPosts.length > 0 ? (
            <section className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
              {secondaryPosts.map((post) => (
                <article
                  key={post.slug}
                  className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6"
                >
                  <div className="flex flex-wrap items-center gap-3 text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    <span>{post.category ?? RELEASE_NOTES_CATEGORY}</span>
                    <span>{formatDate(post.published_at)}</span>
                  </div>
                  <h2 className="mt-4 font-display text-2xl font-semibold text-white">{post.title}</h2>
                  <p className="mt-3 text-sm leading-7 text-slate-200/72">
                    {displayPostExcerpt(post.excerpt)}
                  </p>
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
        </>
      ) : (
        <section className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6">
          <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Publishing queue</div>
          <div className="mt-3 font-display text-3xl font-semibold tracking-[-0.05em] text-white">
            No published release notes yet.
          </div>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-200/72 md:text-base">
            Publish blog posts with the category &ldquo;{RELEASE_NOTES_CATEGORY}&rdquo; from the admin
            portal — or enable changelog creation when publishing a desktop software update — to
            populate this page.
          </p>
        </section>
      )}
    </ContentPageShell>
  );
}
