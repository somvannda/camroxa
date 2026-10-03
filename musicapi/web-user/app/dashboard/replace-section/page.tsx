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
  const [lyrics, setLyrics] = useState("");
  const [vocalGender, setVocalGender] = useState<"m" | "f">("m");
  const [styleWeight, setStyleWeight] = useState("0.65");
  const [audioWeight, setAudioWeight] = useState("0.65");
  const [weirdnessConstraint, setWeirdnessConstraint] = useState("0.65");
  const [personaId, setPersonaId] = useState("");
  const [personaModel, setPersonaModel] = useState<"style_persona" | "voice_persona">("style_persona");

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
            lyrics: lyrics || undefined,
            vocalGender,
            styleWeight: styleWeight === "" ? undefined : Number(styleWeight),
            audioWeight: audioWeight === "" ? undefined : Number(audioWeight),
            weirdnessConstraint: weirdnessConstraint === "" ? undefined : Number(weirdnessConstraint),
            personaId: personaId || undefined,
            personaModel: personaId ? personaModel : undefined,
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

        <Field label="prompt" required help="Lyrics for the replaced segment. If lyrics is also provided, lyrics takes priority.">
          <textarea
            className={textareaCls}
            rows={3}
            placeholder="A calm and relaxing piano track."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
        </Field>

        <Field label="lyrics" help="Optional lyrics for the replaced segment only. Max 5000 characters for V6 models.">
          <textarea
            className={textareaCls}
            rows={3}
            placeholder="Optional — takes priority over prompt"
            value={lyrics}
            onChange={(e) => setLyrics(e.target.value.slice(0, 5000))}
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
                Duration must be at least 10 seconds
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

        <Field label="fullLyrics" required help="Complete lyrics of the whole song after modification">
          <textarea
            className={textareaCls}
            rows={6}
            placeholder={`[Verse 1]\nOriginal lyrics here\n\n[Chorus]\nModified lyrics for this section\n\n[Verse 2]\nMore original lyrics`}
            value={fullLyrics}
            onChange={(e) => setFullLyrics(e.target.value)}
          />
        </Field>

        <div className="grid gap-5 md:grid-cols-2">
          <Field label="vocalGender" help="Preferred vocal gender">
            <select
              className={inputCls}
              value={vocalGender}
              onChange={(e) => setVocalGender(e.target.value as "m" | "f")}
            >
              <option value="m" className="bg-[#141416]">Male</option>
              <option value="f" className="bg-[#141416]">Female</option>
            </select>
          </Field>
          <Field label="styleWeight" help="Style adherence weight, range 0–1">
            <input type="number" min="0" max="1" step="0.05" className={inputCls} value={styleWeight} onChange={(e) => setStyleWeight(e.target.value)} />
          </Field>
          <Field label="audioWeight" help="Audio consistency weight versus other controls, range 0–1">
            <input type="number" min="0" max="1" step="0.05" className={inputCls} value={audioWeight} onChange={(e) => setAudioWeight(e.target.value)} />
          </Field>
          <Field label="weirdnessConstraint" help="Creativity/novelty constraint, range 0–1">
            <input type="number" min="0" max="1" step="0.05" className={inputCls} value={weirdnessConstraint} onChange={(e) => setWeirdnessConstraint(e.target.value)} />
          </Field>
          <Field label="personaId" help="Persona ID or Voice ID to apply. When using a Voice ID, set personaModel to voice_persona.">
            <input className={inputCls} placeholder="Optional" value={personaId} onChange={(e) => setPersonaId(e.target.value)} />
          </Field>
          {personaId && (
            <Field label="personaModel" help="style_persona for Generate Persona IDs; voice_persona for Suno Voice IDs">
              <select
                className={inputCls}
                value={personaModel}
                onChange={(e) => setPersonaModel(e.target.value as "style_persona" | "voice_persona")}
              >
                <option value="style_persona" className="bg-[#141416]">style_persona</option>
                <option value="voice_persona" className="bg-[#141416]">voice_persona</option>
              </select>
            </Field>
          )}
        </div>

        <PrimaryButton type="submit" busy={busy} disabled={!canRun}>
          Replace Section
        </PrimaryButton>
      </form>
    </PageShell>
  );
}
