'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { useRouter } from 'next/navigation';

import { useAuth } from '@/components/auth-provider';
import {
  fetchLikedTrackIds,
  likeTrack,
  unlikeTrack,
} from '@/lib/library-api';

type LikesState = {
  likedIds: Set<string>;
  loading: boolean;
  isLiked: (trackId: string) => boolean;
  toggleLike: (trackId: string) => Promise<void>;
  refresh: () => Promise<void>;
};

const LikesContext = createContext<LikesState | null>(null);

export function LikesProvider({ children }: { children: ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const [likedIds, setLikedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!user) {
      setLikedIds(new Set());
      return;
    }
    setLoading(true);
    try {
      const ids = await fetchLikedTrackIds();
      setLikedIds(new Set(ids));
    } catch {
      setLikedIds(new Set());
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (authLoading) return;
    void refresh();
  }, [authLoading, refresh]);

  const value = useMemo<LikesState>(
    () => ({
      likedIds,
      loading,
      isLiked: (trackId) => likedIds.has(trackId),
      async toggleLike(trackId) {
        if (!user) return;
        const currentlyLiked = likedIds.has(trackId);
        setLikedIds((prev) => {
          const next = new Set(prev);
          if (currentlyLiked) next.delete(trackId);
          else next.add(trackId);
          return next;
        });
        try {
          if (currentlyLiked) await unlikeTrack(trackId);
          else await likeTrack(trackId);
        } catch {
          setLikedIds((prev) => {
            const next = new Set(prev);
            if (currentlyLiked) next.add(trackId);
            else next.delete(trackId);
            return next;
          });
        }
      },
      refresh,
    }),
    [likedIds, loading, user, refresh],
  );

  return <LikesContext.Provider value={value}>{children}</LikesContext.Provider>;
}

export function useLikes() {
  const ctx = useContext(LikesContext);
  if (!ctx) throw new Error('useLikes must be used within LikesProvider');
  return ctx;
}

export function useOptionalLikes() {
  return useContext(LikesContext);
}

/** Heart control — prompts sign-in when logged out. */
export function LikeButton({
  trackId,
  className = '',
  size = 'md',
}: {
  trackId: string;
  className?: string;
  size?: 'sm' | 'md';
}) {
  const { user } = useAuth();
  const likes = useOptionalLikes();
  const router = useRouter();
  const liked = Boolean(likes?.isLiked(trackId));
  const iconClass = size === 'sm' ? 'h-4 w-4' : 'h-5 w-5';

  return (
    <button
      type="button"
      aria-label={liked ? 'Remove from Liked Songs' : 'Save to Liked Songs'}
      className={`inline-flex items-center justify-center rounded-full transition hover:scale-105 ${
        liked ? 'text-fuchsia-400' : 'text-slate-400 hover:text-white'
      } ${className}`}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        if (!user) {
          const next = typeof window !== 'undefined' ? window.location.pathname : '/library';
          router.push(`/login?next=${encodeURIComponent(next)}`);
          return;
        }
        void likes?.toggleLike(trackId);
      }}
    >
      <svg
        viewBox="0 0 24 24"
        className={iconClass}
        fill={liked ? 'currentColor' : 'none'}
        stroke="currentColor"
        strokeWidth="2"
        aria-hidden
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"
        />
      </svg>
    </button>
  );
}
