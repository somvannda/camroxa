import { useState } from "react";
import { Button } from "../../components/button";
import { Icon } from "../../components/icon";
import type { VizzyRenderSummary } from "../../../electron/shared/types";
import { formatBytes, formatRenderDate } from "./vizzy-format";

export interface VizzyRendersPanelProps {
  items: VizzyRenderSummary[];
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onRefresh: () => void;
  onPlay: (name: string) => Promise<string | null>;
  onReveal: (name: string) => void;
  onDelete: (name: string) => Promise<void>;
}

/**
 * Renders rail: the managed `renders/` files with inline playback.
 *
 * It lives beside the hosted editor instead of floating over it: the editor is a
 * native `WebContentsView`, so any DOM drawn on top of its rectangle would be
 * hidden. Shrinking the editor column keeps both surfaces visible.
 */
export function VizzyRendersPanel({
  items,
  loading,
  error,
  onClose,
  onRefresh,
  onPlay,
  onReveal,
  onDelete,
}: VizzyRendersPanelProps) {
  const [confirming, setConfirming] = useState<string | null>(null);
  const [playing, setPlaying] = useState<string | null>(null);
  const [playUrl, setPlayUrl] = useState<string | null>(null);
  const [busyName, setBusyName] = useState<string | null>(null);

  const play = async (name: string): Promise<void> => {
    if (playing === name) {
      setPlaying(null);
      setPlayUrl(null);
      return;
    }
    setBusyName(name);
    try {
      const url = await onPlay(name);
      setPlaying(url ? name : null);
      setPlayUrl(url);
    } finally {
      setBusyName(null);
    }
  };

  const remove = async (name: string): Promise<void> => {
    setBusyName(name);
    try {
      await onDelete(name);
      if (playing === name) {
        setPlaying(null);
        setPlayUrl(null);
      }
      setConfirming(null);
    } finally {
      setBusyName(null);
    }
  };

  return (
    <div
      className="flex h-full min-h-0 flex-col rounded-card border border-border bg-surface-1 shadow-2xl"
      role="region"
      aria-label="Renders"
      data-testid="vizzy-renders-panel"
    >
      <div className="flex h-10 shrink-0 items-center gap-2 border-b border-border px-3">
        <Icon name="fa-clapperboard" size={13} className="text-text-muted" />
        <span className="text-caption uppercase tracking-wide text-text-muted">Renders</span>
        <span className="text-meta text-text-muted">{items.length}</span>
        <div className="ml-auto flex items-center gap-1">
          <button
            type="button"
            aria-label="Refresh renders"
            className="flex h-6 w-6 items-center justify-center rounded-[6px] text-text-muted hover:bg-surface-hover hover:text-text-primary"
            onClick={onRefresh}
            disabled={loading}
          >
            <Icon name="fa-rotate" size={12} />
          </button>
          <button
            type="button"
            aria-label="Close renders"
            className="flex h-6 w-6 items-center justify-center rounded-[6px] text-text-muted hover:bg-surface-hover hover:text-text-primary"
            onClick={onClose}
          >
            <Icon name="fa-xmark" size={13} />
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-2" data-testid="vizzy-renders-list">
        {error ? (
          <p className="px-1 pb-2 text-meta text-danger" role="alert">
            {error}
          </p>
        ) : null}

        {playUrl && playing ? (
          <div className="mb-2 overflow-hidden rounded-control border border-border bg-black">
            <video
              key={playUrl}
              src={playUrl}
              controls
              autoPlay
              className="block max-h-[220px] w-full bg-black"
              data-testid="vizzy-render-video"
            />
            <div className="flex items-center justify-between gap-2 border-t border-border bg-surface-1 px-2 py-1">
              <span className="truncate text-caption text-text-muted">{playing}</span>
              <Button variant="ghost" onClick={() => onReveal(playing)}>
                Open
              </Button>
            </div>
          </div>
        ) : null}

        {items.length === 0 && !loading ? (
          <p className="px-1 py-6 text-center text-body-sm text-text-muted">
            No renders yet. Export a project to see it here.
          </p>
        ) : null}

        {items.map((item) => {
          const isConfirming = confirming === item.name;
          const busy = busyName === item.name;
          return (
            <div
              key={item.name}
              className="mb-1 rounded-control border border-transparent px-2 py-1.5 hover:border-border hover:bg-surface-2"
              data-testid="vizzy-render-row"
              data-name={item.name}
            >
              <div className="flex items-center gap-2">
                <Icon
                  name={playing === item.name ? "fa-pause" : "fa-play"}
                  size={11}
                  className="text-text-muted"
                />
                <button
                  type="button"
                  className="min-w-0 flex-1 truncate text-left text-body-sm text-text-primary hover:text-accent"
                  title={item.name}
                  onClick={() => void play(item.name)}
                  data-testid="vizzy-render-play"
                >
                  {item.name}
                </button>
              </div>
              <div className="mt-0.5 flex items-center gap-2 pl-[19px]">
                <span className="text-caption text-text-muted">
                  {formatBytes(item.bytes)} · {formatRenderDate(item.mtimeMs)}
                </span>
                <div className="ml-auto flex items-center gap-1">
                  <button
                    type="button"
                    className="rounded-[6px] px-1.5 text-caption text-text-muted hover:bg-surface-hover hover:text-text-primary"
                    onClick={() => onReveal(item.name)}
                    data-testid="vizzy-render-reveal"
                  >
                    Reveal
                  </button>
                  <button
                    type="button"
                    className="rounded-[6px] px-1.5 text-caption text-text-muted hover:bg-danger-soft hover:text-danger"
                    onClick={() => setConfirming(isConfirming ? null : item.name)}
                    disabled={busy}
                    data-testid="vizzy-render-delete"
                  >
                    Delete
                  </button>
                </div>
              </div>
              {isConfirming ? (
                <div
                  className="mt-1.5 flex items-center gap-2 rounded-control bg-danger-soft px-2 py-1.5"
                  data-testid="vizzy-render-confirm"
                >
                  <span className="text-caption text-text-primary">Delete this render?</span>
                  <div className="ml-auto flex items-center gap-1">
                    <Button
                      variant="danger"
                      className="h-7 px-2"
                      loading={busy}
                      onClick={() => void remove(item.name)}
                      data-testid="vizzy-render-delete-confirm"
                    >
                      Delete
                    </Button>
                    <Button
                      variant="ghost"
                      className="h-7 px-2"
                      onClick={() => setConfirming(null)}
                      disabled={busy}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="shrink-0 border-t border-border px-3 py-2 text-caption text-text-muted">
        Files in the Camxora renders folder. Delete removes the file from disk.
      </div>
    </div>
  );
}
