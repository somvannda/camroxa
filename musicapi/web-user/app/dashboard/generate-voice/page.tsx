"use client";

import {
  Field,
  PageShell,
  PrimaryButton,
  inputCls,
  textareaCls,
  useJob,
} from "@/components/playground";
import { apiFetch } from "@/lib/api";
import { useCallback, useEffect, useState } from "react";

const SKILL_LEVELS = [
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
  { value: "professional", label: "Professional" },
] as const;

type TaskBundle = {
  taskId?: string;
  audioUrl?: string;
};

const emptyBundle = (): TaskBundle => ({});

const ENDPOINTS = {
  phrase: "voice_phrase",
  record: "voice_record",
  generate: "voice_generate",
} as const;

export default function GenerateVoicePage() {
  const [taskId, setTaskId] = useState("");
  const [voiceName, setVoiceName] = useState("My Voice");
  const [style, setStyle] = useState("Pop, Female Vocal");
  const [singerSkillLevel, setSingerSkillLevel] = useState("beginner");
  const [description, setDescription] = useState("created from uploaded voice");

  const [source, setSource] = useState<TaskBundle>(emptyBundle());
  const [validationPhrase, setValidationPhrase] = useState<TaskBundle & { phrase?: string }>({});
  const [validationAudio, setValidationAudio] = useState<TaskBundle>(emptyBundle());
  const [selectBusy, setSelectBusy] = useState(false);
  const [selectError, setSelectError] = useState("");

  // Real per-endpoint costs, read from the live pricing table so the buttons can
  // show what they will spend before the user clicks them.
  const [costs, setCosts] = useState<Record<string, number>>({});
  useEffect(() => {
    apiFetch<{ pricing: Array<{ endpoint: string; model: string | null; credit_cost: number }> }>("/pricing")
      .then((p) => {
        const map: Record<string, number> = {};
        for (const row of p.pricing) {
          if (row.model === null && row.endpoint in ENDPOINTS) map[row.endpoint] = row.credit_cost;
        }
        setCosts(map);
      })
      .catch(() => { /* costs are advisory; leave them unshown if unavailable */ });
  }, []);

  const selectCost = (costs[ENDPOINTS.phrase] ?? 0) + (costs[ENDPOINTS.record] ?? 0);
  const generateCost = costs[ENDPOINTS.generate] ?? 0;

  const main = useJob();

  const openSelect = useCallback(async () => {
    setSelectBusy(true);
    setSelectError("");
    try {
      const phr0 = await apiFetch<{ job_id: string }>("/me/voice-phrase", {
        method: "POST",
        body: JSON.stringify({ prompt: "" }),
      });
      if (phr0.job_id) setValidationPhrase({ taskId: phr0.job_id });

      const rec = await apiFetch<{ job_id: string }>("/me/voice-record", {
        method: "POST",
        body: JSON.stringify({ extension: "wav" }),
      });
      if (rec.job_id) {
        setSource({ taskId: rec.job_id });
        setValidationAudio({ taskId: rec.job_id });
      }
    } catch (e) {
      // Surface the failure instead of swallowing it: the phrase/record calls
      // charge credits, so a silent error would leave the user paid but stuck.
      setSelectError(e instanceof Error ? e.message : "Failed to start the source tasks.");
    } finally {
      setSelectBusy(false);
    }
  }, []);

  const canRun =
    !main.busy &&
    (taskId || (source.taskId && validationAudio.taskId)) &&
    voiceName.trim().length > 0;

  return (
    <PageShell
      title="Generate Voice"
      subtitle="Create a custom voice from a source audio sample."
      cardTitle="Generate Voice"
      cardSubtitle="Prepare the source and validation audio in the popup, then finish the self-built voice generation here."
      error={selectError || main.error}
      output={
        <VoiceOverview
          main={main}
          source={source}
          validationPhrase={validationPhrase}
          validationAudio={validationAudio}
        />
      }
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!canRun) return;
          main.reset();
          const finalTaskId = taskId || source.taskId || validationAudio.taskId || "";
          main.submit("/me/voice-generate", {
            taskId: finalTaskId,
            voiceName,
            style,
            singerSkillLevel,
            description,
          });
        }}
        className="space-y-5"
      >
        <div>
          <button
            type="button"
            onClick={openSelect}
            disabled={selectBusy}
            className="rounded-md border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10 disabled:opacity-60"
          >
            {selectBusy ? "Initializing…" : selectCost > 0 ? `Select Audio (${selectCost} credits)` : "Select Audio"}
          </button>
          <p className="mt-1.5 text-xs text-white/40">
            Start phrase + recording tasks via popup (initializes source + validation placeholders).
            {selectCost > 0 && ` This spends ${selectCost} credits.`}
          </p>
        </div>

        <Field label="taskId">
          <div>
            <div className="relative">
              <input
                className={`${inputCls} pr-10`}
                placeholder="Not created yet"
                value={taskId}
                onChange={(e) => setTaskId(e.target.value)}
              />
              <button
                type="button"
                onClick={() => { void navigator.clipboard.writeText(taskId).catch(() => {}); }}
                disabled={!taskId}
                aria-label="Copy taskId"
                title="Copy taskId"
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-white/40 transition hover:bg-white/5 hover:text-white disabled:opacity-30"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
                  <rect x="9" y="9" width="13" height="13" rx="2" />
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                </svg>
              </button>
            </div>
            {!taskId && (
              <div className="mt-2 rounded-md border border-white/5 bg-black/20 px-3 py-2 text-xs text-white/55 font-mono break-all">
                {source.taskId || "Not created yet"}
              </div>
            )}
          </div>
        </Field>

        <div className="grid gap-5 md:grid-cols-2">
          <Field label="voiceName">
            <input
              className={inputCls}
              placeholder="My Voice"
              value={voiceName}
              onChange={(e) => setVoiceName(e.target.value)}
            />
          </Field>
          <Field label="style">
            <input
              className={inputCls}
              placeholder="Pop, Female Vocal"
              value={style}
              onChange={(e) => setStyle(e.target.value)}
            />
          </Field>
        </div>

        <Field label="singerSkillLevel">
          <div className="relative">
            <select
              className={`${inputCls} appearance-none pr-9`}
              value={singerSkillLevel}
              onChange={(e) => setSingerSkillLevel(e.target.value)}
            >
              {SKILL_LEVELS.map((s) => (
                <option key={s.value} value={s.value} className="bg-[#0e0e10] text-white">
                  {s.label}
                </option>
              ))}
            </select>
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </div>
        </Field>

        <Field label="description">
          <textarea
            className={textareaCls}
            rows={2}
            placeholder="created from uploaded voice"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>

        <PrimaryButton type="submit" busy={main.busy} disabled={!canRun}>
          {generateCost > 0 ? `Generate Voice (${generateCost} credits)` : "Generate Voice"}
        </PrimaryButton>
      </form>
    </PageShell>
  );
}

function VoiceOverview(props: {
  main: ReturnType<typeof useJob>;
  source: TaskBundle;
  validationPhrase: TaskBundle & { phrase?: string };
  validationAudio: TaskBundle;
}) {
  const { main, source, validationPhrase, validationAudio } = props;
  const [tab, setTab] = useState<"overview" | "json">("overview");
  const terminal = main.task && (main.task.status === "complete" || main.task.status === "error");
  const res = (main.task?.result as Record<string, unknown> | undefined) || {};
  const personaId = (res.personaId || res.persona_id || res.id) as string | undefined;

  return (
    <section className="rounded-2xl border border-white/5 bg-white/[0.02]">
      <div className="flex items-center justify-between border-b border-white/5 px-5 py-3">
        <h3 className="text-sm font-semibold text-white/80">Output</h3>
        <div className="flex items-center gap-1 rounded-lg bg-black/30 p-0.5">
          {(["overview", "json"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-md px-3 py-1 text-xs font-medium capitalize transition ${
                tab === t ? "bg-white/10 text-white" : "text-white/50 hover:text-white/80"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
      <div className="p-5">
        {tab === "overview" ? (
          <div className="space-y-5">
            <Kv title="Source Audio" value={source.taskId || source.audioUrl || null}>
              The source clip will appear after the popup finishes.
            </Kv>
            <Kv
              title="Validation Phrase"
              value={validationPhrase.phrase || validationPhrase.taskId || null}
            >
              The validation phrase will appear here after the popup starts the task.
            </Kv>
            <Kv title="Validation Audio" value={validationAudio.taskId || validationAudio.audioUrl || null}>
              The validation clip will appear here after the popup completes.
            </Kv>

            <div className="rounded-xl border border-white/5 bg-black/20 p-4">
              <div className="text-sm font-semibold text-white mb-2">Voice Result</div>
              <div className="grid gap-2 text-sm">
                <div className="flex gap-2 items-baseline">
                  <span className="text-white/40 min-w-[72px]">taskId:</span>
                  <code className="text-white/80 break-all font-mono text-xs">
                    {main.task?.job_id || "Not created yet"}
                  </code>
                </div>
                <div className="flex gap-2 items-baseline">
                  <span className="text-white/40 min-w-[72px]">voiceId:</span>
                  <span className="text-white/80 break-all font-mono text-xs">
                    {main.busy
                      ? "Pending…"
                      : terminal
                        ? personaId || "Not ready yet"
                        : "Not ready yet"}
                  </span>
                </div>
                {main.busy && !terminal && (
                  <div>
                    <div className="mt-2 h-1.5 w-full max-w-md overflow-hidden rounded-full bg-white/5">
                      <div className="h-full w-1/3 animate-[shimmer_1.4s_infinite] rounded-full bg-gradient-to-r from-transparent via-white/20 to-transparent" />
                    </div>
                    <p className="mt-1 text-xs text-white/50">Running… {main.task?.status}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          <pre className="max-h-[520px] overflow-auto rounded-lg bg-black/40 p-4 text-xs leading-relaxed text-white/80">
{JSON.stringify(
  main.task || { status: "not run", source, validationPhrase, validationAudio },
  null,
  2,
)}
          </pre>
        )}
      </div>
    </section>
  );
}

function Kv(props: { title: string; value: string | null | undefined; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/5 bg-black/20 p-4">
      <div className="text-sm font-semibold text-white">{props.title}</div>
      <p className="mt-1 text-xs text-white/50">{props.children}</p>
      <div className="mt-3 text-sm text-white/85 break-all">
        {props.value ? (
          <code className="font-mono text-xs text-white/75">{props.value}</code>
        ) : (
          <span className="text-white/35">—</span>
        )}
      </div>
    </div>
  );
}
