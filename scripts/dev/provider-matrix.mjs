#!/usr/bin/env node
/**
 * Provider matrix — W6 (docs/studio/RESIDUAL_VERIFICATION_PLAN.md §4).
 *
 * Runs the 12 paid provider operations in cheapest-first order, records the
 * platform ids / provider ids / terminal status of each, and refuses to spend
 * past an approved credit cap.
 *
 * Defaults to `--dry-run`: logs in, reads the real prices from the pricing
 * endpoint, prints the plan and the preconditions, and exits without a single
 * provider call. `--execute` is the only way to spend a credit, and it is
 * gated on the same preconditions plus a public callback tunnel.
 *
 * Node 18+ / no dependencies (global fetch, FormData, Blob).
 *
 *   node scripts/dev/provider-matrix.mjs --budget 320
 *   node scripts/dev/provider-matrix.mjs --budget 320 --execute --out docs/studio/reports/provider-matrix/run-1
 *
 * Exit codes: 0 ok · 2 preconditions not met (plan still printed) · 3 a row did not
 * reach a green terminal state · 1 usage/config error.
 */

import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

const MODELS = new Set(['V6', 'V6_MINI', 'V6_WILD']);
const DEFAULT_MODEL = 'V6_MINI';
const TERMINAL_GENERATION = new Set(['SUCCESS', 'FAILED', 'CANCELLED']);
const TERMINAL_OPERATION = new Set(['complete', 'completed', 'success', 'error', 'failed']);
const API_PREFIX = '/api/v3';

// ---------------------------------------------------------------------------
// CLI + env
// ---------------------------------------------------------------------------

function usage() {
  return `provider-matrix — paid provider matrix runner (W6)

Usage:
  node scripts/dev/provider-matrix.mjs --budget <credits> [--execute] [options]

Required env:
  PLATFORM_API_BASE_URL              e.g. http://127.0.0.1:8100
  PLATFORM_STUDIO_INTERNAL_TOKEN     the same value musicapi runs with
  PLATFORM_TEST_EMAIL                test account email
  PLATFORM_TEST_PASSWORD             test account password
  PLATFORM_SUNO_CALLBACK_BASE_URL    public tunnel base (cloudflared → :8100)

Optional env:
  PLATFORM_ACCESS_TOKEN   skip login with an existing bearer token
  PLATFORM_STUDIO_MODEL   V6 | V6_MINI | V6_WILD (default ${DEFAULT_MODEL})
  MUSICAPI_BASE_URL       e.g. http://127.0.0.1:4003 — probe /internal/studio/health

Options:
  --budget <credits>     hard cap; an operation that would exceed it is skipped (required)
  --execute              actually call the provider (default: dry run)
  --out <dir>            write provider-matrix.json + .md here
  --only <a,b,c>         run only these operation ids
  --task <uuid>          reuse an existing successful generation as the source
  --retries <n>          retries across failed paid operations (default 0)
  --timeout <seconds>    per-operation poll timeout (default 900)
  --poll-interval <s>    poll interval (default 5)
  --self-test            check the pure helpers and the 188-credit arithmetic offline
  --help
`;
}

function parseArgs(argv) {
  const opts = {
    budget: null,
    execute: false,
    out: null,
    only: null,
    task: null,
    retries: 0,
    timeoutSec: 900,
    pollSec: 5,
    help: false,
    selfTest: false,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = () => {
      const value = argv[i + 1];
      if (value === undefined || value.startsWith('--')) throw new Error(`${arg} needs a value`);
      i += 1;
      return value;
    };
    switch (arg) {
      case '--budget': opts.budget = Number(next()); break;
      case '--execute': opts.execute = true; break;
      case '--out': opts.out = next(); break;
      case '--only': opts.only = next().split(',').map((v) => v.trim()).filter(Boolean); break;
      case '--task': opts.task = next(); break;
      case '--retries': opts.retries = Number(next()); break;
      case '--timeout': opts.timeoutSec = Number(next()); break;
      case '--poll-interval': opts.pollSec = Number(next()); break;
      case '--self-test': opts.selfTest = true; break;
      case '--help': case '-h': opts.help = true; break;
      default: throw new Error(`unknown argument: ${arg}`);
    }
  }
  return opts;
}

function readEnv() {
  const env = process.env;
  const baseUrl = String(env.PLATFORM_API_BASE_URL || '').trim().replace(/\/+$/, '');
  return {
    baseUrl,
    token: String(env.PLATFORM_STUDIO_INTERNAL_TOKEN || '').trim(),
    email: String(env.PLATFORM_TEST_EMAIL || env.PLATFORM_EMAIL || '').trim(),
    password: String(env.PLATFORM_TEST_PASSWORD || env.PLATFORM_PASSWORD || ''),
    accessToken: String(env.PLATFORM_ACCESS_TOKEN || '').trim(),
    callbackBase: String(env.PLATFORM_SUNO_CALLBACK_BASE_URL || '').trim(),
    model: String(env.PLATFORM_STUDIO_MODEL || DEFAULT_MODEL).trim().toUpperCase(),
    musicapiBase: String(env.MUSICAPI_BASE_URL || '').trim().replace(/\/+$/, ''),
  };
}

// ---------------------------------------------------------------------------
// Precondition: the callback base must be publicly reachable
//
// Suno rejects callbacks aimed at a local/private host, and the platform
// silently falls back to https://localhost when the base is empty, so a
// generation started against a private base never leaves PENDING.
// Mirrors platform_api.services.web_music_service._callback_base_is_public.
// ---------------------------------------------------------------------------

function isPrivateHost(hostname) {
  const host = String(hostname || '').toLowerCase().replace(/^\[|\]$/g, '');
  if (!host) return true;
  if (host === 'localhost' || host.endsWith('.localhost')) return true;

  // IPv4 literal
  const v4 = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (v4) {
    const [a, b] = v4.slice(1).map(Number);
    if (v4.slice(1).some((part) => Number(part) > 255)) return true;
    if (a === 10) return true;
    if (a === 127) return true;
    if (a === 0) return true;
    if (a === 169 && b === 254) return true;
    if (a === 172 && b >= 16 && b <= 31) return true;
    if (a === 192 && b === 168) return true;
    if (a === 100 && b >= 64 && b <= 127) return true; // CGNAT
    if (a >= 224) return true; // multicast / reserved
    return false;
  }

  // IPv6 literal (bracketed or bare)
  if (host.includes(':')) {
    if (host === '::1' || host === '::') return true;
    if (/^f[cd][0-9a-f]{2}:/.test(host)) return true; // fc00::/7
    if (/^fe[89ab][0-9a-f]:/.test(host)) return true; // fe80::/10
    return false;
  }

  // A single-label host is only routable inside a private network.
  if (!host.includes('.')) return true;
  return false;
}

function callbackBaseProblem(raw) {
  if (!raw) return 'not set — generation would call back to https://localhost';
  let url;
  try {
    url = new URL(raw);
  } catch {
    return 'not an absolute URL';
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return 'must be http(s)';
  if (isPrivateHost(url.hostname)) {
    return `host ${url.hostname} is local/private — the provider cannot call back`;
  }
  return null;
}

// ---------------------------------------------------------------------------
// HTTP
// ---------------------------------------------------------------------------

class HttpError extends Error {
  constructor(status, message, payload) {
    super(message);
    this.name = 'HttpError';
    this.status = status;
    this.payload = payload;
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function createClient({ baseUrl, accessToken, refreshToken = null, onToken = null }) {
  const root = `${baseUrl}${API_PREFIX}`;
  let token = accessToken;
  let refresh = refreshToken;

  /**
   * Exchange the refresh token for a new access token. The login JWT lives 900 s and the
   * matrix's own poll window is up to 900 s, so a long generation row is guaranteed to
   * outlive its token (measured: a generation poll 401'd at the 15-minute mark and the row
   * was recorded as an error instead of a provider result).
   */
  async function renew() {
    if (!refresh) return false;
    try {
      const response = await fetch(`${root}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refresh }),
        signal: AbortSignal.timeout(30000),
      });
      if (!response.ok) return false;
      const payload = await response.json();
      if (!payload || !payload.access_token) return false;
      token = payload.access_token;
      if (payload.refresh_token) refresh = payload.refresh_token;
      if (onToken) onToken(token, refresh);
      return true;
    } catch {
      return false;
    }
  }

  async function call(pathname, options = {}) {
    try {
      return await attempt(pathname, options);
    } catch (err) {
      if (err instanceof HttpError && err.status === 401 && options.auth !== false) {
        if (await renew()) return await attempt(pathname, options);
      }
      throw err;
    }
  }

  async function attempt(pathname, options = {}) {
    const {
      method = 'GET',
      json,
      form,
      raw = false,
      timeoutMs = 60000,
      auth = true,
    } = options;
    const url = pathname.startsWith('http') ? pathname : `${root}${pathname}`;
    const headers = {};
    if (auth && token) headers.Authorization = `Bearer ${token}`;
    let body;
    if (form) {
      body = form;
    } else if (json !== undefined) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(json);
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    let response;
    try {
      response = await fetch(url, { method, headers, body, signal: controller.signal });
    } catch (err) {
      clearTimeout(timer);
      const reason = err?.name === 'AbortError' ? `timed out after ${timeoutMs} ms` : err.message;
      throw new HttpError(0, `${method} ${pathname} failed: ${reason}`, null);
    }
    clearTimeout(timer);

    if (raw) {
      const buffer = Buffer.from(await response.arrayBuffer());
      if (!response.ok) {
        throw new HttpError(response.status, `${method} ${pathname} → ${response.status}`, buffer.toString('utf8').slice(0, 400));
      }
      return { response, buffer };
    }

    const text = await response.text();
    let payload = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = text;
      }
    }
    if (!response.ok) {
      const detail =
        (payload && typeof payload === 'object' && (payload.detail || payload.message || payload.error)) ||
        (typeof payload === 'string' ? payload : '') ||
        response.statusText;
      throw new HttpError(response.status, `${method} ${pathname} → ${response.status}: ${detail}`, payload);
    }
    return payload;
  }

  return { call, root };
}

// ---------------------------------------------------------------------------
// Matrix definition
//
// `costKeys` are resolved from the live pricing endpoints, never hard-coded.
// Order is cheapest-first and dependency-ordered: the free reads, then the
// 12-credit edits, then the 60-credit 12-track split.
// ---------------------------------------------------------------------------

const MATRIX = [
  {
    id: 'generate',
    title: 'Generate a song',
    method: 'POST',
    endpoint: '/web-music/generate',
    costKeys: ['music'],
    provider: 'musicapi POST /v1/music/generate → Suno',
    poll: 'GET /web-music/generations/{task_id}',
    run: runGenerate,
  },
  {
    id: 'export_wav',
    title: 'Export WAV',
    method: 'GET',
    endpoint: '/web-music/generations/{task_id}/download-wav?variant=ok',
    costKeys: [],
    provider: 'Suno WAV conversion (via song wav task)',
    poll: 'synchronous (blocks up to ~60 s, retried)',
    run: runExportWav,
  },
  {
    id: 'export_mp3',
    title: 'Export MP3',
    method: 'GET',
    endpoint: '/web-music/generations/{task_id}/download?variant=ok',
    costKeys: [],
    provider: 'B2 / Suno audio + owner watermark',
    poll: 'synchronous',
    run: runExportMp3,
  },
  {
    id: 'persona',
    title: 'Voice persona',
    method: 'POST',
    endpoint: '/web-music/studio/voice/personas',
    costKeys: [],
    provider: 'none (studio_personas row) / POST /internal/studio/persona (clip mode)',
    poll: 'synchronous, or GET /web-music/studio/personas (clip mode)',
    run: runPersona,
  },
  {
    id: 'bounce_upload',
    title: 'Bounce / upload (upload + upload-extend)',
    method: 'POST',
    endpoint: '/web-music/studio/uploads → /web-music/studio/uploads/{id}/extend',
    costKeys: ['studio_edit'],
    provider: 'storage (upload) + POST /internal/studio/upload-extend',
    poll: 'GET /web-music/studio/operations/{id}',
    run: runBounceUpload,
  },
  {
    id: 'stems_2',
    title: 'Stems — 2 track',
    method: 'POST',
    endpoint: '/web-music/studio/generations/{task_id}/stems',
    costKeys: ['stems_2'],
    provider: 'POST /internal/studio/stems {mode: vocal}',
    poll: 'GET /web-music/studio/operations/{id}',
    run: (ctx) => runClipOperation(ctx, 'stems_2'),
  },
  {
    id: 'cover',
    title: 'Cover',
    method: 'POST',
    endpoint: '/web-music/studio/generations/{task_id}/cover',
    costKeys: ['studio_edit'],
    provider: 'POST /internal/studio/cover',
    poll: 'GET /web-music/studio/operations/{id}',
    run: (ctx) => runClipOperation(ctx, 'cover'),
  },
  {
    id: 'extend',
    title: 'Extend',
    method: 'POST',
    endpoint: '/web-music/studio/generations/{task_id}/extend',
    costKeys: ['studio_edit'],
    provider: 'POST /internal/studio/extend',
    poll: 'GET /web-music/studio/operations/{id}',
    run: (ctx) => runClipOperation(ctx, 'extend'),
  },
  {
    id: 'remaster',
    title: 'Remaster',
    method: 'POST',
    endpoint: '/web-music/studio/generations/{task_id}/remaster',
    costKeys: ['studio_edit'],
    provider: 'POST /internal/studio/remaster',
    poll: 'GET /web-music/studio/operations/{id}',
    run: (ctx) => runClipOperation(ctx, 'remaster'),
  },
  {
    id: 'vocals',
    title: 'Add vocals',
    method: 'POST',
    endpoint: '/web-music/studio/generations/{task_id}/add-vocals',
    costKeys: ['studio_edit'],
    provider: 'POST /internal/studio/add-vocals',
    poll: 'GET /web-music/studio/operations/{id}',
    run: (ctx) => runClipOperation(ctx, 'vocals'),
  },
  {
    id: 'instrumental',
    title: 'Add instrumental',
    method: 'POST',
    endpoint: '/web-music/studio/generations/{task_id}/add-instrumental',
    costKeys: ['studio_edit'],
    provider: 'POST /internal/studio/add-instrumental',
    poll: 'GET /web-music/studio/operations/{id}',
    run: (ctx) => runClipOperation(ctx, 'instrumental'),
  },
  {
    id: 'replace',
    title: 'Replace section',
    method: 'POST',
    endpoint: '/web-music/studio/generations/{task_id}/replace-section',
    costKeys: ['studio_edit'],
    provider: 'POST /internal/studio/replace-section',
    poll: 'GET /web-music/studio/operations/{id}',
    run: (ctx) => runClipOperation(ctx, 'replace'),
  },
  {
    id: 'mashup',
    title: 'Mashup (+ fixture generation)',
    method: 'POST',
    endpoint: '/web-music/studio/mashup',
    costKeys: ['studio_edit', 'music'],
    provider: 'POST /internal/studio/mashup',
    poll: 'GET /web-music/studio/operations/{id}',
    run: runMashup,
  },
  {
    id: 'stems_12',
    title: 'Stems — 12 track',
    method: 'POST',
    endpoint: '/web-music/studio/generations/{task_id}/stems',
    costKeys: ['stems_12'],
    provider: 'POST /internal/studio/stems {mode: advanced}',
    poll: 'GET /web-music/studio/operations/{id}',
    run: (ctx) => runClipOperation(ctx, 'stems_12'),
  },
];

// ---------------------------------------------------------------------------
// Operation implementations
// ---------------------------------------------------------------------------

function stamp() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

function lyricsFor(label) {
  return [
    '[Verse]',
    `A quiet room, a steady line, ${label} in the morning light`,
    'Every take a little closer to the shape I had in mind',
    '',
    '[Chorus]',
    'Hold the note and let it run, nothing here to overthink',
    `${label} on a single pass, the whole arrangement in one link`,
  ].join('\n');
}

async function pollGeneration(ctx, taskId, { timeoutSec } = {}) {
  const deadline = Date.now() + (timeoutSec || ctx.opts.timeoutSec) * 1000;
  let last = null;
  while (Date.now() < deadline) {
    last = await ctx.client.call(`/web-music/generations/${taskId}`, { timeoutMs: 60000 });
    const status = String(last.status || '').toUpperCase();
    if (TERMINAL_GENERATION.has(status)) return last;
    await sleep(ctx.opts.pollSec * 1000);
  }
  return last;
}

async function pollOperation(ctx, operationId) {
  const deadline = Date.now() + ctx.opts.timeoutSec * 1000;
  let last = null;
  while (Date.now() < deadline) {
    last = await ctx.client.call(`/web-music/studio/operations/${operationId}`, { timeoutMs: 60000 });
    const status = String(last.status || '').toLowerCase();
    if (TERMINAL_OPERATION.has(status)) return last;
    await sleep(ctx.opts.pollSec * 1000);
  }
  return last;
}

async function createProject(ctx, title) {
  const project = await ctx.client.call('/web-music/studio/projects', {
    method: 'POST',
    json: { title: `[matrix] ${title}`.slice(0, 120), bpm: 84, time_signature: '4/4', data: {} },
  });
  return String(project.id);
}

async function generateSong(ctx, label) {
  const body = {
    mode: 'advanced',
    title: `Provider matrix ${label}`.slice(0, 200),
    style: 'ambient electronic, soft synth pad, 84 bpm, warm tape',
    lyrics: lyricsFor(label),
    instrumental: false,
    model: ctx.model,
    prompt: '',
  };
  const created = await ctx.client.call('/web-music/generate', { method: 'POST', json: body });
  const taskId = String(created.task_id);
  const final = await pollGeneration(ctx, taskId);
  if (String(final.status || '').toUpperCase() !== 'SUCCESS') {
    throw new Error(`generation ${taskId} ended ${final.status}: ${final.error_message || 'no message'}`);
  }
  return { taskId, final, body };
}

async function runGenerate(ctx) {
  const { taskId, final } = await generateSong(ctx, `generate ${ctx.runTag}`);
  ctx.state.taskId = taskId;
  return {
    ids: { task_id: taskId },
    evidence: {
      status: String(final.status).toUpperCase(),
      model: final.model,
      title: final.title,
      clips: Array.isArray(final.clips)
        ? final.clips.map((clip) => ({ variant: clip.variant, ready: clip.ready, seconds: clip.duration_seconds }))
        : [],
    },
  };
}

async function requireTask(ctx) {
  if (!ctx.state.taskId) throw new Error('no source generation — the generate step must run first (or pass --task)');
  return ctx.state.taskId;
}

async function runExportWav(ctx) {
  const taskId = await requireTask(ctx);
  let lastError = null;
  for (let attempt = 1; attempt <= 6; attempt += 1) {
    try {
      const { response, buffer } = await ctx.client.call(
        `/web-music/generations/${taskId}/download-wav?variant=ok`,
        { raw: true, timeoutMs: 180000 },
      );
      const riff = buffer.subarray(0, 4).toString('ascii');
      ctx.state.wav = buffer;
      return {
        ids: { task_id: taskId },
        evidence: {
          status: 'downloaded',
          content_type: response.headers.get('content-type'),
          filename: response.headers.get('content-disposition'),
          bytes: buffer.length,
          magic: riff,
        },
      };
    } catch (err) {
      lastError = err;
      const message = String(err.message || '');
      const retryable = err.status === 400 && /not ready yet/i.test(message);
      if (!retryable || attempt === 6) break;
      ctx.log(`  · WAV not ready (attempt ${attempt}/6), waiting 15 s`);
      await sleep(15000);
    }
  }
  throw lastError;
}

async function runExportMp3(ctx) {
  const taskId = await requireTask(ctx);
  const { response, buffer } = await ctx.client.call(
    `/web-music/generations/${taskId}/download?variant=ok`,
    { raw: true, timeoutMs: 180000 },
  );
  return {
    ids: { task_id: taskId },
    evidence: {
      status: 'downloaded',
      content_type: response.headers.get('content-type'),
      filename: response.headers.get('content-disposition'),
      bytes: buffer.length,
    },
  };
}

/**
 * Voice persona: the only matrix row that is free and cannot be fully
 * scripted. With PLATFORM_VOICE_ID set (a voice already verified through
 * /studio/voice/samples + /studio/voice/verify) it creates the voice persona.
 * Without it, it records the clip-persona provider job instead, which is the
 * same billing bucket (no charge) and does produce a provider persona id.
 */
async function runPersona(ctx) {
  const voiceId = String(process.env.PLATFORM_VOICE_ID || '').trim();
  if (voiceId) {
    const persona = await ctx.client.call('/web-music/studio/voice/personas', {
      method: 'POST',
      json: { name: `Matrix voice ${ctx.runTag}`.slice(0, 80), styles: 'ambient', voice_id: voiceId },
    });
    return {
      ids: { persona_id: String(persona.id), provider_persona_id: persona.provider_persona_id || voiceId },
      evidence: { mode: 'voice', status: persona.status, provider_persona_id: persona.provider_persona_id },
      note: 'voice persona needs a verified voice_id (human recording of /studio/voice/phrase)',
    };
  }

  const taskId = await requireTask(ctx);
  const persona = await ctx.client.call(`/web-music/studio/generations/${taskId}/personas`, {
    method: 'POST',
    json: {
      name: `Matrix clip ${ctx.runTag}`.slice(0, 80),
      styles: 'ambient electronic',
      description: 'provider matrix persona probe',
      variant: 'ok',
    },
  });
  const personaId = String(persona.id);
  const deadline = Date.now() + ctx.opts.timeoutSec * 1000;
  let latest = persona;
  while (Date.now() < deadline) {
    const list = await ctx.client.call('/web-music/studio/personas', { timeoutMs: 60000 });
    const items = Array.isArray(list) ? list : list.items || [];
    const found = items.find((item) => String(item.id) === personaId);
    if (found) latest = found;
    const status = String(latest.status || '').toLowerCase();
    if (TERMINAL_OPERATION.has(status)) break;
    await sleep(ctx.opts.pollSec * 1000);
  }
  return {
    ids: {
      persona_id: personaId,
      provider_persona_id: latest.provider_persona_id || latest.provider_clip_id || null,
      musicapi_job_id: latest.musicapi_job_id || null,
    },
    evidence: { mode: 'clip', status: latest.status, provider_persona_id: latest.provider_persona_id || null },
    note: 'set PLATFORM_VOICE_ID to exercise the voice-persona route instead',
  };
}

async function runBounceUpload(ctx) {
  const taskId = await requireTask(ctx);
  let audio = ctx.state.wav;
  if (!audio) {
    const { buffer } = await ctx.client.call(
      `/web-music/generations/${taskId}/download-wav?variant=ok`,
      { raw: true, timeoutMs: 180000 },
    );
    audio = buffer;
  }
  const form = new FormData();
  form.append('file', new Blob([audio], { type: 'audio/wav' }), 'provider-matrix-bounce.wav');
  form.append('duration_seconds', '8');
  const upload = await ctx.client.call('/web-music/studio/uploads', { method: 'POST', form, timeoutMs: 120000 });
  const uploadId = String(upload.id);

  const projectId = await createProject(ctx, `upload ${ctx.runTag}`);
  const operation = await ctx.client.call(`/web-music/studio/uploads/${uploadId}/extend`, {
    method: 'POST',
    json: { prompt: 'extend with a soft outro', continue_at: 8, title: 'Matrix bounce', tags: 'ambient', project_id: projectId },
  });
  const final = await pollOperation(ctx, String(operation.id));
  const status = String(final.status || '').toLowerCase();
  if (!TERMINAL_OPERATION.has(status)) throw new Error(`upload extend ended ${final.status}`);
  return {
    ids: {
      upload_id: uploadId,
      operation_id: String(operation.id),
      musicapi_job_id: final.musicapi_job_id || null,
      provider_clip_id: final.provider_clip_id || null,
    },
    evidence: {
      status,
      upload_bytes: upload.size_bytes,
      upload_url: upload.url,
      credits_charged: final.credits_charged,
      charge_op: final.charge_op,
      result_clips: resultClipIds(final),
    },
  };
}

function resultClipIds(operation) {
  const result = operation && operation.result;
  const clips = result && Array.isArray(result.clips) ? result.clips : [];
  return clips.map((clip) => ({
    id: clip.id || clip.clip_id || null,
    variant: clip.variant || null,
    title: clip.title || null,
  }));
}

const CLIP_OPERATION_BODIES = {
  stems_2: (ctx) => ({ body: { variant: 'ok', mode: 'vocal' }, suffix: 'stems 2' }),
  stems_12: (ctx) => ({ body: { variant: 'ok', mode: 'advanced' }, suffix: 'stems 12' }),
  cover: (ctx) => ({ body: { variant: 'ok', prompt: 'warm analog cover, slower tempo' }, suffix: 'cover' }),
  extend: (ctx) => ({ body: { variant: 'ok', continue_at: 20 }, suffix: 'extend' }),
  remaster: (ctx) => ({ body: { variant: 'ok' }, suffix: 'remaster' }),
  vocals: (ctx) => ({ body: { variant: 'ok', prompt: 'soft female vocal, close mic' }, suffix: 'vocals' }),
  instrumental: (ctx) => ({ body: { variant: 'ok', prompt: 'instrumental, no vocals, add strings' }, suffix: 'instrumental' }),
  replace: () => ({
    body: { variant: 'ok', start_s: 10, end_s: 25, lyrics: '[Verse]\nReplaced line for the provider matrix pass' },
    suffix: 'replace',
  }),
};

async function runClipOperation(ctx, opId) {
  const taskId = await requireTask(ctx);
  const spec = CLIP_OPERATION_BODIES[opId](ctx);
  const projectId = await createProject(ctx, `${spec.suffix} ${ctx.runTag}`);
  const created = await ctx.client.call(`/web-music/studio/generations/${taskId}/${endpointTail(opId)}`, {
    method: 'POST',
    json: { ...spec.body, project_id: projectId },
  });
  const operationId = String(created.id);
  const final = await pollOperation(ctx, operationId);
  const status = String(final.status || '').toLowerCase();
  if (!TERMINAL_OPERATION.has(status) || status === 'error' || status === 'failed') {
    throw new Error(`${opId} ended ${final.status}: ${final.error_message || 'no message'}`);
  }
  return {
    ids: {
      operation_id: operationId,
      musicapi_job_id: final.musicapi_job_id || null,
      provider_clip_id: final.provider_clip_id || null,
      project_id: projectId,
    },
    evidence: {
      status,
      credits_charged: final.credits_charged,
      charge_op: final.charge_op,
      result_clips: resultClipIds(final),
    },
  };
}

function endpointTail(opId) {
  return {
    stems_2: 'stems',
    stems_12: 'stems',
    cover: 'cover',
    extend: 'extend',
    remaster: 'remaster',
    vocals: 'add-vocals',
    instrumental: 'add-instrumental',
    replace: 'replace-section',
  }[opId];
}

async function runMashup(ctx) {
  const firstTask = await requireTask(ctx);
  // A mashup needs two distinct successful tasks owned by this user. The
  // fixture generation is charged as part of this row.
  const fixture = await generateSong(ctx, `mashup fixture ${ctx.runTag}`);
  ctx.state.fixtureTaskId = fixture.taskId;
  const projectId = await createProject(ctx, `mashup ${ctx.runTag}`);
  const created = await ctx.client.call('/web-music/studio/mashup', {
    method: 'POST',
    json: { task_ids: [firstTask, fixture.taskId], variants: ['ok', 'ok'], prompt: 'blend both takes', project_id: projectId },
  });
  const operationId = String(created.id);
  const final = await pollOperation(ctx, operationId);
  const status = String(final.status || '').toLowerCase();
  if (!TERMINAL_OPERATION.has(status) || status === 'error' || status === 'failed') {
    throw new Error(`mashup ended ${final.status}: ${final.error_message || 'no message'}`);
  }
  return {
    ids: {
      operation_id: operationId,
      musicapi_job_id: final.musicapi_job_id || null,
      provider_clip_id: final.provider_clip_id || null,
      source_task_ids: [firstTask, fixture.taskId],
      fixture_task_id: fixture.taskId,
    },
    evidence: {
      status,
      credits_charged: final.credits_charged,
      charge_op: final.charge_op,
      result_clips: resultClipIds(final),
      fixture_status: String(fixture.final.status).toUpperCase(),
    },
  };
}

// ---------------------------------------------------------------------------
// Preflight: login, readiness, prices, quota
// ---------------------------------------------------------------------------

async function login(env) {
  if (env.accessToken) return { accessToken: env.accessToken, refreshToken: null };
  if (!env.email || !env.password) {
    throw new Error('PLATFORM_TEST_EMAIL / PLATFORM_TEST_PASSWORD are required unless PLATFORM_ACCESS_TOKEN is set');
  }
  const anonymous = createClient({ baseUrl: env.baseUrl, accessToken: null });
  const payload = await anonymous.call('/auth/login', {
    method: 'POST',
    json: { email: env.email, password: env.password, remember: false },
    auth: false,
    timeoutMs: 30000,
  });
  const token = payload && payload.access_token;
  if (!token) throw new Error('login returned no access_token');
  // The refresh token lets a 15-minute matrix poll past its 900 s access token.
  return { accessToken: token, refreshToken: payload.refresh_token || null };
}

async function probeMusicapi(env) {
  if (!env.musicapiBase) return { skipped: true };
  // A cold Node -> MusicAPI connection on this host has been measured stalling past the
  // 10 s guard and then answering in ~1 ms on the next attempt, so the probe retries
  // instead of refusing a healthy stack. Each attempt keeps its own timeout.
  let last = { skipped: false, ok: false, error: 'no attempt made' };
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const response = await fetch(`${env.musicapiBase}/internal/studio/health`, {
        headers: { 'x-internal-token': env.token },
        signal: AbortSignal.timeout(10000),
      });
      const payload = await response.json();
      last = { skipped: false, ok: response.ok && Boolean(payload.ok), payload, attempt };
      if (last.ok) return last;
    } catch (err) {
      last = { skipped: false, ok: false, error: `${err.message} (attempt ${attempt}/3)`, attempt };
    }
    if (attempt < 3) await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return last;
}

async function readPrices(client) {
  const studio = await client.call('/web-music/studio/pricing', { timeoutMs: 30000 });
  const quota = await client.call('/web-music/quota', { timeoutMs: 60000 });
  return {
    prices: {
      studio_edit: Number(studio.edit ?? 0),
      stems_2: Number(studio.stems_2 ?? 0),
      stems_12: Number(studio.stems_12 ?? 0),
      music: Number(quota.credits_per_song ?? 0),
    },
    quota,
  };
}

function costOf(op, prices) {
  return op.costKeys.reduce((total, key) => total + (Number(prices[key]) || 0), 0);
}

// ---------------------------------------------------------------------------
// Reporting
// ---------------------------------------------------------------------------

function markdown(rows, meta) {
  const lines = [];
  lines.push(`# Provider matrix run — ${meta.stamp}`);
  lines.push('');
  lines.push(`- base: ${meta.baseUrl}`);
  lines.push(`- mode: ${meta.execute ? 'execute' : 'dry-run'}`);
  lines.push(`- budget: ${meta.budget} credits · spent: ${meta.spent} · remaining: ${meta.budget - meta.spent}`);
  lines.push(`- model: ${meta.model}`);
  lines.push('');
  lines.push('| # | Operation | Endpoint | Status | Credits | Platform id | musicapi job | Provider clip | Persona | Notes |');
  lines.push('|---|---|---|---|---|---|---|---|---|---|');
  rows.forEach((row, index) => {
    const ids = row.ids || {};
    const platformId =
      ids.task_id || ids.operation_id || ids.upload_id || ids.persona_id || '';
    const note = [row.error, row.note].filter(Boolean).join(' ').replace(/\|/g, '/').slice(0, 160);
    lines.push(
      `| ${index + 1} | ${row.title} | \`${row.endpoint}\` | ${row.status} | ${row.credits} | ${platformId} | ${ids.musicapi_job_id || ''} | ${ids.provider_clip_id || ''} | ${ids.provider_persona_id || ''} | ${note} |`,
    );
  });
  lines.push('');
  return lines.join('\n');
}

function renderPlan(rows, meta) {
  console.log(`\nProvider matrix — ${meta.execute ? 'EXECUTE' : 'DRY RUN'} (${meta.model})`);
  console.log(`base   ${meta.baseUrl}`);
  console.log(`budget ${meta.budget} credits · wallet ${meta.wallet} · spent 0\n`);
  const width = Math.max(...rows.map((row) => row.title.length));
  let running = 0;
  rows.forEach((row, index) => {
    const capped = running + row.cost > meta.budget;
    running = capped ? running : running + row.cost;
    const mark = capped ? 'cap' : `${row.cost}`.padStart(3);
    console.log(
      `${String(index + 1).padStart(2)}. ${row.title.padEnd(width)}  ${mark} cr  ${row.method} ${row.endpoint}`,
    );
  });
  console.log(`\ntotal ${running} credits${running > meta.budget ? ' (would exceed cap)' : ''}`);
}

// ---------------------------------------------------------------------------
// Offline self-test — proves the helper logic and the documented arithmetic
// without touching the network. `--self-test` runs this and exits.
// ---------------------------------------------------------------------------

const SELF_TEST_PRICES = { studio_edit: 12, stems_2: 12, stems_12: 60, music: 10 };

function selfTest() {
  const failures = [];
  const check = (label, actual, expected) => {
    const ok = JSON.stringify(actual) === JSON.stringify(expected);
    if (!ok) failures.push(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
    console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}`);
  };

  console.log('callback guard');
  check('localhost rejected', Boolean(callbackBaseProblem('http://localhost:8100')), true);
  check('127.0.0.1 rejected', Boolean(callbackBaseProblem('http://127.0.0.1:8100')), true);
  check('10.x rejected', Boolean(callbackBaseProblem('http://10.0.0.5')), true);
  check('192.168.x rejected', Boolean(callbackBaseProblem('http://192.168.1.4:8100')), true);
  check('::1 rejected', Boolean(callbackBaseProblem('http://[::1]:8100')), true);
  check('empty rejected', Boolean(callbackBaseProblem('')), true);
  check('public domain accepted', callbackBaseProblem('https://matrix.trycloudflare.com'), null);
  check('public IPv4 accepted', callbackBaseProblem('http://93.184.216.34:8100'), null);

  console.log('\nper-operation cost (seeded pricing)');
  const costs = {};
  for (const op of MATRIX) costs[op.id] = costOf(op, SELF_TEST_PRICES);
  for (const [id, value] of Object.entries(costs)) console.log(`  ${id.padEnd(16)} ${value} cr`);
  const total = Object.values(costs).reduce((sum, value) => sum + value, 0);
  check('base total is 188 credits', total, 188);
  check('matrix has 14 rows (12 operations + 2 free exports)', MATRIX.length, 14);
  check('stems_2 uses the 2-track key', costs.stems_2, 12);
  check('stems_12 uses the 12-track key', costs.stems_12, 60);
  check('mashup includes its fixture generation', costs.mashup, 22);

  console.log('\nbudget guard (cap 320)');
  const capped = (budget) => {
    let spent = 0;
    const skipped = [];
    for (const op of MATRIX) {
      const cost = costOf(op, SELF_TEST_PRICES);
      if (spent + cost > budget) {
        skipped.push(op.id);
        continue;
      }
      spent += cost;
    }
    return { spent, skipped };
  };
  check('cap 320 runs everything', capped(320), { spent: 188, skipped: [] });
  // Free rows never exceed the cap, so only paid rows are ever skipped.
  check('cap 60 runs the cheap paid rows only', capped(60), {
    spent: 58,
    skipped: ['remaster', 'vocals', 'instrumental', 'replace', 'mashup', 'stems_12'],
  });
  check('cap 5 runs every free row and nothing paid', capped(5), {
    spent: 0,
    skipped: ['generate', 'bounce_upload', 'stems_2', 'cover', 'extend', 'remaster', 'vocals', 'instrumental', 'replace', 'mashup', 'stems_12'],
  });

  if (failures.length) {
    console.error(`\n${failures.length} self-test failure(s):`);
    for (const failure of failures) console.error(`  - ${failure}`);
    return 1;
  }
  console.log('\nself-test: all checks passed');
  return 0;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help) {
    process.stdout.write(usage());
    return 0;
  }
  if (opts.selfTest) return selfTest();
  if (!Number.isFinite(opts.budget) || opts.budget <= 0) {
    throw new Error('--budget <credits> is required (nothing runs without a cap)');
  }
  if (!Number.isFinite(opts.timeoutSec) || opts.timeoutSec < 30) throw new Error('--timeout must be ≥ 30 s');
  if (!Number.isFinite(opts.pollSec) || opts.pollSec < 1) throw new Error('--poll-interval must be ≥ 1 s');

  const env = readEnv();
  const configErrors = [];
  if (!env.baseUrl) configErrors.push('PLATFORM_API_BASE_URL is required');
  if (!env.token) configErrors.push('PLATFORM_STUDIO_INTERNAL_TOKEN is required');
  if (!MODELS.has(env.model)) configErrors.push(`PLATFORM_STUDIO_MODEL must be one of ${[...MODELS].join(', ')}`);
  if (configErrors.length) throw new Error(configErrors.join('; '));

  const callbackProblem = callbackBaseProblem(env.callbackBase);
  if (opts.execute && callbackProblem) {
    throw new Error(
      `refusing to execute: PLATFORM_SUNO_CALLBACK_BASE_URL ${callbackProblem}. ` +
        'Start the tunnel first (cloudflared tunnel --url http://127.0.0.1:8100) — without a public callback the provider cannot report completion.',
    );
  }
  const preconditions = [];
  preconditions.push({
    key: 'callback_public',
    ok: !callbackProblem,
    detail: callbackProblem || `${env.callbackBase} is public`,
    blocking: true,
  });

  const { accessToken, refreshToken } = await login(env);
  const client = createClient({ baseUrl: env.baseUrl, accessToken, refreshToken });

  let readiness = await client.call('/web-music/studio/readiness', { timeoutMs: 60000 });
  // The first cross-process connection to MusicAPI on this host can stall for seconds
  // (measured once at the 10 s guard, then ~1 ms on every retry), and a readiness
  // snapshot is not a load test. One negative snapshot is re-read before it can block a
  // run; a genuinely broken stack still fails twice.
  if (readiness && readiness.checks && Object.values(readiness.checks).some((ok) => !ok)) {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    readiness = await client.call('/web-music/studio/readiness', { timeoutMs: 60000 });
  }
  const checks = readiness && readiness.checks ? readiness.checks : {};
  for (const [key, ok] of Object.entries(checks)) {
    preconditions.push({ key: `readiness.${key}`, ok: Boolean(ok), detail: ok ? 'ok' : 'failed', blocking: true });
  }

  const { prices, quota } = await readPrices(client);
  const wallet = Number(quota.credits_remaining || 0);

  for (const key of ['studio_edit', 'stems_2', 'stems_12', 'music']) {
    const value = prices[key];
    const ok = Number.isFinite(value) && value > 0;
    preconditions.push({
      key: `price.${key}`,
      ok,
      detail: ok ? `${value} credits` : '0 / missing — refusing to run on a mispriced table',
      blocking: true,
    });
  }

  const musicapi = await probeMusicapi(env);
  if (!musicapi.skipped) {
    preconditions.push({
      key: 'musicapi.health',
      ok: Boolean(musicapi.ok),
      detail: musicapi.ok ? `accounts=${musicapi.payload.accounts} active=${musicapi.payload.active_accounts}` : musicapi.error || 'unhealthy',
      blocking: true,
    });
  }

  const selected = opts.only ? MATRIX.filter((op) => opts.only.includes(op.id)) : MATRIX;
  if (!selected.length) throw new Error(`--only matched no operation (known: ${MATRIX.map((op) => op.id).join(', ')})`);
  if (opts.only && !opts.only.includes('generate') && !opts.task) {
    throw new Error('--only without generate needs --task <uuid> (a successful generation to source the edits)');
  }

  const rows = selected.map((op) => ({
    id: op.id,
    title: op.title,
    method: op.method,
    endpoint: op.endpoint,
    cost: costOf(op, prices),
    provider: op.provider,
    poll: op.poll,
    status: 'planned',
    credits: 0,
    ids: {},
    evidence: {},
    error: null,
    note: null,
  }));

  const meta = {
    stamp: stamp(),
    baseUrl: env.baseUrl,
    execute: opts.execute,
    budget: opts.budget,
    model: env.model,
    wallet,
    spent: 0,
  };

  console.log('Preconditions:');
  for (const item of preconditions) {
    console.log(`  ${item.ok ? 'PASS' : 'FAIL'}  ${item.key.padEnd(32)} ${item.detail}`);
  }
  const blockingFailures = preconditions.filter((item) => !item.ok && item.blocking);

  renderPlan(rows, meta);

  if (!opts.execute) {
    console.log('\nDry run: no provider call was made. Re-run with --execute once the cap is approved.');
    if (opts.out) {
      await mkdir(opts.out, { recursive: true });
      await writeFile(path.join(opts.out, 'provider-matrix.plan.json'), JSON.stringify({ meta, prices, preconditions, rows }, null, 2));
      await writeFile(path.join(opts.out, 'provider-matrix.plan.md'), markdown(rows, meta));
    }
    if (blockingFailures.length) {
      console.error(`\n${blockingFailures.length} blocking precondition(s) not met: ${blockingFailures.map((f) => f.key).join(', ')}`);
      return 2;
    }
    if (wallet < opts.budget) {
      console.warn(`\nWallet holds ${wallet} credits, below the ${opts.budget} cap — a full run would stop early.`);
    }
    return 0;
  }

  if (blockingFailures.length) {
    console.error(`\nRefusing to execute: ${blockingFailures.map((f) => f.key).join(', ')}`);
    return 2;
  }

  // --- paid run ---------------------------------------------------------
  const state = { taskId: opts.task || null, fixtureTaskId: null, wav: null };
  if (opts.task) {
    const existing = await client.call(`/web-music/generations/${opts.task}`, { timeoutMs: 60000 });
    if (String(existing.status).toUpperCase() !== 'SUCCESS') {
      throw new Error(`--task ${opts.task} is ${existing.status}, not SUCCESS`);
    }
    rows.unshift({
      id: 'source_task',
      title: 'Reused source generation (--task)',
      method: 'GET',
      endpoint: '/web-music/generations/{task_id}',
      cost: 0,
      provider: 'n/a',
      poll: 'n/a',
      status: 'SUCCESS',
      credits: 0,
      ids: { task_id: String(opts.task) },
      evidence: { model: existing.model, title: existing.title },
      error: null,
      note: 'supplied with --task, not generated by this run',
    });
  }

  const ctx = {
    client,
    opts,
    model: env.model,
    prices,
    state,
    runTag: meta.stamp.slice(0, 19),
    log: (message) => console.log(message),
  };

  let spent = 0;
  let retriesLeft = Math.max(0, opts.retries);
  let quotaBefore = wallet;

  for (const row of rows) {
    const op = MATRIX.find((item) => item.id === row.id);
    if (!op) continue;

    if (spent + row.cost > opts.budget) {
      row.status = 'skipped_budget';
      row.note = `would take spend to ${spent + row.cost} > ${opts.budget}`;
      console.log(`\n[skip] ${row.title} — ${row.note}`);
      continue;
    }

    const started = new Date();
    console.log(`\n[run ] ${row.title} (${row.cost} credits)`);
    try {
      const result = await op.run(ctx);
      row.ids = result.ids || {};
      row.evidence = result.evidence || {};
      row.note = result.note || null;
      row.status = String((result.evidence && result.evidence.status) || 'done');
      const charged = Number((result.evidence && result.evidence.credits_charged) || 0);
      row.credits = charged > 0 ? charged : row.cost;
      spent += row.credits;
      console.log(`[ ok  ] ${row.title} → ${row.status} (${row.credits} credits)`);
    } catch (err) {
      row.status = 'error';
      row.error = String(err.message || err);
      console.log(`[fail ] ${row.title} → ${row.error}`);
      const retryable = op.costKeys.length > 0 && retriesLeft > 0 && !/Refusing|budget/i.test(row.error);
      if (retryable) {
        retriesLeft -= 1;
        console.log(`  · retrying once (${retriesLeft} retries left)`);
        try {
          const retried = await op.run(ctx);
          Object.assign(row, {
            ids: retried.ids || {},
            evidence: retried.evidence || {},
            status: String((retried.evidence && retried.evidence.status) || 'done'),
            error: null,
            note: 'retried',
          });
          row.credits = Number((retried.evidence && retried.evidence.credits_charged) || 0) || row.cost;
          spent += row.credits;
          console.log(`[ ok  ] ${row.title} after retry → ${row.status}`);
        } catch (retryErr) {
          row.error = `${row.error} | retry: ${String(retryErr.message || retryErr)}`;
        }
      }
    }
    row.finished_at = new Date().toISOString();
    row.started_at = started.toISOString();
  }

  // Reconcile the spend against the wallet so the report never under-reports.
  try {
    const after = await client.call('/web-music/quota', { timeoutMs: 60000 });
    const walletAfter = Number(after.credits_remaining || 0);
    meta.walletAfter = walletAfter;
    meta.walletDelta = quotaBefore - walletAfter;
  } catch {
    meta.walletDelta = null;
  }
  meta.spent = spent;

  const outDir = opts.out || path.join('docs', 'studio', 'reports', 'provider-matrix', `run-${meta.stamp}`);
  await mkdir(outDir, { recursive: true });
  await writeFile(path.join(outDir, 'provider-matrix.json'), JSON.stringify({ meta, prices, preconditions, rows }, null, 2));
  await writeFile(path.join(outDir, 'provider-matrix.md'), markdown(rows, meta));

  const failed = rows.filter((row) => row.status === 'error' || row.status === 'skipped_budget');
  console.log(`\nWrote ${outDir}/provider-matrix.{json,md}`);
  console.log(`Spent ${spent} credits (wallet delta ${meta.walletDelta ?? 'n/a'}). ${failed.length} row(s) not green.`);
  return failed.length === 0 ? 0 : 3;
}

main()
  .then((code) => {
    process.exitCode = code;
  })
  .catch((err) => {
    console.error(`provider-matrix: ${err.message}`);
    if (err.payload) console.error(JSON.stringify(err.payload).slice(0, 800));
    process.exitCode = 1;
  });
