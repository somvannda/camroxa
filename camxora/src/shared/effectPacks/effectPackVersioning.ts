export function normalizeAppVersion(value: string): [number, number, number] | null {
  const match = String(value || '')
    .trim()
    .match(/^(\d+)\.(\d+)\.(\d+)/)
  if (!match) {
    return null
  }
  return [Number(match[1]), Number(match[2]), Number(match[3])]
}

function compareVersions(left: [number, number, number], right: [number, number, number]): number {
  for (let index = 0; index < 3; index += 1) {
    const delta = left[index] - right[index]
    if (delta !== 0) {
      return delta
    }
  }
  return 0
}

export function matchesAppVersionRange(appVersion: string, range: string): boolean {
  const normalizedRange = String(range || '*').trim()
  if (!normalizedRange || normalizedRange === '*') {
    return true
  }

  const version = normalizeAppVersion(appVersion)
  if (!version) {
    return false
  }

  if (normalizedRange.startsWith('^')) {
    const base = normalizeAppVersion(normalizedRange.slice(1))
    if (!base) {
      return false
    }
    return version[0] === base[0] && compareVersions(version, base) >= 0
  }

  if (normalizedRange.startsWith('~')) {
    const base = normalizeAppVersion(normalizedRange.slice(1))
    if (!base) {
      return false
    }
    return version[0] === base[0] && version[1] === base[1] && compareVersions(version, base) >= 0
  }

  const exact = normalizeAppVersion(normalizedRange)
  if (!exact) {
    return false
  }
  return compareVersions(version, exact) === 0
}
