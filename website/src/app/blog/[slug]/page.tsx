import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ContentPageShell } from "@/components/marketing/content-page-shell";
import { ReleaseNotesContent } from "@/components/marketing/release-notes-content";
import { getPublicBlogPost, getPublicBlogPosts } from "@/lib/blog";
import { displayPostExcerpt } from "@/lib/release-notes";

type PageProps = {
  params: Promise<{ slug: string }>;
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function renderParagraphs(content: string) {
  return content
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);
}

function isReleaseNotesPost(category: string | null | undefined, content: string): boolean {
  if ((category ?? "").toLowerCase() === "release notes") {
    return true;
  }
  return /^##\s*\[/m.test(content) || /###\s+(Added|Fixed|Changed)/im.test(content);
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const post = await getPublicBlogPost(slug);

  if (!post) {
    return {
      title: "Blog Post Not Found",
      description: "The requested article could not be found.",
    };
  }

  return {
    title: post.seo_title ?? post.title,
    description: post.seo_description ?? displayPostExcerpt(post.excerpt, post.content),
  };
}

export async function generateStaticParams() {
  try {
    const posts = await getPublicBlogPosts();
    return posts.map((post) => ({ slug: post.slug }));
  } catch {
    return [];
  }
}

export default async function BlogPostPage({ params }: PageProps) {
  const { slug } = await params;
  const post = await getPublicBlogPost(slug);

  if (!post) {
    notFound();
  }

  const excerpt = displayPostExcerpt(post.excerpt, post.content);
  const releaseNotes = isReleaseNotesPost(post.category, post.content);

  return (
    <ContentPageShell
      eyebrow={post.category ?? "Blog"}
      title={post.title}
      description={excerpt}
      aside={
        <div className="space-y-5">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Published</div>
            <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
              {formatDate(post.published_at)}
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            Author: {post.author_name ?? "Camxora Team"}
          </p>
        </div>
      }
    >
      <article className="rounded-[32px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] p-6 ring-1 ring-white/6 md:p-8">
        {releaseNotes ? (
          <ReleaseNotesContent content={post.content} />
        ) : (
          <div className="space-y-6">
            {renderParagraphs(post.content).map((paragraph, index) => (
              <p key={index} className="text-base leading-8 text-slate-200/80 md:text-lg">
                {paragraph}
              </p>
            ))}
          </div>
        )}
      </article>
    </ContentPageShell>
  );
}
