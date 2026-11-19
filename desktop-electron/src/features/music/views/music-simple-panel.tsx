import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "../../../components/status";
import { Button } from "../../../components/button";
import { Card } from "../../../components/card";
import { toast } from "../../../components/toast";
import { apiRequest, errorMessage } from "../../../lib/api";
import {
  SIMPLE_MODELS,
  formatDuration,
  generationIsFailed,
  generationIsReady,
  generationStatusLabel,
  type SimpleClip,
  type SimpleGenerateResponse,
  type SimpleGeneration,
  type SimpleGenerationList,
  type SimpleModel,
  type SimpleQuota,
} from "../simple-mode";

const POLL_INTERVAL_MS = 3_000;
const POLL_LIMIT = 60;

function statusTone(generation: SimpleGeneration): "neutral" | "success" | "warning" | "danger" {
  if (generationIsReady(generation)) return "success";
  if (generationIsFailed(generation)) return "danger";
  if (generation.status.toLowerCase().includes("queue")) return "neutral";
  return "warning";
}

function ClipRow({
  clip,
  generation,
  onSave,
  busy,
}: {
  clip: SimpleClip;
  generation: SimpleGeneration;
  onSave: (clip: SimpleClip, format: "mp3" | "wav") => void;
  busy: boolean;
}) {
  const ready = clip.ready || generationIsReady(generation);
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-control border border-border px-3 py-2">
      <div className="min-w-0">
        <p className="truncate text-body text-text-primary">
          {clip.label || (clip.variant === "alt" ? "Alternate" : "Primary")}
          {clip.title ? ` · ${clip.title}` : ""}
        </p>
        <p className="text-caption text-text-muted">
          {ready
            ? formatDuration(clip.duration_seconds) || "Audio ready"
            : "Waiting for Suno to finish this clip"}
          {clip.is_preview && clip.preview_seconds ? ` · ${clip.preview_seconds}s preview` : ""}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Button
          variant="secondary"
          disabled={!ready || busy}
          onClick={() => onSave(clip, "mp3")}
        >
          Save MP3
        </Button>
        <Button variant="ghost" disabled={!ready || busy} onClick={() => onSave(clip, "wav")}>
          WAV
        </Button>
      </div>
    </div>
  );
}

export function MusicSimplePanel() {
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState<SimpleModel>("V6");
  const [instrumental, setInstrumental] = useState(false);
  const [quota, setQuota] = useState<SimpleQuota | null>(null);
  const [generation, setGeneration] = useState<SimpleGeneration | null>(null);
  const [history, setHistory] = useState<SimpleGeneration[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [savingKey, setSavingKey] = useState("");
  const [audio, setAudio] = useState<{ url: string; title: string } | null>(null);
  const [savedPath, setSavedPath] = useState("");
  const pollAttempts = useRef(0);

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const response = await apiRequest<SimpleGenerationList>({
        method: "GET",
        path: "/web-music/generations",
        query: { limit: 10 },
      });
      setHistory(response.items ?? []);
    } catch {
      // History is secondary; a failure must not block the composer.
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  const loadQuota = useCallback(async () => {
    try {
      setQuota(await apiRequest<SimpleQuota>({ method: "GET", path: "/web-music/quota" }));
    } catch {
      setQuota(null);
    }
  }, []);

  useEffect(() => {
    void loadHistory();
    void loadQuota();
  }, [loadHistory, loadQuota]);

  // Poll the generation the user just created until Suno reports success/failure.
  useEffect(() => {
    if (!generation) return;
    if (generationIsReady(generation) || generationIsFailed(generation)) return;
    if (pollAttempts.current >= POLL_LIMIT) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      pollAttempts.current += 1;
      try {
        const latest = await apiRequest<SimpleGeneration>({
          method: "GET",
          path: `/web-music/generations/${encodeURIComponent(generation.id)}`,
        });
        if (cancelled) return;
        setGeneration(latest);
        if (generationIsReady(latest)) {
          toast("Your song is ready.", "success");
          void loadHistory();
          void loadQuota();
        }
      } catch {
        if (cancelled) return;
        setError("Lost contact with the song queue. Retrying…");
      }
    }, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [generation, loadHistory, loadQuota]);

  const generate = async () => {
    const value = prompt.trim();
    if (value.length < 3) {
      setError("Describe the song you want in at least a few words.");
      return;
    }
    setSubmitting(true);
    setError("");
    setAudio(null);
    setSavedPath("");
    pollAttempts.current = 0;
    try {
      const response = await apiRequest<SimpleGenerateResponse>({
        method: "POST",
        path: "/web-music/generate",
        body: {
          mode: "simple",
          prompt: value,
          model,
          instrumental,
        },
      });
      setQuota(response.quota);
      setGeneration({
        id: response.task_id,
        title: response.title,
        lyrics: "",
        style: response.style,
        model: response.model ?? model,
        model_label: response.model_label ?? model,
        instrumental,
        status: response.status,
        clips: [],
      });
      toast("Song queued. Suno is writing the title and lyrics.", "success");
    } catch (cause) {
      const message = errorMessage(cause);
      setError(
        /402|credit|quota|upgrade/i.test(message)
          ? `${message} Top up in the Camxora web app, then try again.`
          : message || "Unable to start the song.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const openGeneration = (item: SimpleGeneration) => {
    setGeneration(item);
    setError("");
    setAudio(null);
    setSavedPath("");
    pollAttempts.current = 0;
  };

  const saveClip = async (clip: SimpleClip, format: "mp3" | "wav") => {
    if (!generation) return;
    const key = `${clip.variant}:${format}`;
    setSavingKey(key);
    setError("");
    try {
      const result = await window.camxora.webmusic.saveClip({
        taskId: generation.id,
        variant: clip.variant === "alt" ? "alt" : "ok",
        title: generation.title,
        format,
      });
      if (!result.ok) {
        setError(result.error.message || "Unable to save this clip.");
        return;
      }
      setSavedPath(result.data.path);
      if (format === "mp3") setAudio({ url: result.data.url, title: generation.title });
      toast(format === "wav" ? "WAV saved." : "MP3 saved and ready to play.", "success");
    } catch (cause) {
      setError(errorMessage(cause) || "Unable to save this clip.");
    } finally {
      setSavingKey("");
    }
  };

  const currentClips = generation?.clips ?? [];
  const canGenerate = !submitting && prompt.trim().length >= 3;

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]" data-testid="music-simple">
      <Card className="p-5">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-title font-semibold text-text-primary">Simple song</h2>
          {quota ? (
            <p className="text-meta text-text-muted">
              {quota.credits_per_song} credits per song · {quota.credits_remaining} credits left
            </p>
          ) : null}
        </div>
        <p className="mt-1 text-meta text-text-secondary">
          Write a short brief. Suno writes the title, lyrics and style; the Camxora library is not
          used.
        </p>

        {error ? (
          <p className="mt-3 rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-meta text-danger" role="alert">
            {error}
          </p>
        ) : null}

        <label className="mt-4 flex flex-col gap-1">
          <span className="text-caption text-text-muted">What should the song be about?</span>
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            rows={5}
            maxLength={5000}
            data-testid="music-simple-prompt"
            placeholder="A warm night-drive bass song about missing the coast, male vocal, mid-tempo."
            className="w-full resize-y rounded-control border border-border bg-surface-1 px-3 py-2 text-body text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
          />
        </label>

        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-caption text-text-muted">Model</span>
            <select
              value={model}
              onChange={(event) => setModel(event.target.value as SimpleModel)}
              className="h-8 rounded-control border border-border bg-surface-1 px-2 text-body text-text-primary focus:border-accent focus:outline-none"
            >
              {SIMPLE_MODELS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex h-8 items-center gap-2 text-body text-text-secondary">
            <input
              type="checkbox"
              checked={instrumental}
              onChange={(event) => setInstrumental(event.target.checked)}
              className="h-4 w-4 accent-accent"
            />
            Instrumental
          </label>
          <Button
            className="ml-auto"
            onClick={() => void generate()}
            loading={submitting}
            disabled={!canGenerate}
            data-testid="music-simple-generate"
          >
            Generate with Suno
          </Button>
        </div>

        {generation ? (
          <div className="mt-5 border-t border-border pt-4" data-testid="music-simple-result">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-title font-semibold text-text-primary">
                  {generation.title || "Untitled"}
                </p>
                <p className="text-meta text-text-muted">
                  {generation.model_label || generation.model}
                  {generation.style ? ` · ${generation.style}` : ""}
                </p>
              </div>
              <Badge tone={statusTone(generation)}>{generationStatusLabel(generation)}</Badge>
            </div>

            {generationIsFailed(generation) ? (
              <p className="mt-2 text-meta text-danger">
                {generation.error_message || "Suno could not finish this song."}
              </p>
            ) : null}

            {currentClips.length > 0 ? (
              <div className="mt-3 space-y-2">
                {currentClips.map((clip) => (
                  <ClipRow
                    key={clip.variant}
                    clip={clip}
                    generation={generation}
                    onSave={(item, format) => void saveClip(item, format)}
                    busy={Boolean(savingKey)}
                  />
                ))}
              </div>
            ) : (
              <p className="mt-2 text-meta text-text-secondary">
                {generationIsFailed(generation)
                  ? "No clips were produced."
                  : "Suno is writing and rendering the song. The clips appear here automatically."}
              </p>
            )}

            {audio ? (
              <div className="mt-3 rounded-control border border-border bg-surface-1 px-3 py-2">
                <p className="truncate text-meta text-text-secondary">{audio.title}</p>
                <audio key={audio.url} controls autoPlay src={audio.url} className="mt-2 w-full" />
              </div>
            ) : null}

            {savedPath ? (
              <div className="mt-3 flex items-center justify-between gap-2">
                <p className="truncate text-caption text-text-muted" title={savedPath}>
                  Saved to {savedPath}
                </p>
                <Button variant="ghost" onClick={() => void window.camxora.files.reveal(savedPath)}>
                  Show in folder
                </Button>
              </div>
            ) : null}

            {generation.lyrics ? (
              <details className="mt-3">
                <summary className="cursor-pointer text-meta text-text-secondary">
                  Lyrics written by Suno
                </summary>
                <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap rounded-control border border-border bg-surface-1 p-3 text-meta text-text-primary">
                  {generation.lyrics}
                </pre>
              </details>
            ) : null}
          </div>
        ) : null}
      </Card>

      <Card className="p-5">
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="text-title font-semibold text-text-primary">Recent simple songs</h2>
          <Button variant="ghost" onClick={() => void loadHistory()} disabled={loadingHistory}>
            Refresh
          </Button>
        </div>
        {history.length === 0 ? (
          <p className="mt-3 text-meta text-text-secondary">
            {loadingHistory ? "Loading…" : "Nothing yet. Your simple songs appear here."}
          </p>
        ) : (
          <ul className="mt-3 divide-y divide-border">
            {history.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => openGeneration(item)}
                  className={`flex w-full items-center justify-between gap-2 px-1 py-2 text-left transition-colors hover:bg-surface-hover ${
                    generation?.id === item.id ? "bg-accent-soft" : ""
                  }`}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-body text-text-primary">
                      {item.title || "Untitled"}
                    </span>
                    <span className="block truncate text-caption text-text-muted">
                      {item.model_label || item.model}
                      {item.created_at ? ` · ${new Date(item.created_at).toLocaleString()}` : ""}
                    </span>
                  </span>
                  <Badge tone={statusTone(item)}>{generationStatusLabel(item)}</Badge>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
