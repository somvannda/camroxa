import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import httpClient from '@/lib/http-client';
import type {
  BlogPostCreateRequest,
  BlogPostRecord,
  BlogPostUpdateRequest,
} from '@/types/blog-posts';

const BLOG_POSTS_QUERY_KEY = ['blog-posts'] as const;

export function useBlogPosts() {
  return useQuery({
    queryKey: BLOG_POSTS_QUERY_KEY,
    queryFn: () => httpClient.get<BlogPostRecord[]>('/api/v1/admin/blog-posts'),
  });
}

export function useCreateBlogPost() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BlogPostCreateRequest) =>
      httpClient.post<BlogPostRecord>('/api/v1/admin/blog-posts', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: BLOG_POSTS_QUERY_KEY });
    },
  });
}

export function useUpdateBlogPost() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { postId: string; payload: BlogPostUpdateRequest }) =>
      httpClient.put<BlogPostRecord>(`/api/v1/admin/blog-posts/${data.postId}`, data.payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: BLOG_POSTS_QUERY_KEY });
    },
  });
}

export function useDeleteBlogPost() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (postId: string) => httpClient.delete<void>(`/api/v1/admin/blog-posts/${postId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: BLOG_POSTS_QUERY_KEY });
    },
  });
}
