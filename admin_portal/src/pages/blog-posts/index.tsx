import { useMemo, useState } from 'react';
import {
  Edit3,
  FileText,
  Globe,
  Plus,
  RefreshCcw,
  Search,
  Trash2,
} from 'lucide-react';

import {
  useBlogPosts,
  useCreateBlogPost,
  useDeleteBlogPost,
  useUpdateBlogPost,
} from '@/hooks/use-blog-posts';
import { toast } from '@/hooks/use-toast';
import type {
  BlogPostCreateRequest,
  BlogPostRecord,
  BlogPostUpdateRequest,
} from '@/types/blog-posts';
import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { ErrorState } from '@/components/shared/error-state';
import { LoadingSkeleton } from '@/components/shared/loading-skeleton';
import { PageHeader } from '@/components/shared/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';

type PostFilter = 'all' | 'published' | 'draft';

type BlogPostFormState = {
  title: string;
  slug: string;
  excerpt: string;
  content: string;
  coverImageUrl: string;
  category: string;
  authorName: string;
  seoTitle: string;
  seoDescription: string;
  isPublished: boolean;
  publishedAt: string;
};

function createEmptyForm(): BlogPostFormState {
  return {
    title: '',
    slug: '',
    excerpt: '',
    content: '',
    coverImageUrl: '',
    category: '',
    authorName: 'Camxora Team',
    seoTitle: '',
    seoDescription: '',
    isPublished: false,
    publishedAt: '',
  };
}

function postToForm(post: BlogPostRecord): BlogPostFormState {
  return {
    title: post.title,
    slug: post.slug,
    excerpt: post.excerpt,
    content: post.content,
    coverImageUrl: post.cover_image_url ?? '',
    category: post.category ?? '',
    authorName: post.author_name ?? '',
    seoTitle: post.seo_title ?? '',
    seoDescription: post.seo_description ?? '',
    isPublished: post.is_published,
    publishedAt: post.published_at ? post.published_at.slice(0, 16) : '',
  };
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function getStatusLabel(post: BlogPostRecord): 'Published' | 'Draft' {
  return post.is_published ? 'Published' : 'Draft';
}

function getStatusBadgeClass(post: BlogPostRecord): string {
  return post.is_published
    ? 'border-emerald-400/25 bg-emerald-500/10 text-emerald-300'
    : 'border-amber-400/25 bg-amber-500/10 text-amber-300';
}

function buildPayload(form: BlogPostFormState): BlogPostCreateRequest | BlogPostUpdateRequest | null {
  const title = form.title.trim();
  const excerpt = form.excerpt.trim();
  const content = form.content.trim();

  if (!title) {
    toast({ title: 'Title is required', variant: 'destructive' });
    return null;
  }
  if (!excerpt) {
    toast({ title: 'Excerpt is required', variant: 'destructive' });
    return null;
  }
  if (!content) {
    toast({ title: 'Content is required', variant: 'destructive' });
    return null;
  }

  return {
    title,
    slug: form.slug.trim() || null,
    excerpt,
    content,
    cover_image_url: form.coverImageUrl.trim() || null,
    category: form.category.trim() || null,
    author_name: form.authorName.trim() || null,
    seo_title: form.seoTitle.trim() || null,
    seo_description: form.seoDescription.trim() || null,
    is_published: form.isPublished,
    published_at: form.publishedAt ? new Date(form.publishedAt).toISOString() : null,
  };
}

export default function BlogPostsPage() {
  const postsQuery = useBlogPosts();
  const createMutation = useCreateBlogPost();
  const updateMutation = useUpdateBlogPost();
  const deleteMutation = useDeleteBlogPost();

  const [createOpen, setCreateOpen] = useState(false);
  const [editPost, setEditPost] = useState<BlogPostRecord | null>(null);
  const [deletePost, setDeletePost] = useState<BlogPostRecord | null>(null);
  const [searchValue, setSearchValue] = useState('');
  const [filterValue, setFilterValue] = useState<PostFilter>('all');
  const [form, setForm] = useState<BlogPostFormState>(() => createEmptyForm());

  const posts = useMemo(() => {
    const items = postsQuery.data ?? [];
    return [...items].sort((a, b) => {
      const aTime = Date.parse(a.published_at ?? a.updated_at ?? a.created_at);
      const bTime = Date.parse(b.published_at ?? b.updated_at ?? b.created_at);
      return bTime - aTime;
    });
  }, [postsQuery.data]);

  const filteredPosts = useMemo(() => {
    const normalizedSearch = searchValue.trim().toLowerCase();
    return posts.filter((post) => {
      if (filterValue === 'published' && !post.is_published) return false;
      if (filterValue === 'draft' && post.is_published) return false;

      if (!normalizedSearch) {
        return true;
      }

      return [
        post.title,
        post.slug,
        post.category ?? '',
        post.author_name ?? '',
        post.excerpt,
      ]
        .join(' ')
        .toLowerCase()
        .includes(normalizedSearch);
    });
  }, [filterValue, posts, searchValue]);

  function openCreate() {
    setForm(createEmptyForm());
    setCreateOpen(true);
  }

  function openEdit(post: BlogPostRecord) {
    setForm(postToForm(post));
    setEditPost(post);
  }

  function closeEditor() {
    if (createMutation.isPending || updateMutation.isPending) return;
    setCreateOpen(false);
    setEditPost(null);
    setForm(createEmptyForm());
  }

  async function handleCreate() {
    const payload = buildPayload(form);
    if (!payload) return;
    try {
      await createMutation.mutateAsync(payload);
      toast({ title: 'Blog post created' });
      closeEditor();
    } catch (error) {
      toast({
        title: 'Unable to create post',
        description: error instanceof Error ? error.message : 'Please try again.',
        variant: 'destructive',
      });
    }
  }

  async function handleUpdate() {
    if (!editPost) return;
    const payload = buildPayload(form);
    if (!payload) return;
    try {
      await updateMutation.mutateAsync({ postId: editPost.id, payload });
      toast({ title: 'Blog post updated' });
      closeEditor();
    } catch (error) {
      toast({
        title: 'Unable to update post',
        description: error instanceof Error ? error.message : 'Please try again.',
        variant: 'destructive',
      });
    }
  }

  async function handleDelete() {
    if (!deletePost) return;
    try {
      await deleteMutation.mutateAsync(deletePost.id);
      toast({ title: 'Blog post deleted' });
      setDeletePost(null);
    } catch (error) {
      toast({
        title: 'Unable to delete post',
        description: error instanceof Error ? error.message : 'Please try again.',
        variant: 'destructive',
      });
    }
  }

  if (postsQuery.isLoading) {
    return <LoadingSkeleton />;
  }

  if (postsQuery.isError) {
    return <ErrorState message={postsQuery.error.message} onRetry={() => postsQuery.refetch()} />;
  }

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        eyebrow="Website content"
        title="Blog Posts"
        description="Manage editorial content for the public website, control draft vs published visibility, and keep SEO metadata aligned with marketing goals."
        actions={
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" />
            Create post
          </Button>
        }
      />

      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-slate-100">
              <Globe className="h-4 w-4 text-slate-300" />
              Website publishing
            </CardTitle>
            <div className="text-sm text-slate-400">
              Search, filter, and publish blog posts that feed the public website.
            </div>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative min-w-[260px]">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <Input
                value={searchValue}
                onChange={(e) => setSearchValue(e.target.value)}
                placeholder="Search title, slug, category, or author"
                className="pl-10"
              />
            </div>
            <Select
              value={filterValue}
              onValueChange={(value) => setFilterValue(value as PostFilter)}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All posts</SelectItem>
                <SelectItem value="published">Published</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={() => postsQuery.refetch()}>
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3 text-sm text-slate-400">
            <Badge variant="outline" className="border-violet-400/20 bg-violet-500/10 text-violet-200">
              {posts.length.toLocaleString()} total posts
            </Badge>
            <span>{posts.filter((post) => post.is_published).length.toLocaleString()} published</span>
            <span>{posts.filter((post) => !post.is_published).length.toLocaleString()} drafts</span>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Post</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Author</TableHead>
                <TableHead>Published</TableHead>
                <TableHead>Updated</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredPosts.map((post) => (
                <TableRow key={post.id}>
                  <TableCell className="align-top">
                    <div className="space-y-1">
                      <div className="font-medium text-white">{post.title}</div>
                      <div className="font-mono text-xs text-slate-500">/{post.slug}</div>
                      <div className="line-clamp-2 max-w-xl text-xs text-slate-400">
                        {post.excerpt}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>{post.category ?? '—'}</TableCell>
                  <TableCell>
                    <Badge className={getStatusBadgeClass(post)}>{getStatusLabel(post)}</Badge>
                  </TableCell>
                  <TableCell>{post.author_name ?? '—'}</TableCell>
                  <TableCell>{formatDateTime(post.published_at)}</TableCell>
                  <TableCell>{formatDateTime(post.updated_at)}</TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-2">
                      <Button variant="outline" size="sm" onClick={() => openEdit(post)}>
                        <Edit3 className="h-3.5 w-3.5" />
                        Edit
                      </Button>
                      <Button variant="destructive" size="sm" onClick={() => setDeletePost(post)}>
                        <Trash2 className="h-3.5 w-3.5" />
                        Delete
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {filteredPosts.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="py-10 text-center text-sm text-slate-500">
                    {posts.length === 0
                      ? 'No blog posts created yet. Create the first post to populate the public blog.'
                      : 'No blog posts match the current filters.'}
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={createOpen || !!editPost} onOpenChange={(open) => (!open ? closeEditor() : null)}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>{editPost ? 'Edit blog post' : 'Create blog post'}</DialogTitle>
            <DialogDescription>
              Manage public-facing content, publication timing, and SEO metadata for the website blog.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-5">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="title">Title</Label>
                <Input
                  id="title"
                  value={form.title}
                  onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
                  placeholder="Announcing the next CAMXORA workflow release"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="slug">Slug</Label>
                <Input
                  id="slug"
                  value={form.slug}
                  onChange={(e) => setForm((prev) => ({ ...prev, slug: e.target.value }))}
                  placeholder="optional-manual-slug"
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="excerpt">Excerpt</Label>
              <Textarea
                id="excerpt"
                value={form.excerpt}
                onChange={(e) => setForm((prev) => ({ ...prev, excerpt: e.target.value }))}
                rows={3}
                placeholder="Short summary for cards, previews, and metadata."
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="content">Content</Label>
              <Textarea
                id="content"
                value={form.content}
                onChange={(e) => setForm((prev) => ({ ...prev, content: e.target.value }))}
                rows={14}
                placeholder="Write the full blog post content here. Plain text paragraphs are supported."
              />
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="grid gap-2">
                <Label htmlFor="category">Category</Label>
                <Input
                  id="category"
                  value={form.category}
                  onChange={(e) => setForm((prev) => ({ ...prev, category: e.target.value }))}
                  placeholder="Product updates"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="authorName">Author</Label>
                <Input
                  id="authorName"
                  value={form.authorName}
                  onChange={(e) => setForm((prev) => ({ ...prev, authorName: e.target.value }))}
                  placeholder="Camxora Team"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="coverImageUrl">Cover image URL</Label>
                <Input
                  id="coverImageUrl"
                  value={form.coverImageUrl}
                  onChange={(e) => setForm((prev) => ({ ...prev, coverImageUrl: e.target.value }))}
                  placeholder="https://..."
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="seoTitle">SEO title</Label>
                <Input
                  id="seoTitle"
                  value={form.seoTitle}
                  onChange={(e) => setForm((prev) => ({ ...prev, seoTitle: e.target.value }))}
                  placeholder="Optional override for browser title"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="seoDescription">SEO description</Label>
                <Textarea
                  id="seoDescription"
                  value={form.seoDescription}
                  onChange={(e) => setForm((prev) => ({ ...prev, seoDescription: e.target.value }))}
                  rows={3}
                  placeholder="Optional search-focused description"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-[180px_minmax(0,1fr)]">
              <div className="grid gap-2">
                <Label>Status</Label>
                <Select
                  value={form.isPublished ? 'published' : 'draft'}
                  onValueChange={(value) =>
                    setForm((prev) => ({ ...prev, isPublished: value === 'published' }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="draft">Draft</SelectItem>
                    <SelectItem value="published">Published</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="publishedAt">Publish at</Label>
                <Input
                  id="publishedAt"
                  type="datetime-local"
                  value={form.publishedAt}
                  onChange={(e) => setForm((prev) => ({ ...prev, publishedAt: e.target.value }))}
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeEditor}>
              Cancel
            </Button>
            <Button
              onClick={editPost ? handleUpdate : handleCreate}
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              <FileText className="h-4 w-4" />
              {createMutation.isPending || updateMutation.isPending
                ? 'Saving...'
                : editPost
                  ? 'Save changes'
                  : 'Create post'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deletePost}
        onOpenChange={(open) => (!open ? setDeletePost(null) : null)}
        title="Delete blog post?"
        description={`This permanently removes "${deletePost?.title ?? 'this post'}" from admin and the public website.`}
        onConfirm={handleDelete}
        variant="destructive"
        confirmText={deleteMutation.isPending ? 'Deleting...' : 'Delete post'}
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}
