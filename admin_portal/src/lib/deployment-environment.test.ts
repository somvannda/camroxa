import { describe, expect, it } from 'vitest';
import {
  labelFromEnvironmentRaw,
  labelFromHostname,
  resolveDeploymentEnvironmentLabel,
} from './deployment-environment';

describe('labelFromEnvironmentRaw', () => {
  it('maps production and staging to product labels', () => {
    expect(labelFromEnvironmentRaw('production')).toBe('Production');
    expect(labelFromEnvironmentRaw('prod')).toBe('Production');
    expect(labelFromEnvironmentRaw('staging')).toBe('Sandbox');
    expect(labelFromEnvironmentRaw('sandbox')).toBe('Sandbox');
  });
});

describe('labelFromHostname', () => {
  it('detects sandbox and production admin hosts', () => {
    expect(labelFromHostname('admin.sandbox.camxora.com')).toBe('Sandbox');
    expect(labelFromHostname('admin.camxora.com')).toBe('Production');
    expect(labelFromHostname('localhost')).toBe('Local');
  });
});

describe('resolveDeploymentEnvironmentLabel', () => {
  it('prefers API environment_label', () => {
    expect(
      resolveDeploymentEnvironmentLabel({
        apiEnvironmentLabel: 'Sandbox',
        apiEnvironment: 'production',
        hostname: 'admin.camxora.com',
      }),
    ).toBe('Sandbox');
  });

  it('falls back to hostname when API fields are missing', () => {
    expect(
      resolveDeploymentEnvironmentLabel({
        hostname: 'admin.sandbox.camxora.com',
      }),
    ).toBe('Sandbox');
  });
});
