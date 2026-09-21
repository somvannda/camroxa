"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

interface Endpoint {
  method: string;
  path: string;
  desc: string;
  params?: { name: string; required: boolean; desc: string }[];
  example?: string;
}

const MODELS: Array<{ label: string; key: string; tagline: string }> = [
  { label: "V4", key: "chirp-v4", tagline: "Improved Vocals — Best audio quality with refined song structure, up to 4 minutes" },
  { label: "V4_5", key: "chirp-auk", tagline: "Smart Prompts — Superior genre blending with smarter prompts, up to 8 minutes" },
  { label: "V4_5PLUS", key: "chirp-bluejay", tagline: "Richer Tones — Enhanced musicality with new creative approaches, up to 8 minutes" },
  { label: "V4_5ALL", key: "chirp-auk-turbo", tagline: "Better Song Structure — V4.5-all is better song structure, max 8 min" },
  { label: "V5", key: "chirp-crow", tagline: "Latest Model — Cutting-edge model with enhanced quality and capabilities" },
  { label: "V5_5", key: "chirp-fenix", tagline: "Voice-Customized Model — Unleash Your Voice: Custom Models Tailored to Your Unique Taste" },
];

type GroupKey = "music" | "lyrics" | "audio" | "video" | "upload" | "voice" | "detail" | "utility";

interface SectionGroup {
  key: GroupKey;
  title: string;
  icon: string;
  tagline: string;
}

const GROUPS: SectionGroup[] = [
  { key: "music", title: "Music Generation APIs", icon: "🎵", tagline: "Generate, extend, cover, mashup, and refine songs" },
  { key: "lyrics", title: "Lyrics Creation APIs", icon: "✍️", tagline: "Write lyrics and retrieve timestamped lines" },
  { key: "audio", title: "Audio Processing APIs", icon: "🔊", tagline: "Separate stems, boost, convert to WAV, recovery, MIDI" },
  { key: "video", title: "Music Video APIs", icon: "🎬", tagline: "Generate MP4 music videos for your clips" },
  { key: "upload", title: "Upload Workflow APIs", icon: "📤", tagline: "3-step upload flow for custom audio input" },
  { key: "voice", title: "Suno Voice APIs", icon: "🎙", tagline: "6 operations: phrase → validate → record → generate → apply → extend" },
  { key: "detail", title: "Asset Detail APIs", icon: "📄", tagline: "Per-asset GET endpoints: m4a/image/wav/stems/video/cover/subtitle/recovery/mp4/midi" },
  { key: "utility", title: "Utility APIs", icon: "🛠️", tagline: "Credits, task status, sunoapi.org aliases" },
];

function groupOf(e: Endpoint): GroupKey {
  let p = e.path;
  if (p.startsWith("/api/v1/")) p = "/v1/" + p.slice("/api/v1/".length);
  if (p.startsWith("/v1/get-credits")) return "utility";
  if (p.startsWith("/v1/generate/record-info")) return "utility";
  if (p === "/v1/generate" || p.startsWith("/v1/generate?")) return "music";
  if (p.startsWith("/v1/generate/extend")) return "music";
  if (p.startsWith("/v1/vocal-removal/generate")) return "audio";
  if (p.startsWith("/v1/lyrics")) return "lyrics";
  if (p.startsWith("/v1/upload")) return "upload";
  if (p.startsWith("/v1/voice")) return "voice";
  if (p.startsWith("/v1/persona")) return "voice";
  if (p.startsWith("/v1/clip/")) return "detail";
  if (p.startsWith("/v1/mp4/")) return p.endsWith("/:id") ? "detail" : "video";
  if (p === "/v1/credits" || p.startsWith("/v1/task")) return "utility";
  if (p.startsWith("/v1/music/wav")) return p.endsWith("/:id") ? "detail" : "audio";
  if (p.startsWith("/v1/music/stems")) return p.endsWith("/:id") ? "detail" : "audio";
  if (p.startsWith("/v1/music/video")) return p.endsWith("/:id") ? "detail" : "audio";
  if (p.startsWith("/v1/music/cover")) return p.endsWith("/:id") ? "detail" : "music";
  if (p.startsWith("/v1/music/subtitle")) return p.endsWith("/:id") ? "detail" : "audio";
  if (p.startsWith("/v1/music/recovery")) return p.endsWith("/:id") ? "detail" : "audio";
  if (p.startsWith("/v1/music/midi")) return p.endsWith("/:id") ? "detail" : "audio";
  if (p.startsWith("/v1/music")) return "music";
  if (p.startsWith("/v1/sounds")) return "music";
  if (p.startsWith("/v1/generate/boost")) return "audio";
  if (p.startsWith("/v1/generate/upload-extend")) return "music";
  if (p.startsWith("/v1/generate/upload-cover")) return "music";
  return "utility";
}

const ENDPOINTS: Endpoint[] = [
  {
    method: "GET",
    path: "/v1/credits",
    desc: "Get the remaining credits on your API key.",
    example: "curl https://musicapi.camxora.com/v1/credits \\\n  -H \"Authorization: Bearer sk_...\"",
  },
  {
    method: "GET",
    path: "/v1/task/:id",
    desc: "Poll a task's status and result.",
    example: "curl https://musicapi.camxora.com/v1/task/<job_id> \\\n  -H \"Authorization: Bearer sk_...\"\n// => { \"job_id\": \"...\", \"type\": \"music\", \"status\": \"complete\", \"result\": { ... } }",
  },
  {
    method: "GET",
    path: "/api/v1/get-credits",
    desc: "Alias of GET /v1/credits with sunoapi.org response shape ({code, msg, data.credits}).",
    example: "curl \"https://musicapi.camxora.com/api/v1/get-credits\" -H \"Authorization: Bearer sk_...\"\n// => { \"code\": 200, \"msg\": \"success\", \"data\": { \"credits\": 999, \"name\": \"...\" } }",
  },
  {
    method: "POST",
    path: "/api/v1/generate",
    desc: "Alias of POST /v1/music with sunoapi.org payload schema ({prompt, customMode, style, title, model, callBackUrl, instrumental}).",
    params: [
      { name: "prompt", required: true, desc: "Text description / lyrics for music generation" },
      { name: "customMode", required: false, desc: "Enable custom parameters mode (true/false)" },
      { name: "style", required: false, desc: "Music style / genre (required in custom mode)" },
      { name: "title", required: false, desc: "Song title (required in custom mode)" },
      { name: "instrumental", required: false, desc: "Generate instrumental only (true/false)" },
      { name: "model", required: false, desc: "Model key: V4 / V4_5 / V4_5PLUS / V4_5ALL / V5 / V5_5 or chirp-*" },
      { name: "callBackUrl", required: false, desc: "Webhook URL for completion" },
    ],
    example: "curl -X POST \"https://musicapi.camxora.com/api/v1/generate\" \\\n  -H \"Authorization: Bearer sk_...\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{ \"prompt\": \"Folk song about the sea\", \"customMode\": false, \"model\": \"V4_5ALL\" }'\n// => { \"code\": 200, \"msg\": \"success\", \"data\": { \"taskId\": \"suno_task_...\" } }",
  },
  {
    method: "POST",
    path: "/api/v1/lyrics",
    desc: "Alias of POST /v1/lyrics accepting sunoapi.org {prompt, callBackUrl} shape.",
  },
  {
    method: "POST",
    path: "/api/v1/generate/extend",
    desc: "Alias of POST /v1/music/extend with sunoapi.org {audioId, continueAt, prompt, model, callBackUrl} payload.",
    params: [
      { name: "audioId", required: true, desc: "Clip id / audio id to extend" },
      { name: "continueAt", required: false, desc: "Extension start seconds" },
      { name: "prompt", required: false, desc: "Continuation prompt" },
      { name: "model", required: false, desc: "Model key" },
      { name: "callBackUrl", required: false, desc: "Webhook URL" },
    ],
  },
  {
    method: "POST",
    path: "/api/v1/vocal-removal/generate",
    desc: "Alias of POST /v1/music/stems with sunoapi.org {taskId, audioId, callBackUrl} payload.",
    params: [
      { name: "taskId", required: false, desc: "Originating task id (optional)" },
      { name: "audioId", required: true, desc: "Clip / audio id to separate" },
      { name: "callBackUrl", required: false, desc: "Webhook URL" },
    ],
  },
  {
    method: "GET",
    path: "/api/v1/generate/record-info",
    desc: "Alias of GET /v1/task/:id with sunoapi.org query shape ?taskId= and {code,msg,data:{taskId,status,response}} response.",
    example: "curl \"https://musicapi.camxora.com/api/v1/generate/record-info?taskId=<taskId>\" -H \"Authorization: Bearer sk_...\"",
  },

  // ===== Music =====
  {
    method: "POST",
    path: "/v1/music",
    desc: "Generate music from a description.",
    params: [
      { name: "gpt_description_prompt", required: false, desc: "Style/description prompt" },
      { name: "prompt", required: false, desc: "Lyrics prompt (custom mode)" },
      { name: "title", required: false, desc: "Track title" },
      { name: "tags", required: false, desc: "Style tags" },
      { name: "negative_tags", required: false, desc: "Negative tags" },
      { name: "instrumental", required: false, desc: "Generate instrumental only (true/false)" },
      { name: "custom_mode", required: false, desc: "Enable custom mode (prompt+tags+title)" },
      { name: "model", required: false, desc: "Model version key" },
      { name: "callback_url", required: false, desc: "Webhook URL for completion" },
    ],
    example: "curl -X POST https://musicapi.camxora.com/v1/music \\\n  -H \"Authorization: Bearer sk_...\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"gpt_description_prompt\":\"Upbeat synthwave\",\"model\":\"chirp-crow\"}'\n// => { \"job_id\": \"...\", \"status\": \"pending\" }",
  },
  {
    method: "POST",
    path: "/v1/sounds",
    desc: "Generate a sound effect / audio sample (sounds mode).",
    params: [
      { name: "prompt", required: true, desc: "Sound description" },
      { name: "model", required: false, desc: "Model version key" },
      { name: "loop", required: false, desc: "Loop or one-shot (true/false)" },
      { name: "tempo", required: false, desc: "BPM (number)" },
      { name: "key", required: false, desc: "Musical key (e.g. \"C major\")" },
      { name: "callback_url", required: false, desc: "Webhook URL for completion" },
    ],
  },
  {
    method: "POST",
    path: "/v1/music/extend",
    desc: "Extend Music — Extend an existing clip.",
    params: [
      { name: "clip_id", required: true, desc: "Clip to extend" },
      { name: "continue_at", required: false, desc: "Extension start seconds (default 170)" },
      { name: "prompt", required: false, desc: "Optional continuation prompt" },
      { name: "model", required: false, desc: "Model key for the extension" },
    ],
  },
  {
    method: "POST",
    path: "/v1/music/cover",
    desc: "Cover Music — Reinterpret existing music in different styles and arrangements.",
    params: [
      { name: "clip_id", required: true, desc: "Clip to cover" },
      { name: "prompt", required: false, desc: "Style / cover description prompt" },
    ],
  },
  {
    method: "POST",
    path: "/v1/music/mashup",
    desc: "Mashup two or more clips together into a single new song.",
    params: [
      { name: "clip_ids", required: true, desc: "Array of 2+ clip IDs to mashup" },
      { name: "prompt", required: false, desc: "Optional style prompt for the mashup" },
    ],
  },
  {
    method: "POST",
    path: "/v1/music/replace-section",
    desc: "Regenerate a specific section [start_s, end_s] of a clip with new lyrics.",
    params: [
      { name: "clip_id", required: true, desc: "Clip to modify" },
      { name: "lyrics", required: true, desc: "New lyrics for the section" },
      { name: "start_s", required: true, desc: "Start second" },
      { name: "end_s", required: true, desc: "End second (must be > start_s)" },
      { name: "prompt", required: false, desc: "Optional style prompt" },
    ],
  },
  {
    method: "POST",
    path: "/v1/music/remaster",
    desc: "Remaster / upsample a clip for higher audio quality.",
    params: [{ name: "clip_id", required: true, desc: "Clip to remaster" }],
  },
  {
    method: "POST",
    path: "/v1/music/add-vocals",
    desc: "Add Vocals — Generate vocal tracks for instrumental music.",
    params: [
      { name: "clip_id", required: true, desc: "Instrumental clip to add vocals to" },
      { name: "prompt", required: false, desc: "Optional lyric prompt" },
    ],
  },
  {
    method: "POST",
    path: "/v1/music/add-instrumental",
    desc: "Add Instrumental — Create instrumental backing for existing vocal-only clip.",
    params: [
      { name: "clip_id", required: true, desc: "Vocal clip" },
      { name: "prompt", required: false, desc: "Optional style prompt" },
    ],
  },
  {
    method: "POST",
    path: "/v1/music/cover-image",
    desc: "Generate cover art for an existing clip.",
    params: [
      { name: "clip_id", required: true, desc: "Clip to generate cover art for" },
      { name: "prompt", required: true, desc: "Cover art description" },
    ],
  },
  {
    method: "POST",
    path: "/v1/generate/upload-extend",
    desc: "Upload and Extend Audio — Upload your own audio and extend it with AI-generated content.",
    params: [
      { name: "audio_url", required: false, desc: "Publicly reachable URL to the audio (required when uploaded_clip_id is not set)" },
      { name: "uploaded_clip_id", required: false, desc: "Clip ID returned by upload register endpoint" },
      { name: "prompt", required: false, desc: "Optional prompt for the continuation" },
      { name: "continue_at", required: false, desc: "Start offset seconds (default 170)" },
    ],
  },
  {
    method: "POST",
    path: "/v1/generate/upload-cover",
    desc: "Upload and Cover Audio — Transform existing audio with new styles and arrangements.",
    params: [
      { name: "audio_url", required: false, desc: "Publicly reachable URL to the audio (required when uploaded_clip_id is not set)" },
      { name: "uploaded_clip_id", required: false, desc: "Clip ID returned by upload register endpoint" },
      { name: "prompt", required: true, desc: "Style/cover prompt" },
      { name: "cover_start_s", required: false, desc: "Cover window start seconds (default 0)" },
      { name: "cover_end_s", required: false, desc: "Cover window end seconds (default 60)" },
    ],
  },

  // ===== Lyrics =====
  {
    method: "POST",
    path: "/v1/lyrics",
    desc: "Generate Lyrics — Create AI-powered lyrics for your songs.",
    params: [{ name: "prompt", required: true, desc: "Lyrics prompt / theme" }],
    example: "curl -X POST https://musicapi.camxora.com/v1/lyrics \\\n  -H \"Authorization: Bearer sk_...\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"prompt\":\"A song about summer\"}'\n// => { \"job_id\": \"...\", \"status\": \"pending\" }",
  },
  {
    method: "GET",
    path: "/v1/lyrics/:id",
    desc: "Get Timestamped Lyrics — Retrieve lyrics with precise timestamps for synchronization.",
  },

  // ===== Audio Processing =====
  {
    method: "POST",
    path: "/v1/music/stems",
    desc: "Separate Vocals from Music — Extract vocals and instrumental tracks separately using advanced AI audio separation.",
    params: [{ name: "clip_id", required: true, desc: "Clip to separate" }],
  },
  {
    method: "POST",
    path: "/v1/music/wav",
    desc: "Convert to WAV Format — Authorize signed WAV download for high-resolution WAV output.",
    params: [
      { name: "clip_id", required: true, desc: "Clip to download" },
      { name: "format", required: false, desc: "Format: wav (default) or m4a" },
    ],
  },
  {
    method: "POST",
    path: "/v1/generate/boost",
    desc: "Boost Music Style — Enhance and refine music styles with AI-powered audio processing.",
    params: [
      { name: "clip_id", required: true, desc: "Clip to restyle" },
      { name: "style_prompt", required: true, desc: "New style description" },
      { name: "start_s", required: false, desc: "Region start seconds (default 0)" },
      { name: "end_s", required: false, desc: "Region end seconds (default 60)" },
    ],
  },
  {
    method: "POST",
    path: "/v1/music/recovery",
    desc: "Generate recovery audio (clean-up / restore) for an existing clip.",
    params: [
      { name: "clip_id", required: true, desc: "Clip to recover" },
      { name: "prompt", required: false, desc: "Optional recovery description prompt" },
    ],
  },
  {
    method: "POST",
    path: "/v1/music/midi",
    desc: "Generate a MIDI / instrumental arrangement for a clip.",
    params: [
      { name: "clip_id", required: true, desc: "Clip to use as reference" },
      { name: "prompt", required: false, desc: "Optional arrangement style prompt" },
    ],
  },

  // ===== Video =====
  {
    method: "POST",
    path: "/v1/mp4/generate",
    desc: "Create Music Video — Generate visual music videos from audio tracks using AI.",
    params: [
      { name: "clip_id", required: true, desc: "Clip to produce a video for" },
      { name: "prompt", required: false, desc: "Optional music-video visual prompt" },
      { name: "quantity", required: false, desc: "Number of videos (default 1)" },
      { name: "aspect_ratio", required: false, desc: "Aspect ratio: \"16:9\" (default), \"9:16\", etc." },
    ],
    example: "curl -X POST https://musicapi.camxora.com/v1/mp4/generate \\\n  -H \"Authorization: Bearer sk_...\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"clip_id\":\"<clip_uuid>\",\"prompt\":\"neon city driving at night\",\"aspect_ratio\":\"16:9\"}'",
  },

  // ===== Upload Workflow =====
  {
    method: "POST",
    path: "/v1/upload/init",
    desc: "Step 1 — create an S3 presigned upload session (returns {id, url, fields}).",
    params: [
      { name: "extension", required: true, desc: "Audio file extension without dot: mp3, wav, m4a, etc." },
      { name: "upload_type", required: false, desc: "One of \"file_upload\" (default), \"voice_recording\", \"song_demo\"" },
      { name: "last_upload_id", required: false, desc: "Optional retry-chaining upload id" },
      { name: "callback_url", required: false, desc: "Webhook URL for completion" },
    ],
    example: "curl -X POST https://musicapi.camxora.com/v1/upload/init \\\n  -H \"Authorization: Bearer sk_...\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"extension\":\"mp3\",\"upload_type\":\"file_upload\"}'",
  },
  {
    method: "POST",
    path: "/v1/upload/register",
    desc: "Step 3 — register the completed S3 upload so Suno processes it and returns a clip_id.",
    params: [
      { name: "upload_id", required: true, desc: "UUID returned by /v1/upload/init" },
      { name: "upload_type", required: true, desc: "Same value as in init (e.g. \"file_upload\")" },
      { name: "upload_filename", required: true, desc: "Original filename of the uploaded file" },
      { name: "upload_title", required: false, desc: "Optional display title" },
      { name: "callback_url", required: false, desc: "Webhook URL for completion" },
    ],
    example: "curl -X POST https://musicapi.camxora.com/v1/upload/register \\\n  -H \"Authorization: Bearer sk_...\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"upload_id\":\"<from-init>\",\"upload_type\":\"file_upload\",\"upload_filename\":\"demo.mp3\"}'",
  },
  {
    method: "GET",
    path: "/v1/upload/status/:id",
    desc: "Step 4 — Poll processing status of a registered upload.",
  },

  // ===== Suno Voice =====
  {
    method: "POST",
    path: "/v1/persona/create",
    desc: "Create a voice persona (voice clone) from a clip with clear vocals.",
    params: [
      { name: "clip_id", required: true, desc: "Source clip (up to 60s of clear vocals)" },
      { name: "name", required: true, desc: "Persona display name" },
      { name: "styles", required: false, desc: "Optional style tags" },
    ],
  },
  {
    method: "POST",
    path: "/v1/voice/phrase",
    desc: "Suno Voice op 1 — generate a reference phrase the user can read for voice-recording validation.",
    params: [{ name: "prompt", required: true, desc: "Prompt / context for the phrase generator" }],
    example: "curl -X POST https://musicapi.camxora.com/v1/voice/phrase \\\n  -H \"Authorization: Bearer sk_...\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"prompt\":\"Create a 20 second reading phrase for voice enrollment.\"}'",
  },
  {
    method: "POST",
    path: "/v1/voice/validate",
    desc: "Suno Voice op 2 — validate a voice sample (from upload session id or public URL).",
    params: [
      { name: "upload_id", required: false, desc: "Upload id returned by /v1/voice/record (required if audio_url not set)" },
      { name: "audio_url", required: false, desc: "Public URL of voice WAV/MP3 sample (required if upload_id not set)" },
    ],
  },
  {
    method: "POST",
    path: "/v1/voice/record",
    desc: "Suno Voice op 3 — create a voice-recording upload session.",
    params: [{ name: "extension", required: true, desc: "File extension: wav, mp3, m4a" }],
  },
  {
    method: "POST",
    path: "/v1/voice/generate",
    desc: "Suno Voice op 4 — create a voice persona (clone) from a processed clip.",
    params: [
      { name: "clip_id", required: true, desc: "Up-to-60s clip with a single clear voice" },
      { name: "name", required: true, desc: "Persona display name" },
      { name: "styles", required: false, desc: "Optional style tags" },
    ],
  },
  {
    method: "POST",
    path: "/v1/voice/apply",
    desc: "Suno Voice op 5 — generate new music using a persona / voice clone.",
    params: [
      { name: "persona_id", required: false, desc: "Persona id to use" },
      { name: "prompt", required: false, desc: "Lyrics / description prompt" },
      { name: "title", required: false, desc: "Song title" },
      { name: "tags", required: false, desc: "Style tags" },
      { name: "model", required: false, desc: "Model key (chirp-*)" },
    ],
    example: "curl -X POST https://musicapi.camxora.com/v1/voice/apply \\\n  -H \"Authorization: Bearer sk_...\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"persona_id\":\"<persona_uuid>\",\"prompt\":\"A bright ballad about the sea\"}'",
  },
  {
    method: "POST",
    path: "/v1/voice/extend",
    desc: "Suno Voice op 6 — extend a song further using a persona / voice clone.",
    params: [
      { name: "persona_id", required: false, desc: "Persona id to use" },
      { name: "continue_at", required: false, desc: "Extension start seconds (default 170)" },
      { name: "prompt", required: false, desc: "Optional extension prompt" },
    ],
  },

  // ===== Asset Detail (GET) =====
  { method: "GET", path: "/v1/clip/:id", desc: "Clip detail — playback URLs (m4a, image), metadata, status." },
  { method: "GET", path: "/v1/music/wav/:id", desc: "WAV Conversion Detail — Monitor WAV format conversion tasks and download status." },
  { method: "GET", path: "/v1/music/stems/:id", desc: "Vocal Separation Detail — Check progress and access separated audio files." },
  { method: "GET", path: "/v1/music/video/:id", desc: "Music Video Detail — Track music video generation progress and retrieve download links." },
  { method: "GET", path: "/v1/music/cover/:id", desc: "Cover Detail — Monitor the status of music cover tasks and get cover results." },
  { method: "GET", path: "/v1/music/subtitle/:id", desc: "Subtitle / caption detail — SRT/VTT-format subtitles." },
  { method: "GET", path: "/v1/music/recovery/:id", desc: "Recovery audio detail — result of a recovery job." },
  { method: "GET", path: "/v1/mp4/:id", desc: "MP4 task detail — result of a music-video generation job." },
  { method: "GET", path: "/v1/music/midi/:id", desc: "MIDI detail — result of a MIDI generation job." },
];

function MethodBadge({ method }: { method: string }) {
  const color =
    method === "GET"
      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
      : method === "POST"
      ? "bg-violet-500/10 text-violet-400 border-violet-500/30"
      : "bg-white/10 text-white/80 border-white/20";
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wider ${color}`}>
      {method}
    </span>
  );
}

function slug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

interface TocItem { id: string; label: string; level: number; }

const DEFAULT_ORIGIN = "https://musicapi.camxora.com";

function applyOrigin(s: string, origin: string): string {
  return s.split(DEFAULT_ORIGIN).join(origin);
}

export default function PublicDocsPage() {
  const [toc, setToc] = useState<TocItem[]>([]);
  const [active, setActive] = useState<string>("");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [baseOrigin, setBaseOrigin] = useState<string>(DEFAULT_ORIGIN);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const host = window.location.hostname;
      if (host !== "localhost" && host !== "127.0.0.1" && host !== "0.0.0.0") {
        setBaseOrigin(window.location.origin);
      }
    }
  }, []);

  useEffect(() => {
    const headings = Array.from(document.querySelectorAll<HTMLElement>("[data-toc]"));
    const items: TocItem[] = headings.map((h) => ({
      id: h.id,
      label: h.dataset.toc || h.textContent || "",
      level: h.tagName === "H2" ? 2 : 3,
    }));
    setToc(items);

    const io = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-80px 0px -70% 0px", threshold: 0 },
    );
    headings.forEach((h) => io.observe(h));
    return () => io.disconnect();
  }, []);

  const groups = GROUPS.map((g) => ({
    ...g,
    endpoints: ENDPOINTS.filter((e) => groupOf(e) === g.key),
  })).filter((g) => g.endpoints.length > 0);

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)]">
      <header className="sticky top-0 z-50 border-b border-[var(--border)] bg-black/60 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <button
              className="mr-2 rounded-md border border-[var(--border)] p-2 md:hidden"
              onClick={() => setMobileOpen((o) => !o)}
              aria-label="Toggle menu"
            >☰</button>
            <Link href="/" className="flex items-center gap-2">
              <div className="grad-bg flex h-8 w-8 items-center justify-center rounded-lg text-sm font-bold text-white">♪</div>
              <span className="text-lg font-bold">Camxora Music API</span>
            </Link>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/" className="hidden rounded-lg px-4 py-2 text-sm font-medium text-[var(--muted)] hover:text-white sm:block">Home</Link>
            <Link href="/login" className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white">Sign in</Link>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-0 px-4 md:grid-cols-[260px_minmax(0,1fr)_240px] md:px-6">
        {/* ===== Left sidebar ===== */}
        <aside
          className={`${
            mobileOpen ? "block" : "hidden"
          } sticky top-16 h-[calc(100vh-4rem)] overflow-y-auto border-r border-[var(--border)] py-8 pr-2 md:block`}
        >
          <div className="space-y-8">
            <div>
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)]">Overview</div>
              <nav className="space-y-1">
                <a href="#welcome" className="block rounded-md px-3 py-1.5 text-sm hover:bg-white/5">Welcome</a>
                <a href="#about" className="block rounded-md px-3 py-1.5 text-sm hover:bg-white/5">About Camxora API</a>
                <a href="#key-features" className="block rounded-md px-3 py-1.5 text-sm hover:bg-white/5">Key Features</a>
                <a href="#use-cases" className="block rounded-md px-3 py-1.5 text-sm hover:bg-white/5">Use Cases</a>
              </nav>
            </div>
            <div>
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)]">Getting Started</div>
              <nav className="space-y-1">
                <a href="#getting-started" className="block rounded-md px-3 py-1.5 text-sm hover:bg-white/5">Getting Started</a>
                <a href="#api-base-url" className="block rounded-md px-3 py-1.5 text-sm hover:bg-white/5">API Base URL</a>
                <a href="#authentication" className="block rounded-md px-3 py-1.5 text-sm hover:bg-white/5">Authentication</a>
                <a href="#model-versions" className="block rounded-md px-3 py-1.5 text-sm hover:bg-white/5">AI Model Versions</a>
                <a href="#quick-start" className="block rounded-md px-3 py-1.5 text-sm hover:bg-white/5">Quick Start Guide</a>
              </nav>
            </div>
            <div>
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)]">Quick Start Guides</div>
              <nav className="space-y-1">
                {groups.map((g) => (
                  <a
                    key={g.key}
                    href={`#group-${g.key}`}
                    className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm hover:bg-white/5"
                  >
                    <span>{g.icon}</span>
                    <span className="truncate">{g.title.replace(/ APIs$/, "")}</span>
                  </a>
                ))}
              </nav>
            </div>
            <div>
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)]">Support</div>
              <nav className="space-y-1">
                <a href="#callbacks" className="block rounded-md px-3 py-1.5 text-sm hover:bg-white/5">Callback Integration</a>
                <a href="#support" className="block rounded-md px-3 py-1.5 text-sm hover:bg-white/5">Support &amp; Community</a>
              </nav>
            </div>
          </div>
        </aside>

        {/* ===== Main content ===== */}
        <main className="min-w-0 border-x-0 border-[var(--border)] py-10 md:border-x md:px-10">
          <section className="mb-12">
            <h1 id="welcome" data-toc="Welcome to Camxora API Documentation" className="scroll-mt-24 text-4xl font-extrabold tracking-tight">
              Welcome to <span className="grad-text">Camxora Music API</span> Documentation
            </h1>
            <p className="mt-3 text-[16px] text-[var(--muted)]">
              Complete Camxora API documentation — Your gateway to affordable and stable AI music API services.
            </p>
          </section>

          <section className="mb-12">
            <h2 id="about" data-toc="About Camxora API" className="scroll-mt-24 mb-4 text-2xl font-bold">About Camxora API</h2>
            <p className="text-sm text-[var(--muted)]">
              Camxora API delivers advanced AI music capabilities through easy-to-integrate APIs, including music
              generation, lyrics creation, audio processing, and video production. Our platform is designed for
              developers and businesses who need:
            </p>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {[
                ["99.9% Uptime", "Reliable and stable API performance"],
                ["Affordable Pricing", "Transparent, usage-based pricing system"],
                ["20-Second Streaming Output", "Fast delivery with streaming response"],
                ["High Concurrency", "Scalable solutions that grow with your needs"],
                ["24/7 Support", "Professional technical assistance"],
                ["Watermark-Free", "Commercial-ready music generation"],
              ].map(([t, d]) => (
                <li key={t} className="glass rounded-xl p-3 text-sm">
                  <div className="font-semibold">{t}</div>
                  <div className="mt-0.5 text-xs text-[var(--muted)]">{d}</div>
                </li>
              ))}
            </ul>
          </section>

          <section className="mb-12">
            <h2 id="key-features" data-toc="Key Features" className="scroll-mt-24 mb-4 text-2xl font-bold">Key Features</h2>
            <div className="space-y-4">
              {[
                ["🚀", "Latest AI Music Models", "Suno V5_5, V5, V4.5 Plus, V4.5 All, V4.5, V4. Supports creation of both vocal and instrumental tracks, music extension, and multi-format downloads."],
                ["💎", "Watermark-Free Commercial Use", "All music generated through our API is watermark-free, immediately suitable for commercial projects."],
                ["⚡", "20-Second Streaming Output", "Rapid delivery with streaming output enables real-time applications and live content creation."],
                ["🏗️", "High-Concurrency Architecture", "Built to handle multiple simultaneous requests with reliable performance under heavy traffic."],
                ["💰", "Transparent and Affordable Pricing", "Cost-effective and transparent pricing plans accessible to creators and enterprises."],
                ["🔧", "Comprehensive Developer Support", "Detailed, developer-friendly API documentation backed by an experienced technical team."],
              ].map(([icon, title, body]) => (
                <div key={title} className="glass rounded-2xl p-5">
                  <div className="flex items-start gap-3">
                    <div className="text-2xl">{icon}</div>
                    <div>
                      <h3 className="text-lg font-semibold">{title}</h3>
                      <p className="mt-1 text-sm text-[var(--muted)]">{body}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="mb-12">
            <h2 id="getting-started" data-toc="Getting Started" className="scroll-mt-24 mb-4 text-2xl font-bold">Getting Started</h2>
            <ol className="list-decimal space-y-2 pl-6 text-sm">
              <li><strong>Sign Up</strong> — Create your free account at Camxora Music API.</li>
              <li><strong>Get API Key</strong> — Obtain your authentication credentials from the API Key Management Page.</li>
              <li><strong>Choose Your API</strong> — Select from our comprehensive API collection below.</li>
              <li><strong>Follow Quick Start</strong> — Use the Quick Start Guide for rapid integration.</li>
              <li><strong>Test &amp; Deploy</strong> — Verify your integration and go live.</li>
            </ol>
          </section>

          <section className="mb-12">
            <h2 id="api-base-url" data-toc="API Base URL" className="scroll-mt-24 mb-4 text-2xl font-bold">API Base URL</h2>
            <p className="mb-3 text-sm text-[var(--muted)]">All API requests should be sent to:</p>
            <pre className="overflow-x-auto rounded-xl bg-black/40 p-4 font-mono text-sm">
{applyOrigin(`https://musicapi.camxora.com`, baseOrigin)}
              <span className="block text-[var(--muted)]"># or http://localhost:3000 during local dev (API backend)</span>
            </pre>
            <p className="mt-2 text-xs text-[var(--muted)]">
              <span className="text-violet-300">✓</span> In production deployments this value is automatically derived from the host you are visiting — no manual update required when you deploy to <code className="rounded bg-white/10 px-1.5 py-0.5">musicapi.camxora.com</code> or any other custom domain.
            </p>
          </section>

          <section className="mb-12">
            <h2 id="authentication" data-toc="Authentication" className="scroll-mt-24 mb-4 text-2xl font-bold">Authentication</h2>
            <p className="mb-3 text-sm text-[var(--muted)]">All API requests require authentication using a Bearer token:</p>
            <pre className="overflow-x-auto rounded-xl bg-black/40 p-4 font-mono text-sm">
Authorization: Bearer YOUR_API_KEY
            </pre>
            <p className="mt-3 text-sm text-[var(--muted)]">
              Pass your API key in the <code className="rounded bg-white/10 px-1.5 py-0.5">Authorization</code> header of every request.
              You can create and rotate API keys from your dashboard. Your keys carry many privileges, so keep them secure —
              do not share them in public repositories or client-side code.
            </p>
          </section>

          <section className="mb-12">
            <h2 id="model-versions" data-toc="AI Model Versions" className="scroll-mt-24 mb-4 text-2xl font-bold">AI Model Versions</h2>
            <p className="mb-4 text-sm text-[var(--muted)]">
              Camxora Music API supports the following AI music models. You can pass any of the keys below as the <code className="rounded bg-white/10 px-1.5 py-0.5">model</code> parameter:
            </p>
            <div className="overflow-hidden rounded-2xl border border-[var(--border)]">
              <table className="w-full border-collapse text-sm">
                <thead className="bg-white/5 text-left text-xs uppercase tracking-wider text-[var(--muted)]">
                  <tr>
                    <th className="px-4 py-3">Model Label</th>
                    <th className="px-4 py-3">Model Key</th>
                    <th className="px-4 py-3">Description</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {MODELS.map((m) => (
                    <tr key={m.key} className="hover:bg-white/5">
                      <td className="px-4 py-3 font-semibold">{m.label}</td>
                      <td className="px-4 py-3 font-mono text-xs text-violet-400">{m.key}</td>
                      <td className="px-4 py-3 text-[var(--muted)]">{m.tagline}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="mb-12">
            <h2 id="quick-start" data-toc="Quick Start Guide" className="scroll-mt-24 mb-4 text-2xl font-bold">Quick Start Guide</h2>
            <div className="space-y-4">
              <div className="glass rounded-2xl p-5">
                <h3 className="mb-3 text-lg font-semibold">Step 1 — Check your credits</h3>
                <pre className="overflow-x-auto rounded-xl bg-black/40 p-4 font-mono text-sm">
{applyOrigin(`# Check balance (Camxora native shape)
curl "https://musicapi.camxora.com/v1/credits" \\
  -H "Authorization: Bearer YOUR_API_KEY"

# Or use the docs.sunoapi.org compatible alias
curl "https://musicapi.camxora.com/api/v1/get-credits" \\
  -H "Authorization: Bearer YOUR_API_KEY"`, baseOrigin)}
                </pre>
              </div>
              <div className="glass rounded-2xl p-5">
                <h3 className="mb-3 text-lg font-semibold">Step 2 — Generate your first song</h3>
                <pre className="overflow-x-auto rounded-xl bg-black/40 p-4 font-mono text-sm">
{applyOrigin(`# Native /v1/music endpoint
curl -X POST "https://musicapi.camxora.com/v1/music" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "gpt_description_prompt": "Upbeat synthwave road trip theme",
    "model": "chirp-crow"
  }'

# Or use the docs.sunoapi.org-compatible alias
curl -X POST "https://musicapi.camxora.com/api/v1/generate" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "prompt": "Upbeat synthwave road trip theme",
    "customMode": false,
    "model": "V5",
    "callBackUrl": "https://your-webhook.example.com/done"
  }'`, baseOrigin)}
                </pre>
                <p className="mt-3 text-sm text-[var(--muted)]">
                  Poll <code className="rounded bg-white/10 px-1.5 py-0.5">/v1/task/:id</code> (or the aliased <code className="rounded bg-white/10 px-1.5 py-0.5">/api/v1/generate/record-info?taskId=</code>)
                  until status is <code className="rounded bg-white/10 px-1.5 py-0.5">complete</code>, then follow the <code className="rounded bg-white/10 px-1.5 py-0.5">clip/:id</code> links in the response for playback URLs.
                </p>
              </div>
            </div>
          </section>

          <section className="mb-12">
            <h2 id="use-cases" data-toc="Use Cases" className="scroll-mt-24 mb-4 text-2xl font-bold">Use Cases</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {[
                ["🎬 Media Production", "Royalty-free background scores for videos, films, and podcasts with custom moods and genres."],
                ["🎮 Game Development", "Adaptive procedural soundtracks and level-specific ambient tracks generated on-demand."],
                ["📱 Social Content", "Viral-ready hooks and trending-style beats for TikTok, Reels, and YouTube Shorts."],
                ["🛍️ Advertising", "Custom jingles and branded audio identities tailored to campaign briefs."],
                ["🎼 Music Education", "Arrangement variations, accompaniment tracks, and MIDI transcriptions for learning."],
                ["💬 AI Assistants", "High-quality TTS-backed musical cues for chat bots, voice skills, and interactive fiction."],
              ].map(([t, d]) => (
                <div key={t} className="glass rounded-2xl p-4">
                  <div className="font-semibold">{t}</div>
                  <p className="mt-1.5 text-sm text-[var(--muted)]">{d}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="mb-12">
            <h2 id="callbacks" data-toc="Callback Integration" className="scroll-mt-24 mb-4 text-2xl font-bold">Callback Integration</h2>
            <p className="mb-3 text-sm text-[var(--muted)]">
              Any POST endpoint that accepts a <code className="rounded bg-white/10 px-1.5 py-0.5">callback_url</code> (or sunoapi.org alias <code className="rounded bg-white/10 px-1.5 py-0.5">callBackUrl</code>)
              will issue a webhook POST to that URL once the job transitions to <code className="rounded bg-white/10 px-1.5 py-0.5">complete</code> or <code className="rounded bg-white/10 px-1.5 py-0.5">error</code>.
            </p>
            <pre className="overflow-x-auto rounded-xl bg-black/40 p-4 font-mono text-sm">
{`// Example callback payload (POSTed to your callBackUrl)
{
  "job_id":      "suno_task_01H...",
  "type":        "music",
  "status":      "complete",
  "result":      { "clips": [ { "id": "...", "audio_url": "...", "image_url": "..." } ] },
  "endpoint":    "music",
  "credits":     9
}`}
            </pre>
          </section>

          <section className="mb-16">
            <h2 id="support" data-toc="Support & Community" className="scroll-mt-24 mb-4 text-2xl font-bold">Support &amp; Community</h2>
            <p className="text-sm text-[var(--muted)]">
              Need help? Reach out through your account dashboard for priority 24/7 technical support.
              We also maintain detailed per-endpoint examples below — every operation is documented with its
              parameters, cURL example, and response envelope shape.
            </p>
          </section>

          {/* ===== Quick Start Guide endpoint groups ===== */}
          {groups.map((g) => {
            const sectionId = `group-${g.key}`;
            return (
            <section key={g.key} className="mb-16 scroll-mt-24">
              <div className="mb-5 flex items-baseline gap-3">
                <h2 id={sectionId} data-toc={`${g.icon} ${g.title}`} className="text-2xl font-bold">
                  <span className="mr-2">{g.icon}</span>
                  {g.title}
                </h2>
                <span className="text-sm text-[var(--muted)]">{g.tagline}</span>
              </div>

              <div className="space-y-6">
                {g.endpoints.map((e) => {
                  const anchor = slug(`${e.method}-${e.path}`);
                  return (
                    <article key={anchor} id={anchor} className="glass scroll-mt-24 rounded-2xl p-5">
                      <div className="flex flex-wrap items-center gap-3">
                        <MethodBadge method={e.method} />
                        <code className="break-all font-mono text-sm text-white">{e.path}</code>
                      </div>
                      <p className="mt-3 text-sm text-[var(--muted)]">{e.desc}</p>

                      {e.params && e.params.length > 0 && (
                        <div className="mt-4 overflow-hidden rounded-xl border border-[var(--border)]">
                          <table className="w-full border-collapse text-sm">
                            <thead className="bg-white/5 text-left text-xs uppercase tracking-wider text-[var(--muted)]">
                              <tr>
                                <th className="px-4 py-2.5">Param</th>
                                <th className="px-4 py-2.5">Required</th>
                                <th className="px-4 py-2.5">Description</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-[var(--border)]">
                              {e.params.map((p) => (
                                <tr key={p.name} className="hover:bg-white/5">
                                  <td className="px-4 py-2.5 font-mono text-xs text-violet-400">{p.name}</td>
                                  <td className="px-4 py-2.5">
                                    {p.required ? (
                                      <span className="inline-flex items-center rounded-full bg-fuchsia-500/10 px-2 py-0.5 text-[11px] font-semibold text-fuchsia-400">required</span>
                                    ) : (
                                      <span className="inline-flex items-center rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-[var(--muted)]">optional</span>
                                    )}
                                  </td>
                                  <td className="px-4 py-2.5 text-[var(--muted)]">{p.desc}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}

                      {e.example && (
                        <details className="mt-4 rounded-xl border border-[var(--border)] bg-black/20">
                          <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium hover:bg-white/5">Example request</summary>
                          <pre className="overflow-x-auto px-4 pb-4 pt-2 font-mono text-xs leading-relaxed">{applyOrigin(e.example, baseOrigin)}</pre>
                        </details>
                      )}
                    </article>
                  );
                })}
              </div>
            </section>
            );
          })}

          <footer className="mt-20 border-t border-[var(--border)] pt-6 text-center text-xs text-[var(--muted)]">
            © {new Date().getFullYear()} Camxora Music API — {ENDPOINTS.length} endpoints, 100% Suno-compatible surface area.
          </footer>
        </main>

        {/* ===== Right sidebar (TOC) ===== */}
        <aside className="sticky top-16 hidden h-[calc(100vh-4rem)] overflow-y-auto py-8 pl-4 md:block">
          <div className="space-y-1">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)]">On this page</div>
            {toc.map((t) => (
              <a
                key={t.id}
                href={`#${t.id}`}
                className={`block border-l-2 px-3 py-1 text-xs transition-colors ${
                  active === t.id
                    ? "border-l-violet-500 text-violet-400 font-semibold"
                    : "border-l-transparent text-[var(--muted)] hover:text-white"
                } ${t.level === 3 ? "pl-6" : ""}`}
              >
                {t.label}
              </a>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
