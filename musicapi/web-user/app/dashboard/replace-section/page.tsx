"use client";

import {
  Field,
  OutputTabs,
  PageShell,
  PrimaryButton,
  Switch,
  inputCls,
  textareaCls,
  useJob,
} from "@/components/playground";
import { useState } from "react";

export default function ReplaceSectionPage() {
  const [useCustomAudio, setUseCustomAudio] = useState(false);
  const [taskId, setTaskId] = useState("");
  const [audioId, setAudioId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [tags, setTags] = useState("");
  const [title, setTitle] = useState("");
  const [infillStartS, setInfillStartS] = useState("0");
  const [infillEndS, setInfillEndS] = useState("10");
  const [negativeTags, setNegativeTags] = useState("");
  const [fullLyrics, setFullLyrics] = useState("");

  const { busy, task, error, submit, reset, retry, canRetry, retryCost } = useJob({ endpoint: "replace_section" });

  const start = Number(infillStartS);
  const end = Number(infillEndS);
  const durationOk = Number.isFinite(start) && Number.isFinite(end) && end - start >= 10;
  const canRun =
    !busy &&
    (useCustomAudio ? !!audioId.trim() : !!taskId.trim()) &&
    prompt.trim() &&
    tags.trim() &&
    title.trim() &&
    durationOk &&
    fullLyrics.trim();

  return (
    <PageShell
      title="Replace Section"
      subtitle="Replace a section of generated music with new content."
      cardTitle="Replace Section"
      cardSubtitle="Replace a section of generated music with new content."
      error={error}
      output={
        <OutputTabs
          task={task}
          busy={busy}
          readyTitle="Ready to replace"
          readyBody="Fill in the form and click Run to replace a section of generated music."
          kind="clips"
          retry={retry}
          canRetry={canRetry}
          retryCost={retryCost}
          onReset={reset}
        />
      }
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!canRun) return;
          reset();
          submit("/me/replace-section", {
            useCustomAudio,
            taskId,
            audioId,
            prompt,
            tags,
            title,
            infillStartS: start,
            infillEndS: end,
            negativeTags: negativeTags || undefined,
            fullLyrics,
          });
        }}
        className="space-y-5"
      >
        <div className="flex items-center justify-between rounded-xl border border-white/5 bg-black/20 px-4 py-3">
          <div>
            <div className="text-sm font-medium text-white">Use uploaded custom audio</div>
          </div>
          <Switch checked={useCustomAudio} onChange={setUseCustomAudio} />
        </div>

        <div className="grid gap-5 md:grid-cols-2">
          {!useCustomAudio && (
            <Field label="taskId" required help="Original music task ID">
              <input
                className={inputCls}
                placeholder="Enter music generation task ID"
                value={taskId}
                onChange={(e) => setTaskId(e.target.value)}
              />
            </Field>
          )}
          <Field label="audioId" required help="Audio ID to replace">
            <input
              className={inputCls}
              placeholder="Enter audio ID"
              value={audioId}
              onChange={(e) => setAudioId(e.target.value)}
            />
          </Field>
        </div>

        <Field label="prompt" required help="Prompt describing the replacement segment content">
          <input
            className={inputCls}
            placeholder="A calm and relaxing piano track."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
        </Field>

        <div className="grid gap-5 md:grid-cols-2">
          <Field label="tags" required help="Music style tags">
            <input
              className={inputCls}
              placeholder="Jazz"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
            />
          </Field>
          <Field label="title" required>
            <input
              className={inputCls}
              placeholder="Relaxing Piano"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </Field>
        </div>

        <div className="grid gap-5 md:grid-cols-2">
          <Field label="infillStartS" required help="Start time (seconds)">
            <input
              type="number"
              step="0.01"
              className={inputCls}
              value={infillStartS}
              onChange={(e) => setInfillStartS(e.target.value)}
            />
          </Field>
          <Field label="infillEndS" required help="End time (seconds)">
            <div>
              <input
                type="number"
                step="0.01"
                className={`${inputCls} ${!durationOk ? "border-red-500/40" : ""}`}
                value={infillEndS}
                onChange={(e) => setInfillEndS(e.target.value)}
              />
              <p className={`mt-1.5 text-xs ${!durationOk ? "text-red-300" : "text-white/40"}`}>
                {!durationOk ? "Duration must be at least 10 seconds" : "Duration must be at least 10 seconds"}
              </p>
            </div>
          </Field>
        </div>

        <Field label="negativeTags" help="Music styles to exclude (optional)">
          <input
            className={inputCls}
            placeholder="Rock"
            value={negativeTags}
            onChange={(e) => setNegativeTags(e.target.value)}
          />
        </Field>

        <Field label="fullLyrics" required help="Complete lyrics after modification">
          <textarea
            className={textareaCls}
            rows={6}
            placeholder={`[Verse 1]\nOriginal lyrics here\n\n[Chorus]\nModified lyrics for this section\n\n[Verse 2]\nMore original lyrics`}
            value={fullLyrics}
            onChange={(e) => setFullLyrics(e.target.value)}
          />
        </Field>

        <PrimaryButton type="submit" busy={busy} disabled={!canRun}>
          Replace Section
        </PrimaryButton>
      </form>
    </PageShell>
  );
}
