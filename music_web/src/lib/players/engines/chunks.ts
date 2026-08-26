import { decryptCamxoraChunk } from '@/lib/camxora-decrypt';
import {
  fetchEncryptedChunkRecord,
  SegmentOutOfRangeError,
  type LicenseSession,
} from '@/lib/content-license';
import { isAbortLike, wipeBytes } from '@/lib/mpeg-playback';

const CHUNK_CONCURRENCY = 3;

export async function fetchAndDecryptChunk(
  session: LicenseSession,
  chunkIndex: number,
  signal?: AbortSignal,
): Promise<{ data: Uint8Array; chunkCount: number | null }> {
  if (!session.content_key || !session.segment_url) {
    throw new Error('License session is missing audio.');
  }
  const record = await fetchEncryptedChunkRecord(session.segment_url, chunkIndex, signal);
  try {
    const plain = await decryptCamxoraChunk(record.data, session.content_key, chunkIndex);
    return { data: plain, chunkCount: record.chunkCount };
  } catch (err) {
    if (isAbortLike(err) || signal?.aborted) throw err;
    const plain = await decryptCamxoraChunk(record.data, session.content_key, chunkIndex);
    return { data: plain, chunkCount: record.chunkCount };
  }
}

export async function fetchRemainingChunksOrdered(
  session: LicenseSession,
  startChunk: number,
  initialExpected: number | null,
  token: number,
  loadToken: { current: number },
  signal: AbortSignal | undefined,
  onChunk: (index: number, data: Uint8Array) => Promise<void>,
): Promise<number | null> {
  let expected = initialExpected;
  let nextFetch = startChunk;
  let nextProcess = startChunk;
  const pending = new Map<number, Uint8Array>();
  const inFlight = new Set<number>();
  let finished = expected != null && startChunk >= expected;
  let processing = false;
  let settled = false;

  return new Promise<number | null>((resolve, reject) => {
    const settle = (fn: () => void) => {
      if (settled) return;
      settled = true;
      fn();
    };

    const maybeFinish = () => {
      if (finished && inFlight.size === 0 && !pending.has(nextProcess)) {
        settle(() => resolve(expected));
      }
    };

    const processLoop = async () => {
      if (processing) return;
      processing = true;
      try {
        while (pending.has(nextProcess)) {
          if (signal?.aborted || token !== loadToken.current) {
            settle(() => resolve(expected));
            return;
          }
          const data = pending.get(nextProcess)!;
          pending.delete(nextProcess);
          try {
            await onChunk(nextProcess, data);
          } catch (err) {
            settle(() => reject(err));
            return;
          }
          nextProcess += 1;
          if (expected != null && nextProcess >= expected) {
            finished = true;
          }
        }
      } finally {
        processing = false;
      }
      maybeFinish();
      pumpFetch();
    };

    const pumpFetch = () => {
      if (signal?.aborted || token !== loadToken.current) {
        finished = true;
        maybeFinish();
        return;
      }
      while (inFlight.size < CHUNK_CONCURRENCY && !finished) {
        const idx = nextFetch;
        if (expected != null && idx >= expected) break;
        nextFetch += 1;
        inFlight.add(idx);
        fetchAndDecryptChunk(session, idx, signal)
          .then((result) => {
            inFlight.delete(idx);
            if (signal?.aborted || token !== loadToken.current) {
              wipeBytes(result.data);
              maybeFinish();
              return;
            }
            if (result.chunkCount) expected = result.chunkCount;
            pending.set(idx, result.data);
            void processLoop();
          })
          .catch((err) => {
            inFlight.delete(idx);
            if (err instanceof SegmentOutOfRangeError) {
              finished = true;
              maybeFinish();
              pumpFetch();
              return;
            }
            if (isAbortLike(err) || signal?.aborted) {
              finished = true;
              maybeFinish();
              return;
            }
            settle(() => reject(err));
          });
      }
      maybeFinish();
    };

    pumpFetch();
  });
}
