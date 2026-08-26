import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  DEFAULT_POST_AUTH_PATH,
  destinationForSignedInUser,
  safeNextPath,
} from './auth-redirect.ts';

describe('safeNextPath', () => {
  it('defaults to Create', () => {
    assert.equal(safeNextPath(null), DEFAULT_POST_AUTH_PATH);
    assert.equal(safeNextPath(''), DEFAULT_POST_AUTH_PATH);
  });

  it('rejects auth pages and off-site paths', () => {
    assert.equal(safeNextPath('/login'), DEFAULT_POST_AUTH_PATH);
    assert.equal(safeNextPath('/register'), DEFAULT_POST_AUTH_PATH);
    assert.equal(safeNextPath('/verify-email'), DEFAULT_POST_AUTH_PATH);
    assert.equal(safeNextPath('https://evil.example/'), DEFAULT_POST_AUTH_PATH);
    assert.equal(safeNextPath('//evil.example'), DEFAULT_POST_AUTH_PATH);
  });

  it('keeps safe in-app paths', () => {
    assert.equal(safeNextPath('/playlists'), '/playlists');
    assert.equal(safeNextPath('/library?tab=liked'), '/library');
  });
});

describe('destinationForSignedInUser', () => {
  it('returns null when signed out', () => {
    assert.equal(destinationForSignedInUser(null), null);
    assert.equal(destinationForSignedInUser(undefined), null);
  });

  it('sends confirmed (or unknown) sessions to Create', () => {
    assert.equal(destinationForSignedInUser({ email_confirmed: true }), '/create');
    assert.equal(destinationForSignedInUser({ email: 'duke@test.com' }), '/create');
  });

  it('honors a safe next path', () => {
    assert.equal(
      destinationForSignedInUser({ email_confirmed: true }, '/playlists'),
      '/playlists',
    );
    assert.equal(
      destinationForSignedInUser({ email_confirmed: true }, '/register'),
      '/create',
    );
  });

  it('sends unconfirmed sessions to verify-email', () => {
    assert.equal(
      destinationForSignedInUser(
        { email: 'duke@test.com', email_confirmed: false },
        '/create',
      ),
      '/verify-email?email=duke%40test.com&next=%2Fcreate',
    );
  });
});
