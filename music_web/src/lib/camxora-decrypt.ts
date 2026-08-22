/** Web Crypto AES-256-GCM decrypt for Camxora chunked packages (CXA1). */

export const DECRYPT_MODULE_VERSION = 'camxora-decrypt-webcrypto-v1';

const NONCE_LEN = 12;

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function hexToBytes(hex: string): Uint8Array {
  const clean = hex.trim().toLowerCase();
  if (clean.length % 2 !== 0) throw new Error('Invalid content key.');
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i += 1) {
    out[i] = Number.parseInt(clean.slice(i * 2, i * 2 + 2), 16);
  }
  return out;
}

export async function decryptModuleHash(): Promise<string> {
  const digest = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(DECRYPT_MODULE_VERSION),
  );
  return bytesToHex(new Uint8Array(digest));
}

function readU32Be(view: DataView, offset: number): number {
  return view.getUint32(offset, false);
}

export async function decryptCamxoraChunk(
  record: ArrayBuffer,
  contentKeyHex: string,
  index: number,
): Promise<Uint8Array> {
  const bytes = new Uint8Array(record);
  if (bytes.byteLength < NONCE_LEN + 4) {
    throw new Error('Encrypted chunk is too short.');
  }
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const nonce = bytes.slice(0, NONCE_LEN);
  const tokenLen = readU32Be(view, NONCE_LEN);
  const token = bytes.slice(NONCE_LEN + 4, NONCE_LEN + 4 + tokenLen);
  if (token.byteLength !== tokenLen) {
    throw new Error('Encrypted chunk is truncated.');
  }
  const keyBytes = hexToBytes(contentKeyHex);
  const key = await crypto.subtle.importKey(
    'raw',
    keyBytes.buffer.slice(keyBytes.byteOffset, keyBytes.byteOffset + keyBytes.byteLength) as ArrayBuffer,
    'AES-GCM',
    false,
    ['decrypt'],
  );
  const aad = new TextEncoder().encode(`camxora-chunk-v1:${index}`);
  const plain = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: nonce, additionalData: aad, tagLength: 128 },
    key,
    token.buffer.slice(token.byteOffset, token.byteOffset + token.byteLength) as ArrayBuffer,
  );
  return new Uint8Array(plain);
}
