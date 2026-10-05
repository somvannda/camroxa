#!/usr/bin/env node
/**
 * Pre-build guard: refuse to build a *production* music_web bundle that would
 * ship a missing or sandbox Turnstile sitekey.
 *
 * Runs automatically via the `prebuild` npm script. The signal is
 * `NEXT_PUBLIC_CAMXORA_ENV=production`, which the deploy scripts write into
 * `.env.production`; local builds are unaffected.
 *
 * See `docs/changelog/2026-10-05-music-web-turnstile-login-lockout.md`.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const SANDBOX_SITE_KEY = '0x4AAAAAAERrvCRyn8xcIet3';

function readEnvFile(name) {
  try {
    const text = readFileSync(resolve(process.cwd(), name), 'utf8');
    const values = {};
    for (const rawLine of text.split('\n')) {
      const line = rawLine.trim();
      if (!line || line.startsWith('#')) continue;
      const eq = line.indexOf('=');
      if (eq === -1) continue;
      const key = line.slice(0, eq).trim();
      let value = line.slice(eq + 1).trim();
      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }
      values[key] = value;
    }
    return values;
  } catch {
    return {};
  }
}

const fileEnv = {
  ...readEnvFile('.env'),
  ...readEnvFile('.env.production'),
  ...readEnvFile('.env.local'),
};
const readEnv = (name) => (process.env[name] ?? fileEnv[name] ?? '').trim();

// Only enforce on production builds; local/dev builds may legitimately omit it.
if (readEnv('NEXT_PUBLIC_CAMXORA_ENV') !== 'production') {
  process.exit(0);
}

const siteKey = readEnv('NEXT_PUBLIC_CLOUDFLARE_TURNSTILE_SITE_KEY');
const problems = [];
if (!siteKey) {
  problems.push('NEXT_PUBLIC_CLOUDFLARE_TURNSTILE_SITE_KEY is not set');
} else if (siteKey === SANDBOX_SITE_KEY) {
  problems.push(`sitekey is the sandbox key (${SANDBOX_SITE_KEY})`);
}

if (problems.length > 0) {
  console.error('[turnstile] Refusing to build a production music_web bundle:');
  for (const problem of problems) {
    console.error(`  - ${problem}`);
  }
  console.error(
    '  Set the production Turnstile sitekey (see scripts/deploy/apply_turnstile_production.py).',
  );
  process.exit(1);
}

console.log('[turnstile] production sitekey OK');
