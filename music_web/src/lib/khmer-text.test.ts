import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { containsKhmer, khmerTextClass } from './khmer-text.ts';

describe('containsKhmer', () => {
  it('detects Khmer letters', () => {
    assert.equal(containsKhmer('សួស្តី ពិភពលោក'), true);
    assert.equal(containsKhmer('Rainy night ស្រឡាញ់'), true);
  });

  it('ignores Latin-only and empty text', () => {
    assert.equal(containsKhmer('Hello world'), false);
    assert.equal(containsKhmer(''), false);
    assert.equal(containsKhmer(null), false);
    assert.equal(containsKhmer(undefined), false);
  });
});

describe('khmerTextClass', () => {
  it('returns the Siemreap class only for Khmer copy', () => {
    assert.equal(khmerTextClass('បទចម្រៀង'), 'font-khmer');
    assert.equal(khmerTextClass('City Lights'), '');
  });
});
