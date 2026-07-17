export type BlogPostRecord = {
  id: string;
  slug: string;
  title: string;
  excerpt: string;
  content: string;
  cover_image_url: string | null;
  category: string | null;
  author_name: string | null;
  seo_title: string | null;
  seo_description: string | null;
  is_published: boolean;
  published_at: string | null;
  created_at: string;
  updated_at: string;
};

export type BlogPostCreateRequest = {
  title: string;
  slug?: string | null;
  excerpt: string;
  content: string;
  cover_image_url?: string | null;
  category?: string | null;
  author_name?: string | null;
  seo_title?: string | null;
  seo_description?: string | null;
  is_published: boolean;
  published_at?: string | null;
};

export type BlogPostUpdateRequest = BlogPostCreateRequest;

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
