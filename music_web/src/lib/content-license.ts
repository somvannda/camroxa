import { musicAuthFetch } from '@/lib/auth-fetch';
import { decryptModuleHash } from '@/lib/camxora-decrypt';

const DEVICE_STORE = 'camxora-playback';
const DEVICE_KEY = 'device_public_id';

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DEVICE_STORE, 1);
    req.onupgradeneeded = () => {
      req.result.createObjectStore('kv');
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function readStoredDeviceId(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const existing = window.localStorage.getItem(DEVICE_KEY);
    return existing && existing.length >= 8 ? existing : null;
  } catch {
    return null;
  }
}

function writeStoredDeviceId(id: string) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(DEVICE_KEY, id);
  } catch {
    /* private mode may block storage */
  }
}

export async function getOrCreateDevicePublicId(): Promise<string> {
  const fromStorage = readStoredDeviceId();
  try {
    const db = await openDb();
    const existing = await new Promise<string | undefined>((resolve, reject) => {
      const tx = db.transaction('kv', 'readonly');
      const req = tx.objectStore('kv').get(DEVICE_KEY);
      req.onsuccess = () => resolve(req.result as string | undefined);
      req.onerror = () => reject(req.error);
    });
    if (existing && existing.length >= 8) {
      db.close();
      writeStoredDeviceId(existing);
      return existing;
    }
    const created = fromStorage || crypto.randomUUID();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction('kv', 'readwrite');
      tx.objectStore('kv').put(created, DEVICE_KEY);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    db.close();
    writeStoredDeviceId(created);
    return created;
  } catch {
    if (fromStorage) return fromStorage;
    const created = crypto.randomUUID();
    writeStoredDeviceId(created);
    return created;
  }
}

export type LicenseSession = {
  token: string;
  ready: boolean;
  package_status: string;
  content_key: string | null;
  segment_url: string;
  lane: string;
  ttl_seconds: number;
  decrypt_module_hash: string;
  subject_type: string;
  subject_id: string;
  variant: string;
  session_bind?: string;
};

export async function registerPlaybackDevice(): Promise<string> {
  const devicePublicId = await getOrCreateDevicePublicId();
  const response = await musicAuthFetch('/api/v1/web-music/licenses/devices/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_public_id: devicePublicId, platform: 'music_web' }),
  });
  if (!response.ok) {
    throw new Error(`Device register failed: ${response.status}`);
  }
  return devicePublicId;
}

function inferPlaySource(): string {
  if (typeof window === 'undefined') return 'unknown';
  const path = window.location.pathname;
  if (path.startsWith('/explore')) return 'explore';
  if (path.startsWith('/search')) return 'search';
  if (path.startsWith('/genres')) return 'genre';
  if (path.startsWith('/artists')) return 'artist';
  if (path.startsWith('/albums')) return 'album';
  if (path.startsWith('/playlists')) return 'playlist';
  if (path.startsWith('/library')) return 'library';
  if (path.startsWith('/create')) return 'create';
  if (path === '/') return 'home';
  return 'unknown';
}

function inferSearchQuery(): string | undefined {
  if (typeof window === 'undefined') return undefined;
  return new URLSearchParams(window.location.search).get('q')?.trim() || undefined;
}

export async function createLicenseSession(input: {
  subjectType: 'stream_track' | 'suno_task';
  subjectId: string;
  variant?: 'ok' | 'alt';
}): Promise<LicenseSession> {
  const devicePublicId = await registerPlaybackDevice();
  const wasmHash = await decryptModuleHash();
  const response = await musicAuthFetch('/api/v1/web-music/licenses/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      device_public_id: devicePublicId,
      subject_type: input.subjectType,
      subject_id: input.subjectId,
      variant: input.variant ?? 'ok',
      purpose: 'play',
      wasm_hash: wasmHash,
      play_source: inferPlaySource(),
      search_query: inferSearchQuery(),
    }),
  });
  if (!response.ok) {
    throw new Error(`License session failed: ${response.status}`);
  }
  return response.json() as Promise<LicenseSession>;
}

export async function sendLicenseHeartbeat(input: {
  token: string;
  event?: string;
  bytesServed?: number;
  positionSeconds?: number;
  playbackRate?: number;
  seq?: number;
  sessionBind?: string;
}): Promise<void> {
  await musicAuthFetch('/api/v1/web-music/licenses/heartbeat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      token: input.token,
      event: input.event ?? 'heartbeat',
      bytes_served: input.bytesServed ?? 0,
      position_seconds: input.positionSeconds ?? 0,
      playback_rate: input.playbackRate ?? 1,
      seq: input.seq ?? 0,
      session_bind: input.sessionBind,
    }),
  });
}

export function reportPlaybackTrace(input: {
  token?: string | null;
  event: 'play_start' | 'play_session' | 'play_path' | 'play_chunks' | 'play_decode' | 'play_ok' | 'play_error';
  detail?: string;
}): void {
  void musicAuthFetch('/api/v1/web-music/licenses/client-trace', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      token: input.token || undefined,
      event: input.event,
      detail: (input.detail || '').slice(0, 500) || undefined,
    }),
  }).catch(() => undefined);
}

export class SegmentOutOfRangeError extends Error {
  constructor() {
    super('Segment out of range');
    this.name = 'SegmentOutOfRangeError';
  }
}

export type EncryptedChunk = {
  data: ArrayBuffer;
  chunkCount: number | null;
};

export async function fetchEncryptedChunkRecord(
  segmentUrl: string,
  chunk: number,
  signal?: AbortSignal,
): Promise<EncryptedChunk> {
  const url = `${segmentUrl}${segmentUrl.includes('?') ? '&' : '?'}chunk=${chunk}`;
  const response = await musicAuthFetch(url, signal ? { signal } : {});
  if (response.status === 404) {
    throw new SegmentOutOfRangeError();
  }
  if (!response.ok) {
    throw new Error(`Segment fetch failed: ${response.status}`);
  }
  const countRaw = response.headers.get('X-Camxora-Chunk-Count');
  const parsed = countRaw ? Number(countRaw) : NaN;
  return {
    data: await response.arrayBuffer(),
    chunkCount: Number.isFinite(parsed) && parsed > 0 ? parsed : null,
  };
}

export async function fetchEncryptedChunk(segmentUrl: string, chunk: number): Promise<ArrayBuffer> {
  const record = await fetchEncryptedChunkRecord(segmentUrl, chunk);
  return record.data;
}
