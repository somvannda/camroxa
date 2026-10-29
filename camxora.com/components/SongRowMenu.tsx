"use client";

import Link from "next/link";

import { Icon } from "@/components/Icon";
import {
  SMenu,
  SMenuItem,
  SMenuSeparator,
  SMenuSub,
  SMenuSubContent,
  SMenuSubTrigger,
} from "@/components/ui/s-menu";
import { clipDownloadUrl } from "@/lib/clip-utils";
import type { WebMusicClip, WebMusicGeneration } from "@/lib/library-api";
import type {
  WebMusicPlaylistSummary,
  WebMusicWorkspace,
} from "@/lib/web-music-api";

export type SongRowMenuProps = {
  song: WebMusicGeneration;
  clip: WebMusicClip;
  ready: boolean;
  instrumental: boolean;
  liked: boolean;
  disliked: boolean;
  playlists: WebMusicPlaylistSummary[];
  workspaces: WebMusicWorkspace[];
  trashDisabled?: boolean;
  onLike: () => void;
  onDislike: () => void;
  onShare: () => void;
  onCopyLink: () => void;
  onCover: () => void;
  onReusePrompt: () => void;
  onMashup: () => void;
  onVoice: () => void;
  onDetails: () => void;
  onMove: (workspace: WebMusicWorkspace) => void;
  onQueue: () => void;
  onAddToPlaylist: (playlist: WebMusicPlaylistSummary) => void;
  onRadio: () => void;
  onReport: () => void;
  onTrash: () => void;
};

/**
 * The song ⋮ menu, shared by Create and Library so both surfaces offer exactly
 * the same actions in the same order (Suno parity).
 */
export function SongRowMenu({
  song,
  clip,
  ready,
  instrumental,
  liked,
  disliked,
  playlists,
  workspaces,
  trashDisabled = false,
  onLike,
  onDislike,
  onShare,
  onCopyLink,
  onCover,
  onReusePrompt,
  onMashup,
  onVoice,
  onDetails,
  onMove,
  onQueue,
  onAddToPlaylist,
  onRadio,
  onReport,
  onTrash,
}: SongRowMenuProps) {
  const variant = clip.variant || "ok";
  return (
    <SMenu
      align="end"
      sideOffset={6}
      trigger={
        <button type="button" className="s-row-more" aria-label="More options">
          <Icon name="fa-ellipsis-vertical" />
        </button>
      }
    >
      <SMenuItem onSelect={onLike}>
        <Icon name="fa-heart" /> {liked ? "Remove like" : "Like"}
      </SMenuItem>
      <SMenuItem onSelect={onDislike}>
        <Icon name="fa-thumbs-down" /> {disliked ? "Remove dislike" : "Dislike"}
      </SMenuItem>
      <SMenuItem onSelect={onShare}>
        <Icon name="fa-share-nodes" /> Share
      </SMenuItem>
      <SMenuItem onSelect={onCopyLink}>
        <Icon name="fa-link" /> Copy link
      </SMenuItem>
      <SMenuSub>
        <SMenuSubTrigger disabled={!ready}>
          <Icon name="fa-download" /> Download
        </SMenuSubTrigger>
        <SMenuSubContent>
          <SMenuItem asChild>
            <a href={clip.download_url || clipDownloadUrl(song.id, variant, "mp3")} download>
              MP3
            </a>
          </SMenuItem>
          <SMenuItem asChild>
            <a href={clipDownloadUrl(song.id, variant, "wav")} download>
              WAV
            </a>
          </SMenuItem>
          {!instrumental ? (
            <>
              <SMenuItem asChild>
                <a href={clipDownloadUrl(song.id, variant, "lrc")} download>
                  LRC
                </a>
              </SMenuItem>
              <SMenuItem asChild>
                <a href={clipDownloadUrl(song.id, variant, "srt")} download>
                  SRT
                </a>
              </SMenuItem>
            </>
          ) : null}
        </SMenuSubContent>
      </SMenuSub>

      <SMenuSeparator />

      <SMenuSub>
        <SMenuSubTrigger>
          <Icon name="fa-repeat" /> Remix
        </SMenuSubTrigger>
        <SMenuSubContent>
          <SMenuItem disabled={!ready} onSelect={onCover}>
            <Icon name="fa-retweet" /> Cover
          </SMenuItem>
          <SMenuItem onSelect={onReusePrompt}>
            <Icon name="fa-quote-left" /> Reuse Prompt
          </SMenuItem>
          <SMenuItem disabled={!ready} onSelect={onMashup}>
            <Icon name="fa-code-merge" /> Mashup
          </SMenuItem>
          <SMenuItem disabled title="Coming soon">
            <Icon name="fa-waveform" /> Sample this song
          </SMenuItem>
          <SMenuItem disabled title="Coming soon">
            <Icon name="fa-wand-sparkles" /> Use as Inspiration
          </SMenuItem>
          <SMenuItem onSelect={onVoice}>
            <Icon name="fa-microphone-lines" /> Voice
          </SMenuItem>
        </SMenuSubContent>
      </SMenuSub>

      <SMenuSub>
        <SMenuSubTrigger>
          <Icon name="fa-pen-to-square" /> Edit
        </SMenuSubTrigger>
        <SMenuSubContent>
          <SMenuItem onSelect={onDetails}>
            <Icon name="fa-circle-info" /> Song Details
          </SMenuItem>
          <SMenuItem asChild>
            <Link href="/studio/editor">
              <Icon name="fa-table-columns" /> Open in Editor
            </Link>
          </SMenuItem>
          <SMenuItem disabled title="Replace Section needs the section editor — coming soon">
            <Icon name="fa-scissors" /> Replace Section
          </SMenuItem>
          <SMenuItem disabled title="No crop service yet">
            <Icon name="fa-crop-simple" /> Crop Song
          </SMenuItem>
        </SMenuSubContent>
      </SMenuSub>

      <SMenuSub>
        <SMenuSubTrigger>
          <Icon name="fa-folder-tree" /> Manage
        </SMenuSubTrigger>
        <SMenuSubContent>
          {workspaces.length ? (
            workspaces.map((workspace) => (
              <SMenuItem
                key={workspace.id}
                disabled={workspace.id === song.workspace_id}
                onSelect={() => onMove(workspace)}
              >
                <Icon name="fa-folder" /> {workspace.name}
              </SMenuItem>
            ))
          ) : (
            <SMenuItem disabled>No workspaces yet</SMenuItem>
          )}
        </SMenuSubContent>
      </SMenuSub>

      <SMenuSeparator />

      <SMenuItem disabled={!ready} onSelect={onQueue}>
        <Icon name="fa-bars-staggered" /> Add to Queue
      </SMenuItem>
      <SMenuSub>
        <SMenuSubTrigger>
          <Icon name="fa-list" /> Add to Playlist
        </SMenuSubTrigger>
        <SMenuSubContent>
          {playlists.length ? (
            playlists.map((playlist) => (
              <SMenuItem key={playlist.id} onSelect={() => onAddToPlaylist(playlist)}>
                <Icon name="fa-rectangle-list" /> {playlist.name}
              </SMenuItem>
            ))
          ) : (
            <SMenuItem disabled>No playlists yet</SMenuItem>
          )}
        </SMenuSubContent>
      </SMenuSub>
      <SMenuItem disabled={!ready} onSelect={onRadio}>
        <Icon name="fa-tower-broadcast" /> Song Radio
      </SMenuItem>

      <SMenuSeparator />

      <SMenuItem
        onSelect={() => {
          window.location.href = `/publish?clip=${encodeURIComponent(song.id)}&variant=${encodeURIComponent(variant)}`;
        }}
      >
        <Icon name="fa-arrow-up-from-bracket" /> Publish
      </SMenuItem>
      <SMenuItem asChild>
        <Link href="/studio/editor">
          <Icon name="fa-table-columns" /> Open in Studio
        </Link>
      </SMenuItem>

      <SMenuSeparator />

      <SMenuItem onSelect={onReport}>
        <Icon name="fa-flag" /> Report
      </SMenuItem>
      <SMenuItem disabled={trashDisabled} onSelect={onTrash}>
        <Icon name="fa-trash" /> Move to Trash
      </SMenuItem>
    </SMenu>
  );
}
