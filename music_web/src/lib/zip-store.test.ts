import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { crc32, createStoreZip } from './zip-store.ts';

const encoder = new TextEncoder();

describe('crc32', () => {
  it('matches the standard CRC-32 vector', () => {
    // 0xCBF43926 is the well-known CRC-32 of "123456789".
    assert.equal(crc32(encoder.encode('123456789')), 0xcbf43926);
  });

  it('is 0 for empty input', () => {
    assert.equal(crc32(new Uint8Array()), 0);
  });
});

describe('createStoreZip', () => {
  it('writes a readable store-only archive for one entry', async () => {
    const blob = createStoreZip([{ name: 'hello.txt', data: encoder.encode('hello world') }]);
    const bytes = new Uint8Array(await blob.arrayBuffer());
    const view = new DataView(bytes.buffer);

    // Local file header signature.
    assert.equal(view.getUint32(0, true), 0x04034b50);
    assert.equal(view.getUint16(8, true), 0, 'stored (no compression)');
    assert.equal(view.getUint32(14, true), crc32(encoder.encode('hello world')));
    assert.equal(view.getUint32(18, true), 11);
    assert.equal(view.getUint32(22, true), 11);

    // End of central directory record.
    const eocd = bytes.length - 22;
    assert.equal(view.getUint32(eocd, true), 0x06054b50);
    assert.equal(view.getUint16(eocd + 8, true), 1);
    assert.equal(view.getUint16(eocd + 10, true), 1);
  });

  it('records a central directory for every entry', async () => {
    const blob = createStoreZip([
      { name: 'a.mp3', data: new Uint8Array([1, 2, 3]) },
      { name: 'b.lrc', data: encoder.encode('[00:01.00]la') },
    ]);
    const bytes = new Uint8Array(await blob.arrayBuffer());
    const view = new DataView(bytes.buffer);
    const eocd = bytes.length - 22;

    assert.equal(view.getUint16(eocd + 10, true), 2, 'two entries');
    const centralOffset = view.getUint32(eocd + 16, true);
    assert.equal(view.getUint32(centralOffset, true), 0x02014b50);
  });
});
