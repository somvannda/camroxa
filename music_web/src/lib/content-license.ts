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

export async function getOrCreateDevicePublicId(): Promise<string> {
  const db = await openDb();
  const existing = await new Promise<string | undefined>((resolve, reject) => {
    const tx = db.transaction('kv', 'readonly');
    const req = tx.objectStore('kv').get(DEVICE_KEY);
    req.onsuccess = () => resolve(req.result as string | undefined);
    req.onerror = () => reject(req.error);
  });
  if (existing && existing.length >= 8) {
    db.close();
    return existing;
  }
  const created = crypto.randomUUID();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction('kv', 'readwrite');
    tx.objectStore('kv').put(created, DEVICE_KEY);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
  return created;
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

export async function fetchEncryptedChunk(segmentUrl: string, chunk: number): Promise<ArrayBuffer> {
  const url = `${segmentUrl}${segmentUrl.includes('?') ? '&' : '?'}chunk=${chunk}`;
  const response = await musicAuthFetch(url);
  if (!response.ok) {
    throw new Error(`Segment fetch failed: ${response.status}`);
  }
  return response.arrayBuffer();
}
