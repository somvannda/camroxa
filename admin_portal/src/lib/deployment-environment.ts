/**
 * Resolve a human-facing deployment label for admin ops UI.
 *
 * Prefer the platform_api /health payload (authoritative). Fall back to the
 * admin host so the badge still works before / after a mixed deploy.
 */

export type DeploymentEnvironmentLabel =
  | 'Production'
  | 'Sandbox'
  | 'Development'
  | 'Local'
  | 'Unknown'
  | string;

const HOST_SANDBOX = /sandbox/i;
const HOST_LOCAL = /^(localhost|127\.0\.0\.1)(:\d+)?$/i;

export function labelFromEnvironmentRaw(raw: string | null | undefined): DeploymentEnvironmentLabel {
  const value = String(raw ?? '')
    .trim()
    .toLowerCase();
  if (!value || value === 'unknown') return 'Unknown';
  if (value === 'production' || value === 'prod') return 'Production';
  if (value === 'staging' || value === 'sandbox') return 'Sandbox';
  if (value === 'development' || value === 'dev') return 'Development';
  if (value === 'local' || value === 'localhost') return 'Local';
  return value.replace(/_/g, ' ').replace(/\b\w/g, (ch) => ch.toUpperCase());
}

export function labelFromHostname(hostname: string | null | undefined): DeploymentEnvironmentLabel {
  const host = String(hostname ?? '')
    .trim()
    .toLowerCase();
  if (!host) return 'Unknown';
  if (HOST_LOCAL.test(host) || host.endsWith('.local')) return 'Local';
  if (HOST_SANDBOX.test(host)) return 'Sandbox';
  if (host === 'admin.camxora.com' || host.endsWith('.camxora.com')) return 'Production';
  return 'Unknown';
}

export function resolveDeploymentEnvironmentLabel(options: {
  apiEnvironment?: string | null;
  apiEnvironmentLabel?: string | null;
  hostname?: string | null;
}): DeploymentEnvironmentLabel {
  const fromApiLabel = String(options.apiEnvironmentLabel ?? '').trim();
  if (fromApiLabel) return fromApiLabel;

  const fromApiRaw = labelFromEnvironmentRaw(options.apiEnvironment);
  if (fromApiRaw !== 'Unknown') return fromApiRaw;

  return labelFromHostname(options.hostname ?? (typeof window !== 'undefined' ? window.location.hostname : ''));
}

export function deploymentEnvironmentBadgeClass(label: DeploymentEnvironmentLabel): string {
  switch (label) {
    case 'Production':
      return 'border-rose-400/25 bg-rose-500/10 text-rose-200';
    case 'Sandbox':
      return 'border-amber-400/25 bg-amber-500/10 text-amber-200';
    case 'Development':
    case 'Local':
      return 'border-sky-400/25 bg-sky-500/10 text-sky-200';
    default:
      return 'border-slate-400/20 bg-slate-500/10 text-slate-300';
  }
}
