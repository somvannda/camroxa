export type PublicBlogPostSummary = {
  slug: string;
  title: string;
  excerpt: string;
  cover_image_url: string | null;
  category: string | null;
  author_name: string | null;
  published_at: string;
  updated_at: string;
};

export type PublicBlogPostDetail = PublicBlogPostSummary & {
  content: string;
  seo_title: string | null;
  seo_description: string | null;
};

const BLOG_REVALIDATE_SECONDS = 300;

function resolvePlatformApiBaseUrl(): string {
  return (
    process.env.NEXT_PUBLIC_PLATFORM_API_BASE_URL ??
    (process.env.NODE_ENV === "development"
      ? "http://localhost:8000/api/v1"
      : "https://api.camxora.com/api/v1")
  );
}

export async function getPublicBlogPosts(category?: string): Promise<PublicBlogPostSummary[]> {
  const url = new URL(`${resolvePlatformApiBaseUrl()}/blog-posts/public`);
  const normalizedCategory = category?.trim();
  if (normalizedCategory) {
    url.searchParams.set("category", normalizedCategory);
  }

  const response = await fetch(url.toString(), {
    next: { revalidate: BLOG_REVALIDATE_SECONDS },
  });

  if (!response.ok) {
    throw new Error(`Unable to load blog posts (${response.status})`);
  }

  return (await response.json()) as PublicBlogPostSummary[];
}

export async function getPublicBlogPost(slug: string): Promise<PublicBlogPostDetail | null> {
  const response = await fetch(
    `${resolvePlatformApiBaseUrl()}/blog-posts/public/${encodeURIComponent(slug)}`,
    { next: { revalidate: BLOG_REVALIDATE_SECONDS } },
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Unable to load blog post (${response.status})`);
  }

  return (await response.json()) as PublicBlogPostDetail;
}
