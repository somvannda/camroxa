import { config } from "./config.js";
import { apiHeaders, baseHeaders, makeBrowserTokenHeader } from "./auth.js";
import { solveCaptchaForAccount } from "./captcha.js";
import { normalizeModel } from "./models.js";
import { randomUUID } from "node:crypto";

const CLERK_VERSION = "5.117.0";
const CLERK_API_VERSION = "2025-11-10";

function titleCase(s: string): string {
  return s.replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1));
}

export interface AccountCreds {
  id: string;
  clientCookie: string;
  deviceId: string;
  type?: "free" | "paid";
  /** Called when Clerk rotates the `__client` cookie so it can be persisted. */
  persistCookie?: (cookie: string) => void;
}

export interface GenerateParams {
  gptDescriptionPrompt?: string;
  prompt?: string;
  tags?: string;
  title?: string;
  negativeTags?: string;
  instrumental?: boolean;
  model?: string;
  captchaToken?: string;
  personaId?: string;
  personaModel?: "style_persona" | "voice_persona" | string;
  duration?: number;
  vocalGender?: "m" | "f" | string;
  styleWeight?: number;
  weirdnessConstraint?: number;
  audioWeight?: number;
  /** Diversity of generated results, integer 0–4 (live-verified accepted). */
  variety?: number;
  /** Base64-encoded images sent as `user_uploaded_images_b64` (legacy/ignored). */
  imagesB64?: string[];
  /** Image upload ids (from `uploadImage`) sent as `user_uploaded_image_ids`. */
  imageIds?: string[];
  /** Audio upload ids (from `createAudioUpload`) sent as `user_uploaded_audio_ids`. */
  audioIds?: string[];
  /** Suno internal task (e.g. "agentic_thinking") and create metadata. */
  task?: string;
  metadata?: Record<string, unknown>;
  /** Suno clip id used as an artist/style reference. */
  artistClipId?: string;
}

export interface SoundsParams {
  prompt: string;
  model?: string;
  loop?: boolean;
  tempo?: number | null;
  key?: string | null;
}

export interface Clip {
  id: string;
  status: string;
  title?: string;
  audio_url?: string;
  media_urls?: Array<{ url?: string; content_type?: string }>;
  [key: string]: unknown;
}

export interface BillingInfo {
  total_credits_left?: number;
  subscription_type?: string;
  accessible_features?: Array<{ name?: string }>;
  models?: Array<{
    name?: string;
    external_key?: string;
    can_use?: boolean;
    is_default_free_model?: boolean;
    is_default_model?: boolean;
    major_version?: number;
    description?: string;
  }>;
  [key: string]: unknown;
}

/**
 * A single Suno account session: mints/refreshes its own JWT and exposes the
 * same operations as the CLI core, but scoped to one account.
 */
export class SunoClient {
  private cachedJwt?: string;
  private jwtExpiresAt = 0;

  constructor(public readonly account: AccountCreds) {}

  /**
   * Capture a rotated `__client` cookie from a Clerk response and persist it,
   * so the account stays authenticated without re-entering the cookie. Clerk
   * rotates this cookie opportunistically; missing the rotation eventually
   * invalidates the session.
   */
  private captureSetCookie(res: Response): void {
    const anyHeaders = res.headers as unknown as { getSetCookie?: () => string[] };
    const raw = typeof anyHeaders.getSetCookie === "function" ? anyHeaders.getSetCookie() : [];
    const cookies: string[] = Array.isArray(raw) && raw.length
      ? raw
      : (() => { const single = res.headers.get("set-cookie"); return single ? [single] : []; })();
    for (const sc of cookies) {
      const m = sc.match(/__client=([^;]+)/);
      const next = m?.[1];
      if (next && next !== this.account.clientCookie) {
        this.account.clientCookie = next;
        try {
          this.account.persistCookie?.(next);
        } catch {
          /* persistence is best-effort */
        }
      }
    }
  }

  /** Read a JWT's `exp` claim (ms), or 0 when unparseable. */
  private decodeExpiry(jwt: string): number {
    try {
      const payload = jwt.split(".")[1];
      const json = JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as { exp?: number };
      return json.exp ? json.exp * 1000 : 0;
    } catch {
      return 0;
    }
  }

  private clerkHeaders(extra: Record<string, string> = {}): Record<string, string> {
    return {
      ...baseHeaders(),
      authorization: this.account.clientCookie,
      cookie: `__client=${this.account.clientCookie}`,
      ...extra,
    };
  }

  private async getSessionId(): Promise<string> {
    const url = `${config.clerkUrl}/v1/client?__clerk_api_version=${CLERK_API_VERSION}&_clerk_js_version=${CLERK_VERSION}`;
    const res = await fetch(url, { headers: this.clerkHeaders(), signal: AbortSignal.timeout(15_000) });
    this.captureSetCookie(res);
    if (!res.ok) throw new Error(`Clerk /client failed (${res.status}): ${await res.text()}`);
    const data = (await res.json()) as { response?: { last_active_session_id?: string } };
    const sid = data.response?.last_active_session_id;
    if (!sid) throw new Error(`Account ${this.account.id}: no active Clerk session.`);
    return sid;
  }

  private async mintJwt(sessionId: string): Promise<string> {
    const url = `${config.clerkUrl}/v1/client/sessions/${sessionId}/tokens?__clerk_api_version=${CLERK_API_VERSION}&_clerk_js_version=${CLERK_VERSION}`;
    const res = await fetch(url, {
      method: "POST",
      headers: this.clerkHeaders({ "content-type": "application/x-www-form-urlencoded" }),
      signal: AbortSignal.timeout(15_000),
    });
    this.captureSetCookie(res);
    if (!res.ok) throw new Error(`Clerk token mint failed (${res.status}): ${await res.text()}`);
    const data = (await res.json()) as { jwt?: string };
    if (!data.jwt) throw new Error("Clerk returned no jwt.");
    this.jwtExpiresAt = this.decodeExpiry(data.jwt);
    return data.jwt;
  }

  async resolveJwt(): Promise<string> {
    const stored = this.account.clientCookie?.trim() ?? "";
    // Both an access JWT (token_type "access") and the durable __client refresh
    // token are JWTs, so format alone is not enough — decode the claim.
    if (/^eyJ[\w-]*\.[\w-]+\.[\w-]+$/.test(stored)) {
      let access = true;
      try {
        const payload = JSON.parse(
          Buffer.from(stored.split(".")[1], "base64url").toString("utf8"),
        ) as Record<string, unknown>;
        access = payload["suno.com/claims/token_type"] === "access";
      } catch {
        access = true; // unknown JWT shape → treat as a one-off access token
      }
      if (access) return stored;
    }
    // Durable `__client` refresh cookie → mint a JWT from Clerk, renewing
    // proactively ~5 minutes before expiry so jobs never hit a 401.
    const expiring = this.jwtExpiresAt > 0 && Date.now() > this.jwtExpiresAt - 5 * 60_000;
    if (!this.cachedJwt || expiring) {
      this.cachedJwt = await this.mintJwt(await this.getSessionId());
    }
    return this.cachedJwt;
  }

  async refreshJwt(): Promise<string> {
    this.cachedJwt = undefined;
    this.jwtExpiresAt = 0;
    return this.resolveJwt();
  }

  private async request(path: string, init: RequestInit = {}, retryAuth = true): Promise<Response> {
    const jwt = await this.resolveJwt();
    const res = await fetch(`${config.apiUrl}${path}`, {
      ...init,
      headers: apiHeaders(jwt, this.account.deviceId, (init.headers as Record<string, string>) ?? {}),
      signal: AbortSignal.timeout(30_000),
    });
    if (retryAuth && (res.status === 401 || res.status === 403)) {
      await this.refreshJwt();
      return this.request(path, init, false);
    }
    return res;
  }

  /** Public passthrough for probe scripts (treat as internal). */
  async rawRequest(path: string, init: RequestInit = {}): Promise<Response> {
    return this.request(path, init, false);
  }

  async billingInfo(): Promise<BillingInfo> {
    const res = await this.request("/api/billing/info/");
    if (!res.ok) throw new Error(`billing/info failed (${res.status}): ${await res.text()}`);
    return (await res.json()) as BillingInfo;
  }

  async captchaRequired(): Promise<boolean> {
    const res = await this.request("/api/c/check", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ ctype: "generation" }),
    });
    if (!res.ok) return true;
    const data = (await res.json()) as { required?: boolean };
    return data.required ?? true;
  }

  async generateLyrics(prompt: string): Promise<string> {
    const res = await this.request("/api/generate/lyrics/", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    if (!res.ok) throw new Error(`generate/lyrics failed (${res.status}): ${await res.text()}`);
    const data = (await res.json()) as { id?: string };
    if (!data.id) throw new Error("No lyrics id returned.");
    return data.id;
  }

  async getLyrics(id: string): Promise<Record<string, unknown>> {
    const res = await this.request(`/api/generate/lyrics/${id}`);
    if (!res.ok) throw new Error(`lyrics/${id} failed (${res.status}): ${await res.text()}`);
    return (await res.json()) as Record<string, unknown>;
  }

  /** Solve the generation gate's Turnstile for this account via 2Captcha. */
  private async solveCaptcha(): Promise<string> {
    return solveCaptchaForAccount({ twoCaptchaKey: config.twoCaptchaKey });
  }

  /** Resolve an hCaptcha token on demand, paying 2Captcha only when required. */
  private async ensureCaptchaToken(provided?: string): Promise<string> {
    if (provided) return provided;
    try {
      if (await this.captchaRequired()) {
        return this.solveCaptcha();
      }
      return "";
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (/TWOCAPTCHA_KEY|2captcha|captcha/i.test(msg)) {
        throw new Error("captcha required: " + msg);
      }
      throw e;
    }
  }

  async generateMusic(params: GenerateParams = {}): Promise<Clip[]> {
    const token = await this.ensureCaptchaToken(params.captchaToken);

    const payload: Record<string, unknown> = {
      make_instrumental: params.instrumental ?? false,
      mv: normalizeModel(params.model) ?? config.model,
      prompt: params.prompt ?? "",
      generation_type: "TEXT",
      continue_at: null,
      continue_clip_id: null,
      task: params.task ?? null,
      token,
      gpt_description_prompt: params.gptDescriptionPrompt ?? "",
      tags: params.tags ?? "",
      title: params.title ?? "",
      negative_tags: params.negativeTags ?? "",
    };
    if (params.metadata) payload.metadata = params.metadata;
    if (params.personaId) {
      payload.persona_id = params.personaId;
      payload.artist_clip_id = params.personaId;
      payload.persona_model = params.personaModel ?? "style_persona";
    }
    if (params.duration != null) payload.duration = params.duration;
    if (params.vocalGender) payload.vocal_gender = params.vocalGender;
    if (params.styleWeight != null) payload.style_weight = params.styleWeight;
    if (params.weirdnessConstraint != null) payload.weirdness_constraint = params.weirdnessConstraint;
    if (params.audioWeight != null) payload.audio_weight = params.audioWeight;
    if (params.variety != null) payload.variety = params.variety;
    if (params.imagesB64 && params.imagesB64.length) {
      payload.user_uploaded_images_b64 = params.imagesB64;
    }
    if (params.imageIds && params.imageIds.length) {
      payload.user_uploaded_image_ids = params.imageIds;
    }
    if (params.audioIds && params.audioIds.length) {
      payload.user_uploaded_audio_ids = params.audioIds;
    }
    if (params.artistClipId) payload.artist_clip_id = params.artistClipId;

    const res = await this.request("/api/generate/v2/", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`generate/v2 failed (${res.status}): ${await res.text()}`);
    const data = (await res.json()) as { clips?: Clip[] };
    return data.clips ?? [];
  }

  async getClips(ids: string[]): Promise<Clip[]> {
    const res = await this.request(`/api/feed/?ids=${ids.join(",")}`);
    if (!res.ok) throw new Error(`feed failed (${res.status}): ${await res.text()}`);
    const data = (await res.json()) as Clip[];
    return Array.isArray(data) ? data : [];
  }

  /** Submit a clip-producing operation and return its clips. */
  private async submitClips(path: string, payload: Record<string, unknown>): Promise<Clip[]> {
    const token = await this.ensureCaptchaToken();
    if (token) payload.token = token;
    const res = await this.request(path, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`${path} failed (${res.status}): ${await res.text()}`);
    const data = (await res.json()) as Clip[] | { clips?: Clip[] };
    return Array.isArray(data) ? data : data.clips ?? [];
  }

  /** Shared remix payload shape for extend/cover (captured live). */
  private remixPayload(task: "extend" | "cover", clipId: string): Record<string, unknown> {
    return {
      task,
      generation_type: "TEXT",
      title: "",
      tags: "",
      negative_tags: "",
      mv: config.model,
      prompt: "",
      make_instrumental: false,
      user_uploaded_images_b64: null,
      metadata: {
        web_client_pathname: "/create",
        create_surface: "desktop_create_form",
        is_max_mode: false,
        create_mode: "custom",
        user_tier: "",
        create_session_token: randomUUID(),
        disable_volume_normalization: false,
        is_remix: true,
      },
      override_fields: [],
      cover_clip_id: task === "cover" ? clipId : null,
      cover_start_s: null,
      cover_end_s: null,
      persona_id: null,
      artist_clip_id: null,
      artist_start_s: null,
      artist_end_s: null,
      continue_clip_id: task === "extend" ? clipId : null,
      continued_aligned_prompt: null,
      continue_at: null,
      transaction_uuid: randomUUID(),
      token_provider: null,
    };
  }

  /** Extend an existing clip. */
  async extendMusic(clipId: string, params: { continueAt?: number } = {}): Promise<Clip[]> {
    const payload = this.remixPayload("extend", clipId);
    payload.continue_at = params.continueAt ?? 170;
    return this.submitClips("/api/generate/v2-web/", payload);
  }

  /** Cover / reinterpret a clip (SIMPLE_REMIX description mode). */
  async coverMusic(clipId: string, prompt?: string): Promise<Clip[]> {
    return this.submitClips("/api/generate/v2-web/", {
      task: "cover",
      generation_type: "SIMPLE_REMIX",
      mv: config.model,
      gpt_description_prompt: prompt ?? "",
      cover_clip_id: clipId,
      override_fields: ["prompt"],
      prompt: "",
    });
  }

  /** Stem separation. Live-verified modes:
   *  - "vocal"   → 2 tracks (Vocals + Instrumental): stem_task "two"
   *  - "stems"   → 12 tracks: stem_task "twelve"
   *  - "advanced"→ falls back to the 12-track set (single-stem selection TBD).
   *  Requires a paid plan. */
  async stems(clipId: string, mode: "vocal" | "stems" | "advanced" = "stems"): Promise<Clip[]> {
    const cfg =
      mode === "vocal"
        ? { stem_type_id: 0, stem_type_group_name: "Two", stem_task: "two" }
        : { stem_type_id: 91, stem_type_group_name: "Twelve", stem_task: "twelve" };
    return this.submitClips("/api/generate/v2-web/", {
      task: "gen_stem",
      generation_type: "TEXT",
      mv: "chirp-v3-5-b",
      prompt: "",
      tags: "",
      title: "",
      negative_tags: "",
      make_instrumental: true,
      continue_clip_id: clipId,
      ...cfg,
    });
  }

  /** Remaster a clip with a different model. */
  async remaster(clipId: string, model?: string): Promise<Clip[]> {
    const token = await this.ensureCaptchaToken();
    const payload: Record<string, unknown> = {
      clip_id: clipId,
      model_name: normalizeModel(model) ?? "chirp-flounder",
      variation_category: "normal",
    };
    if (token) payload.token = token;
    return this.submitClips("/api/generate/upsample", payload);
  }

  /** Mashup two clips together. */
  async mashup(clipIds: string[], prompt?: string): Promise<Clip[]> {
    return this.submitClips("/api/generate/v2-web/", {
      task: "mashup_condition",
      generation_type: "TEXT",
      mv: config.model,
      prompt: prompt ?? "",
      gpt_description_prompt: prompt ?? "",
      title: "",
      tags: "",
      negative_tags: "",
      mashup_clip_ids: clipIds,
      override_fields: ["prompt"],
      transaction_uuid: randomUUID(),
    });
  }

  /** Add vocals to an existing clip. */
  async addVocals(clipId: string, prompt: string): Promise<Clip[]> {
    return this.submitClips("/api/generate/v2-web/", {
      task: "overpainting",
      generation_type: "TEXT",
      mv: config.model,
      overpainting_clip_id: clipId,
      prompt,
    });
  }

  /** Add instrumental to an existing clip. */
  async addInstrumental(clipId: string, prompt: string): Promise<Clip[]> {
    return this.addVocals(clipId, prompt);
  }

  /** Replace a time section of a clip. */
  async replaceSection(
    clipId: string,
    params: {
      startS: number;
      endS: number;
      lyrics: string;
      model?: string;
      prompt?: string;
      tags?: string;
      title?: string;
      negativeTags?: string;
      vocalGender?: string;
      styleWeight?: number;
      weirdnessConstraint?: number;
      audioWeight?: number;
      personaId?: string;
      personaModel?: string;
    },
  ): Promise<Clip[]> {
    const payload: Record<string, unknown> = {
      task: "infill",
      generation_type: "TEXT",
      mv: params.model ?? config.model,
      prompt: params.lyrics,
      gpt_description_prompt: params.prompt ?? params.lyrics,
      tags: params.tags ?? "",
      title: params.title ?? "",
      negative_tags: params.negativeTags ?? "",
      continue_clip_id: clipId,
      infill_context_start_s: params.startS,
      infill_context_end_s: params.endS,
      infill_start_s: params.startS,
      infill_end_s: params.endS,
      infill_dur_s: params.endS - params.startS,
      infill_lyrics: params.lyrics,
      continued_aligned_prompt: params.lyrics,
    };
    if (params.vocalGender) payload.vocal_gender = params.vocalGender;
    if (params.styleWeight != null) payload.style_weight = params.styleWeight;
    if (params.weirdnessConstraint != null) payload.weirdness_constraint = params.weirdnessConstraint;
    if (params.audioWeight != null) payload.audio_weight = params.audioWeight;
    if (params.personaId) {
      payload.persona_id = params.personaId;
      payload.artist_clip_id = params.personaId;
      payload.persona_model = params.personaModel ?? "style_persona";
    }
    return this.submitClips("/api/generate/v2-web/", payload);
  }

  /**
   * Extend a clip using an uploaded audio file.
   * Accepts either:
   *   - uploadedClipId: clip_id returned from completing the Suno 3-step S3 upload flow, OR
   *   - audioUrl:    public URL pointing to an audio file (forward-compatibility wrapper)
   * Internally submits task: upload_extend with the params wrapper confirmed via 422.
   */
  async uploadExtendMusic(params: {
    uploadedClipId?: string;
    audioUrl?: string;
    continueAt?: number;
    prompt?: string;
    title?: string;
    tags?: string;
  }): Promise<Clip[]> {
    const continueClipId = params.uploadedClipId ?? params.audioUrl ?? "";
    if (!continueClipId) throw new Error("uploadedClipId or audioUrl is required for upload_extend.");
    return this.submitClips("/api/generate/v2-web/", {
      task: "upload_extend",
      generation_type: "TEXT",
      mv: config.model,
      params: {
        prompt: params.prompt ?? "",
        continue_clip_id: continueClipId,
        continue_at: params.continueAt ?? 170,
        continued_aligned_prompt: params.prompt ?? "",
        title: params.title ?? "",
        tags: params.tags ?? "",
      },
      override_fields: ["prompt"],
      make_instrumental: false,
      transaction_uuid: randomUUID(),
    });
  }

  /**
   * Cover / reinterpret a clip using a previously uploaded audio file as the source material.
   * Submits task: cover_infill with the params wrapper confirmed via 422.
   */
  async uploadCoverMusic(params: {
    uploadedClipId?: string;
    audioUrl?: string;
    coverStartS?: number;
    coverEndS?: number;
    prompt?: string;
    title?: string;
    tags?: string;
  }): Promise<Clip[]> {
    const coverClipId = params.uploadedClipId ?? params.audioUrl ?? "";
    if (!coverClipId) throw new Error("uploadedClipId or audioUrl is required for upload_cover.");
    return this.submitClips("/api/generate/v2-web/", {
      task: "cover_infill",
      generation_type: "TEXT",
      mv: config.model,
      prompt: params.prompt ?? "",
      make_instrumental: false,
      // Pydantic `loc` names the model, so these are flat top-level fields.
      cover_clip_id: coverClipId,
      continue_clip_id: coverClipId,
      cover_start_s: params.coverStartS ?? null,
      cover_end_s: params.coverEndS ?? null,
      title: params.title ?? "",
      tags: params.tags ?? "",
      override_fields: ["prompt"],
      transaction_uuid: randomUUID(),
    });
  }

  /** Create a voice persona from a clip. */
  async createPersona(
    clipId: string,
    name: string,
    styles?: string,
    opts?: { vocalStartS?: number; vocalEndS?: number; description?: string },
  ): Promise<unknown> {
    const token = await this.ensureCaptchaToken();
    const vocalStartS = opts?.vocalStartS ?? 0;
    const vocalEndS = opts?.vocalEndS ?? 60;
    const description = opts?.description ?? "";
    const stemRes = await this.request(`/api/clip/${clipId}/vox-stem`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ vocal_start_s: vocalStartS, vocal_end_s: vocalEndS, token }),
    });
    if (!stemRes.ok) throw new Error(`vox-stem failed (${stemRes.status}): ${await stemRes.text()}`);
    const stem = (await stemRes.json()) as { id?: string };
    // /api/clip/{id}/vox-stem returns {status:"submitted"} and processes
    // asynchronously; persona/create answers "Vocal audio is still processing"
    // until it is ready. Retry with backoff rather than guessing a fixed delay.
    let lastErr = "persona/create failed";
    for (let attempt = 0; attempt < 8; attempt++) {
      const res = await this.request("/api/persona/create/", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          root_clip_id: clipId,
          name,
          description,
          is_public: true,
          persona_type: "vox",
          vox_audio_id: stem.id,
          vocal_start_s: vocalStartS,
          vocal_end_s: vocalEndS,
          user_input_styles: styles ?? "",
          clips: [clipId],
          token,
        }),
      });
      if (res.ok) return res.json();
      const text = await res.text();
      lastErr = `persona/create failed (${res.status}): ${text}`;
      if (!/still processing|processing/i.test(text) || attempt === 7) break;
      await new Promise((r) => setTimeout(r, 5000));
    }
    throw new Error(lastErr);
  }

  /** Generate cover art for a clip. */
  async generateCoverImage(clipId: string, prompt: string): Promise<unknown> {
    const token = await this.ensureCaptchaToken();
    const res = await this.request("/api/video_gen/image/generate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt, clip_id: clipId, quantity: 2, image_gen_category: "basic", aspect_ratio: "1:1", token }),
    });
    if (!res.ok) throw new Error(`cover image failed (${res.status}): ${await res.text()}`);
    return res.json();
  }

  /** Authorize a download and return the signed clip URL for a given format. Uses 3-step flow:
   *  1. POST /api/download/authorize — unlocks download for the clip on the account
   *  2. Poll GET /api/download/clip/:id?format= until status !== "processing" (S3 transcode pipeline)
   *  3. Returns the status=ready signed `download_url` from S3 (real MP3/WAV — not encrypted placeholder)
   */
  async downloadUrl(clipId: string, format = "wav"): Promise<string> {
    const authorizeResp = await this.request("/api/download/authorize", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        item_id: clipId,
        item_type: "clip",
        format,
      }),
    }, true);
    if (!authorizeResp.ok) {
      const fallback = `${config.apiUrl}/api/download/clip/${clipId}?format=${format}`;
      if (authorizeResp.status === 401 || authorizeResp.status === 403 || authorizeResp.status === 404) {
        return fallback;
      }
      throw new Error(`download/authorize failed (${authorizeResp.status}): ${await authorizeResp.text()}`);
    }
    const maxPolls = 120;
    const pollMs = 500;
    for (let i = 0; i < maxPolls; i++) {
      const r = await this.request(
        `/api/download/clip/${clipId}?format=${encodeURIComponent(format)}`,
        {
          redirect: "manual",
          headers: { accept: "application/json,audio/*,*/*" },
        },
        true,
      );
      if (!r.ok) {
        if (r.status >= 300 && r.status < 400) {
          const loc = r.headers.get("location");
          if (loc) return loc;
        }
        await new Promise((res) => setTimeout(res, pollMs));
        continue;
      }
      const text = await r.text();
      let data: any = null;
      try { data = JSON.parse(text); } catch { data = { ok: false, raw: text }; }
      // A 200 `{ok:false}` (e.g. reason "not_authorized"/"quota_exhausted" once the
      // account's monthly download quota is spent) is a terminal denial, not a
      // "still processing" state — fail fast instead of polling for minutes.
      if (data && typeof data === "object" && data.ok === false) {
        throw new Error(
          `download/clip denied: ${data.reason ?? "unknown"}${data.message ? ` — ${data.message}` : ""}`,
        );
      }
      if (data && typeof data === "object" && (data.status === "ready" || data.status === "ok")) {
        const url = data.download_url ?? data.url ?? data.cdn_url ?? data.downloadUrl;
        if (url && typeof url === "string") return url;
      }
      if (data && typeof data === "object" && (data.status === "error" || data.status === "failed")) {
        throw new Error(`download/clip status=${data.status} body=${text.slice(0, 300)}`);
      }
      await new Promise((res) => setTimeout(res, pollMs));
    }
    return `${config.apiUrl}/api/download/clip/${clipId}?format=${format}`;
  }

  /** Download a clip as a Buffer in the requested format. Uses downloadUrl then fetches bytes. */
  async downloadBuffer(clipId: string, format: "mp3" | "wav" = "mp3"): Promise<{ buffer: Buffer; contentType: string }> {
    const ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36";
    const url = await this.downloadUrl(clipId, format);
    const resp = await fetch(url, {
      redirect: "follow",
      headers: {
        "user-agent": ua,
        accept: format === "wav" ? "audio/wav,audio/*,*/*;q=0.8" : "audio/mpeg,audio/mp3,audio/*,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
      },
      // Generous cap: buffers a whole audio file, so allow a slow transfer.
      signal: AbortSignal.timeout(120_000),
    });
    if (!resp.ok) throw new Error(`downloadBuffer upstream ${resp.status}: ${await resp.text()}`);
    const ct = resp.headers.get("content-type") || (format === "wav" ? "audio/wav" : "audio/mpeg");
    const arr = await resp.arrayBuffer();
    return { buffer: Buffer.from(arr), contentType: ct };
  }

  /**
   * Fetch the DRM license for a clip from Suno's own license server
   * (`POST /api/mango/rights`). The returned `key`/`iv` are wrapped with a key
   * derived from the caller's auth token; `glt` is only present for anonymous
   * playback. `clipIds` are decrypted client-side (see `sunoAudio.ts`).
   */
  async mangoRights(
    contentId: string,
    contentType = "clip",
  ): Promise<{ key: string; iv: string; glt?: string }> {
    const res = await this.request("/api/mango/rights", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ content_params: { content_id: contentId, content_type: contentType } }),
    });
    if (!res.ok) throw new Error(`mango/rights failed (${res.status}): ${await res.text()}`);
    return (await res.json()) as { key: string; iv: string; glt?: string };
  }

  /** Generate a "Sounds" clip (sound effect / sample) via the v2-web endpoint. */
  async generateSounds(params: SoundsParams): Promise<Clip[]> {
    const token = await this.ensureCaptchaToken();
    const payload: Record<string, unknown> = {
      mv: normalizeModel(params.model) ?? config.model,
      prompt: "",
      title: titleCase(params.prompt),
      tags: params.prompt,
      negative_tags: "",
      make_instrumental: true,
      transaction_uuid: randomUUID(),
      metadata: {
        web_client_pathname: "/create",
        create_surface: "web",
        is_max_mode: false,
        create_mode: "custom",
        user_tier: "free",
        create_session_token: randomUUID(),
        disable_volume_normalization: false,
        sound_configs: {
          user_tempo: params.tempo ?? null,
          user_key: params.key ?? null,
          user_loop: params.loop ?? false,
        },
      },
    };
    if (token) payload.token = token;
    return this.submitClips("/api/generate/v2-web/", payload);
  }

  /** Poll clips until complete/error. */
  async pollClips(ids: string[], timeoutMs = 300_000, intervalMs = 5_000): Promise<Clip[]> {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const clips = await this.getClips(ids);
      if (clips.length > 0 && clips.every((c) => c.status === "complete" || c.status === "error")) {
        return clips;
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }
    throw new Error("Timed out waiting for clip completion.");
  }

  // =========================================
  // Upload 3-step flow
  // =========================================

  /** Step 1: create audio upload session → S3 presigned policy + fields.
   *  Confirmed via probe round 9: POST /api/uploads/audio/ with {extension, upload_type}
   *  Returns {id: UUID, url: S3 base URL, fields: multipart form fields for S3 PUT}
   */
  async createAudioUpload(params: {
    extension: string;
    uploadType?: "file_upload" | "voice_recording" | "audio_recording" | "song_demo";
    lastUploadId?: string;
  }): Promise<{ id: string; url: string; fields: Record<string, string>; is_file_uploaded?: boolean }> {
    const token = await this.ensureCaptchaToken();
    const body: Record<string, unknown> = {
      extension: params.extension.replace(/^\./, ""),
      upload_type: params.uploadType ?? "file_upload",
    };
    if (params.lastUploadId) body.last_upload_id = params.lastUploadId;
    if (token) body.token = token;
    const res = await this.request("/api/uploads/audio/", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`createAudioUpload failed (${res.status}): ${await res.text()}`);
    return (await res.json()) as { id: string; url: string; fields: Record<string, string>; is_file_uploaded?: boolean };
  }

  /** Step 3: register / finish upload (after S3 multipart PUT succeeded).
   *  Suno's Pydantic `loc` names the model, not a nesting level, so the fields are
   *  flat top-level: {upload_type, upload_filename, upload_title}. */
  async registerAudioUpload(
    uploadId: string,
    params: { uploadType: string; uploadFilename: string; uploadTitle?: string }
  ): Promise<unknown> {
    const token = await this.ensureCaptchaToken();
    const body: Record<string, unknown> = {
      upload_type: params.uploadType,
      upload_filename: params.uploadFilename,
      upload_title: params.uploadTitle ?? "",
    };
    if (token) body.token = token;
    const res = await this.request(`/api/uploads/audio/${uploadId}/upload-finish/`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`registerAudioUpload failed (${res.status}): ${await res.text()}`);
    return res.json();
  }

  /** Poll an upload session's processing status (step 4) until processing gives us a usable clip_id.
   *  Browser capture: GET /api/uploads/audio/{id}/ returns {id, status, title, copyright_muted}
   */
  async getAudioUploadStatus(
    uploadId: string,
    timeoutMs = 60_000,
    intervalMs = 2_000
  ): Promise<{ id: string; status: string; title?: string; copyright_muted?: boolean; clip_id?: string }> {
    const deadline = Date.now() + timeoutMs;
    let last: { id: string; status: string; title?: string; copyright_muted?: boolean; clip_id?: string } | undefined;
    while (Date.now() < deadline) {
      const res = await this.request(`/api/uploads/audio/${uploadId}/`, { method: "GET" });
      if (res.ok) {
        last = (await res.json()) as {
          id: string;
          status: string;
          title?: string;
          copyright_muted?: boolean;
          clip_id?: string;
        };
        const s = last.status ?? "";
        if (s.includes("complete") || s.includes("passed_audio_processing") || s.includes("ready") || last.clip_id) return last;
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }
    if (last) return last;
    throw new Error(`Timed out waiting for upload ${uploadId} to process.`);
  }

  /** Single-shot upload-status read for HTTP status endpoints. Unlike
   *  getAudioUploadStatus it does NOT poll, so a bogus id returns promptly
   *  instead of holding the request open for up to a minute. Callers that need
   *  to wait for processing should keep using getAudioUploadStatus. */
  async fetchAudioUploadStatus(
    uploadId: string,
  ): Promise<{ id: string; status: string; title?: string; copyright_muted?: boolean; clip_id?: string }> {
    const res = await this.request(`/api/uploads/audio/${uploadId}/`, { method: "GET" });
    if (!res.ok) throw new Error(`getAudioUploadStatus failed (${res.status}): ${await res.text()}`);
    return (await res.json()) as {
      id: string;
      status: string;
      title?: string;
      copyright_muted?: boolean;
      clip_id?: string;
    };
  }

  /** Full audio upload: create session → POST bytes to Suno's S3 → register →
   *  poll for the processed clip id. Returns a clip id usable as a persona/task
   *  root. Mirrors uploadImage but for audio (voice recordings / song demos). */
  async uploadAudio(
    bytes: Buffer,
    extension = "wav",
    uploadType: "voice_recording" | "file_upload" | "song_demo" = "voice_recording",
  ): Promise<string> {
    const ext = extension.replace(/^\./, "").toLowerCase() || "wav";
    const session = await this.createAudioUpload({ extension: ext, uploadType });
    const contentType = session.fields["Content-Type"] || `audio/${ext}`;
    const form = new FormData();
    for (const [k, v] of Object.entries(session.fields)) form.append(k, v);
    form.append("file", new Blob([new Uint8Array(bytes)], { type: contentType }), `audio.${ext}`);
    const up = await fetch(session.url, { method: "POST", body: form });
    if (!up.ok && up.status !== 204) {
      throw new Error(`audio S3 upload failed (${up.status}): ${await up.text()}`);
    }
    await this.registerAudioUpload(session.id, { uploadType, uploadFilename: `audio.${ext}` });
    const status = await this.getAudioUploadStatus(session.id);
    return status.clip_id || session.id;
  }

  // =========================================
  // Image upload (cover art / reference)
  // =========================================

  /** Step 1: create an image upload session → { id, url, fields }.
   *  Confirmed live: POST /api/uploads/image/ with { extension } (e.g. "jpg"). */
  async createImageUpload(
    extension: string,
  ): Promise<{ id: string; url: string; fields: Record<string, string> }> {
    const res = await this.request("/api/uploads/image/", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ extension: extension.replace(/^\./, "") }),
    });
    if (!res.ok) throw new Error(`createImageUpload failed (${res.status}): ${await res.text()}`);
    return (await res.json()) as { id: string; url: string; fields: Record<string, string> };
  }

  /** Full 2-step image upload: POST the bytes against Suno's S3 policy and return
   *  the image id that goes in `user_uploaded_image_ids`. */
  async uploadImage(bytes: Buffer, extension = "jpg"): Promise<string> {
    const ext = extension.replace(/^\./, "").toLowerCase();
    const { id, url, fields } = await this.createImageUpload(ext);
    const contentType = fields["Content-Type"] || `image/${ext}`;
    const form = new FormData();
    for (const [k, v] of Object.entries(fields)) form.append(k, v);
    form.append("file", new Blob([new Uint8Array(bytes)], { type: contentType }), `image.${ext}`);
    const up = await fetch(url, { method: "POST", body: form });
    if (!up.ok && up.status !== 204) {
      throw new Error(`image S3 upload failed (${up.status}): ${await up.text()}`);
    }
    // Confirm the upload with Suno (required — without this the generate call
    // rejects the image as "not uploaded successfully").
    const finish = await this.request(`/api/uploads/image/${id}/upload-finish/`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!finish.ok) {
      throw new Error(`image upload-finish failed (${finish.status}): ${await finish.text()}`);
    }
    return id;
  }

  // =========================================
  // Detail endpoints (GET, no captcha usually)
  // =========================================

  /**
   * GET /api/clip/{clip_id} — Suno's canonical per-clip record (metadata,
   * media_urls, image_url, video_url, ownership). This is the durable read
   * source: the old `/api/download/clip/{id}` route is gated by a per-account
   * monthly download quota and returns HTTP 200 `{ok:false, reason:"not_authorized"}`
   * once that quota is spent, so it can no longer back a detail API.
   */
  async getClipObject(clipId: string): Promise<Record<string, unknown>> {
    const res = await this.request(`/api/clip/${clipId}`, { method: "GET" });
    if (!res.ok) throw new Error(`getClipObject failed (${res.status}): ${await res.text()}`);
    const data = await res.json();
    return data && typeof data === "object" ? (data as Record<string, unknown>) : {};
  }

  /** Clip detail — the full clip record. */
  async getClipDetail(clipId: string): Promise<unknown> {
    return this.getClipObject(clipId);
  }

  /**
   * Suno's own word-level alignment for a generated clip —
   * `GET /api/gen/{clip_id}/aligned_lyrics`, the karaoke data its player uses.
   * This is exactly what sunoapi.org resells as `alignedWords` (their `palign`
   * is Suno's `p_align`), so it is language-agnostic and needs no local ASR.
   * Returns a flat word list in Suno's shape
   * (`{word,success,start_s,end_s,p_align}`); `[]` when the clip has none
   * (e.g. an instrumental).
   */
  async getAlignedLyrics(clipId: string): Promise<Array<Record<string, unknown>>> {
    const res = await this.request(`/api/gen/${clipId}/aligned_lyrics`, { method: "GET" });
    if (res.status === 404) return [];
    if (!res.ok) throw new Error(`getAlignedLyrics failed (${res.status}): ${await res.text()}`);
    const body = (await res.json()) as { data?: unknown };
    const segments = Array.isArray(body.data) ? body.data : [];
    const words: Array<Record<string, unknown>> = [];
    for (const segment of segments) {
      if (!Array.isArray(segment)) continue;
      for (const item of segment) {
        if (item && typeof item === "object") words.push(item as Record<string, unknown>);
      }
    }
    return words;
  }

  /**
   * Lyrics detail, derived from the clip record's `metadata.prompt` (the
   * lyric/prompt text captured at generation). Suno exposes no standalone
   * lyrics route — `/api/clip/{id}/lyrics` is a plain 404 — so the clip record
   * is the only source. Word-level alignment isn't available from Suno and is
   * returned empty here rather than fabricated.
   *
   * This is the *fallback* path: when the LRC microservice is enabled,
   * `runTimestampedLyricsJob` in `server.ts` intercepts the job and aligns the
   * clip's audio against this lyric text (`musicapi/lrc-service`) to emit real
   * line-level LRC. This method answers with plain lyrics only when alignment
   * is disabled/unavailable.
   */
  async lyricsDetail(clipId: string): Promise<unknown> {
    const clip = await this.getClipObject(clipId);
    const meta = (clip.metadata ?? {}) as Record<string, unknown>;
    const lyrics = typeof meta.prompt === "string" ? meta.prompt : "";
    return { ...clip, lyrics, aligned_words: [] };
  }

  /** WAV download detail endpoint — same as downloadUrl but exposed as detail for parity. */
  async wavDetail(clipId: string, format = "wav"): Promise<{ clip_id: string; format: string; download_url: string }> {
    const url = await this.downloadUrl(clipId, format);
    return { clip_id: clipId, format, download_url: url };
  }

  /** Stems (vocal-separation) detail — `/api/clip/{id}/stems` is still served. */
  async stemsDetail(clipId: string): Promise<unknown> {
    const res = await this.request(`/api/clip/${clipId}/stems`, { method: "GET" });
    if (res.ok) return res.json();
    return this.getClipObject(clipId);
  }

  /** Video/MP4 detail — the clip record carries `video_url` once a video exists. */
  async videoDetail(clipId: string): Promise<unknown> {
    return this.getClipObject(clipId);
  }

  /** Cover image detail — the clip record carries `image_url`/`image_large_url`. */
  async coverDetail(clipId: string): Promise<unknown> {
    return this.getClipObject(clipId);
  }

  /**
   * Subtitle/captions detail — Suno exposes no captions route; derive from clip lyrics.
   *
   * `subtitle` is empty here; when alignment is enabled, the timestamped-lyrics
   * pipeline produces LRC that can be converted to SRT via `lrcToSrt`.
   */
  async subtitleDetail(clipId: string): Promise<unknown> {
    const clip = await this.getClipObject(clipId);
    const meta = (clip.metadata ?? {}) as Record<string, unknown>;
    const lyrics = typeof meta.prompt === "string" ? meta.prompt : "";
    return { ...clip, lyrics, subtitle: "" };
  }

  /** Recovery audio detail — no dedicated Suno route; return the clip record. */
  async recoveryDetail(clipId: string): Promise<unknown> {
    return this.getClipObject(clipId);
  }

  /** MP4 task detail — no dedicated Suno route; return the clip record. */
  async mp4Detail(clipIdOrTaskId: string): Promise<unknown> {
    return this.getClipObject(clipIdOrTaskId);
  }

  /** MIDI detail — no dedicated Suno route; return the clip record. */
  async midiDetail(clipIdOrTaskId: string): Promise<unknown> {
    return this.getClipObject(clipIdOrTaskId);
  }

  // =========================================
  // Recovery audio, MP4/video, Boost, MIDI, Voice ops
  // =========================================

  /** Generate recovery audio for a clip (placeholder; falls back to clip detail if separate task not yet discovered). */
  async generateRecoveryAudio(clipId: string, prompt = ""): Promise<Clip[]> {
    const text = prompt && prompt.trim() ? prompt : "recovery audio, clean vocals";
    return this.submitClips("/api/generate/v2-web/", {
      task: "fixed_infill",
      mv: config.model,
      generation_type: "TEXT",
      prompt: text,
      gpt_description_prompt: text,
      tags: "",
      title: "Recovery audio",
      negative_tags: "",
      params: {
        prompt: text,
        continue_clip_id: clipId,
        title: "Recovery audio",
      },
      override_fields: ["prompt"],
      transaction_uuid: randomUUID(),
    });
  }

  /** Generate a music video (MP4) for a clip. Mirrors cover_image pattern. */
  async generateMP4(
    clipId: string,
    params: { prompt?: string; quantity?: number; aspectRatio?: string } = {}
  ): Promise<unknown> {
    const token = await this.ensureCaptchaToken();
    const res = await this.request("/api/video_gen/mp4/generate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        clip_id: clipId,
        prompt: params.prompt ?? "",
        quantity: params.quantity ?? 1,
        aspect_ratio: params.aspectRatio ?? "16:9",
        token,
      }),
    });
    if (!res.ok) {
      // Fallback: try video_gen/image/generate path sibling pattern if mp4 not yet live.
      const fb = await this.request("/api/video_gen/image/generate", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          prompt: params.prompt ?? "music video",
          clip_id: clipId,
          quantity: params.quantity ?? 1,
          image_gen_category: "basic",
          aspect_ratio: params.aspectRatio ?? "16:9",
          token,
        }),
      });
      if (!fb.ok) throw new Error(`generateMP4 failed (${res.status}): ${await res.text()}`);
      return fb.json();
    }
    return res.json();
  }

  /** Boost music style / re-style a clip. Uses v2-web infill task. */
  async boostStyle(
    clipId: string,
    stylePrompt: string,
    params: { startS?: number; endS?: number } = {}
  ): Promise<Clip[]> {
    const startS = params.startS ?? 0;
    const endS = params.endS ?? 60;
    // Top-level infill shape (matches replaceSection, which Suno accepts); the
    // nested `params` wrapper was rejected with a `params.prompt` 422.
    return this.submitClips("/api/generate/v2-web/", {
      task: "infill",
      generation_type: "TEXT",
      mv: config.model,
      prompt: stylePrompt,
      gpt_description_prompt: stylePrompt,
      tags: "",
      title: `Boost: ${stylePrompt.slice(0, 40)}`,
      negative_tags: "",
      continue_clip_id: clipId,
      infill_context_start_s: startS,
      infill_context_end_s: endS,
      infill_start_s: startS,
      infill_end_s: endS,
      infill_dur_s: Math.max(1, endS - startS),
      infill_lyrics: stylePrompt,
      continued_aligned_prompt: stylePrompt,
      override_fields: ["prompt"],
      transaction_uuid: randomUUID(),
    });
  }

  /** Generate MIDI for a clip. Uses v2-web infill task pattern. */
  async generateMIDI(clipId: string, prompt = "instrumental midi arrangement"): Promise<Clip[]> {
    return this.submitClips("/api/generate/v2-web/", {
      task: "infill",
      mv: config.model,
      generation_type: "TEXT",
      params: {
        prompt,
        continue_clip_id: clipId,
        title: "MIDI Arrangement",
        tags: "midi, instrumental, score",
      },
      override_fields: ["prompt"],
      make_instrumental: true,
      transaction_uuid: randomUUID(),
    });
  }

  // =========================================
  // Suno Voice 6 operations (phrase / validate / record / generate / apply + 1 more for 6)
  // =========================================

  /** Voice op 1: phrase — fetch the validation phrase the user must record. */
  async voicePhrase(_prompt?: string): Promise<{ phrase_id: string; phrase_text: string }> {
    const res = await this.request("/api/voice-verification/phrase", { method: "GET" });
    if (!res.ok) throw new Error(`voice phrase failed (${res.status}): ${await res.text()}`);
    return (await res.json()) as { phrase_id: string; phrase_text: string };
  }

  /**
   * Upload audio for a voice flow and WAIT for `status:"complete"` before
   * returning the upload session id. `uploadAudio` returns as soon as
   * `passed_audio_processing`, which is too early: `processed_clip/voice-vox-stem`
   * then answers `{"detail":"Upload not found"}`.
   */
  async uploadForVoice(bytes: Buffer, uploadType: "voice_recording" | "audio_recording" = "voice_recording"): Promise<string> {
    const session = await this.createAudioUpload({ extension: "mp3", uploadType });
    const contentType = session.fields["Content-Type"] || "audio/mpeg";
    const form = new FormData();
    for (const [k, v] of Object.entries(session.fields)) form.append(k, v);
    form.append("file", new Blob([new Uint8Array(bytes)], { type: contentType }), "voice.mp3");
    const up = await fetch(session.url, { method: "POST", body: form });
    if (!up.ok && up.status !== 204) throw new Error(`audio S3 upload failed (${up.status}): ${await up.text()}`);
    await this.registerAudioUpload(session.id, { uploadType, uploadFilename: "voice.mp3" });
    for (let i = 0; i < 30; i++) {
      const st = await this.fetchAudioUploadStatus(session.id).catch(() => null);
      if (st?.status === "complete") break;
      await new Promise((r) => setTimeout(r, 2000));
    }
    return session.id;
  }

  /**
   * Voice op 2: validate. Suno's custom-voice workflow exposes the validation
   * phrase via `GET /api/voice-verification/phrase`; the actual verification
   * (comparing the spoken phrase against the singing recording) happens later at
   * `POST /api/voice-verification/` with both recording ids and the phrase id.
   * We surface the phrase-generation step here.
   */
  async voiceValidate(
    params: { uploadId?: string; audioUrl?: string; voiceUrl?: string; language?: string } = {},
  ): Promise<Record<string, unknown>> {
    const phrase = await this.voicePhrase();
    const out: Record<string, unknown> = { ...phrase };
    // Best-effort: extract the source vocal stem so a later voice/generate can
    // verify against it. This needs a Voice-entitled (Premier) account; when it
    // is unavailable we still return the phrase and record the reason.
    const sourceUrl = params.voiceUrl ?? params.audioUrl;
    try {
      let uploadId = params.uploadId;
      if (!uploadId && sourceUrl) {
        const resp = await fetch(sourceUrl, { signal: AbortSignal.timeout(60_000) });
        if (!resp.ok) throw new Error(`Could not download the source recording (${resp.status}).`);
        uploadId = await this.uploadForVoice(Buffer.from(await resp.arrayBuffer()));
      }
      if (uploadId) {
        const stem = await this.voiceVoxStem(uploadId);
        const vr = stem.voice_recording_id ?? stem.id;
        if (typeof vr === "string") out.voice_recording_id = vr;
        else out.voice_recording_error = "voice-vox-stem returned no recording id (Voice entitlement required).";
      }
    } catch (e) {
      out.voice_recording_error = e instanceof Error ? e.message : String(e);
    }
    return out;
  }

  /**
   * Custom Voice step: extract the vocal stem from a source recording upload
   * (`upload_id` from the audio upload flow) — the `voice_recording_id` used by
   * voice verification. Requires a Voice-entitled (Premier) account.
   */
  async voiceVoxStem(uploadId: string, recordingType?: "verification"): Promise<Record<string, unknown>> {
    const body: Record<string, unknown> = { upload_id: uploadId };
    if (recordingType) body.recording_type = recordingType;
    const res = await this.request("/api/processed_clip/voice-vox-stem", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`voice-vox-stem failed (${res.status}): ${await res.text()}`);
    return (await res.json()) as Record<string, unknown>;
  }

  /** Poll a voice verification by id (`GET /api/voice-verification/{id}`). */
  async getVoiceVerification(verificationId: string): Promise<Record<string, unknown>> {
    const res = await this.request(`/api/voice-verification/${verificationId}`);
    if (!res.ok) throw new Error(`voice-verification get failed (${res.status}): ${await res.text()}`);
    return (await res.json()) as Record<string, unknown>;
  }

  /**
   * Custom Voice step: verify the user's spoken recording of the validation
   * phrase against the source voice. `POST /api/voice-verification/` takes the
   * three ids FLAT (not nested under `spec`). Requires a Voice-entitled account.
   */
  async verifyVoice(params: {
    phraseId: string;
    voiceRecordingId: string;
    verificationRecordingId: string;
  }): Promise<Record<string, unknown>> {
    const res = await this.request("/api/voice-verification/", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        voice_recording_id: params.voiceRecordingId,
        verification_recording_id: params.verificationRecordingId,
        phrase_id: params.phraseId,
      }),
    });
    if (!res.ok) throw new Error(`voice-verification failed (${res.status}): ${await res.text()}`);
    return (await res.json()) as Record<string, unknown>;
  }

  /** Voice op 3: record — alias for createAudioUpload(uploadType: voice_recording), returns session same shape. */
  async voiceRecord(extension = "wav"): Promise<{ id: string; url: string; fields: Record<string, string> }> {
    return this.createAudioUpload({ extension, uploadType: "voice_recording" });
  }

  /** Voice op 4: generate — create a voice persona / clone (reuses createPersona). */
  async voiceGenerate(params: {
    clipId: string;
    name: string;
    styles?: string;
    description?: string;
    vocalStartS?: number;
    vocalEndS?: number;
  }): Promise<unknown> {
    return this.createPersona(params.clipId, params.name, params.styles, {
      vocalStartS: params.vocalStartS,
      vocalEndS: params.vocalEndS,
      description: params.description,
    });
  }

  /** Voice op 5: apply — generate new music using a persona / voice clone. */
  async voiceApply(params: {
    personaId?: string;
    clipId?: string;
    prompt?: string;
    title?: string;
    tags?: string;
    model?: string;
    personaModel?: string;
  }): Promise<Clip[]> {
    const persona = params.personaId ?? params.clipId ?? "";
    if (!persona) throw new Error("personaId or clipId required for voiceApply.");
    // Applying a voice/persona is a normal generation with persona_id + persona_model
    // (the same `/api/generate/v2/` payload music generation uses). `voice_persona`
    // for a Suno Voice id, `style_persona` for a Generate Persona id.
    return this.generateMusic({
      personaId: persona,
      personaModel: params.personaModel ?? "voice_persona",
      prompt: params.prompt,
      title: params.title,
      tags: params.tags,
      model: params.model,
    });
  }

  /** Voice op 6: extend using persona / vox_extend — use vox task pattern. */
  async voiceExtend(params: {
    personaId?: string;
    clipId?: string;
    continueAt?: number;
    prompt?: string;
    personaModel?: string;
  }): Promise<Clip[]> {
    const clip = params.clipId ?? "";
    if (!clip) throw new Error("clipId is required to extend — a persona has no audio to continue.");
    // Extend an existing clip; attach the persona/voice so the continuation keeps it.
    const payload = this.remixPayload("extend", clip);
    payload.prompt = params.prompt ?? "";
    payload.continue_at = params.continueAt ?? 170;
    if (params.personaId) {
      payload.persona_id = params.personaId;
      payload.artist_clip_id = params.personaId;
      payload.persona_model = params.personaModel ?? "voice_persona";
    }
    return this.submitClips("/api/generate/v2-web/", payload);
  }
}
