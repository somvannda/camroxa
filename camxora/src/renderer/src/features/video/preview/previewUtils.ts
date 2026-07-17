export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

export function normalizeColor(value: string, fallback: string): string {
  const raw = typeof value === 'string' ? value.trim() : ''
  if (!raw) {
    return fallback
  }
  if (raw.startsWith('#')) {
    return raw
  }
  return /^[\da-fA-F]{3,8}$/.test(raw) ? `#${raw}` : raw
}

function parseHexColor(value: string): { red: number; green: number; blue: number } | null {
  const normalized = value.trim()
  if (!normalized.startsWith('#')) {
    return null
  }

  const hex = normalized.slice(1)
  if (!/^[\da-fA-F]{3,4}$|^[\da-fA-F]{6}$|^[\da-fA-F]{8}$/.test(hex)) {
    return null
  }

  const expanded =
    hex.length === 3 || hex.length === 4
      ? hex
          .slice(0, 3)
          .split('')
          .map((channel) => channel + channel)
          .join('')
      : hex.slice(0, 6)

  return {
    red: Number.parseInt(expanded.slice(0, 2), 16) / 255,
    green: Number.parseInt(expanded.slice(2, 4), 16) / 255,
    blue: Number.parseInt(expanded.slice(4, 6), 16) / 255,
  }
}

function parseRgbChannel(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed) {
    return null
  }

  if (trimmed.endsWith('%')) {
    const parsedPercent = Number.parseFloat(trimmed.slice(0, -1))
    if (!Number.isFinite(parsedPercent)) {
      return null
    }
    return clamp(parsedPercent / 100, 0, 1)
  }

  const parsedNumber = Number.parseFloat(trimmed)
  if (!Number.isFinite(parsedNumber)) {
    return null
  }
  return clamp(parsedNumber / 255, 0, 1)
}

function parseRgbColor(value: string): { red: number; green: number; blue: number } | null {
  const match = value
    .trim()
    .match(/^rgba?\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^,\)]+)(?:\s*,\s*[^,\)]+)?\s*\)$/i)
  if (!match) {
    return null
  }

  const red = parseRgbChannel(match[1] ?? '')
  const green = parseRgbChannel(match[2] ?? '')
  const blue = parseRgbChannel(match[3] ?? '')
  if (red === null || green === null || blue === null) {
    return null
  }

  return { red, green, blue }
}

export function tryParseColorToNormalizedRgb(
  color: string,
): { red: number; green: number; blue: number } | null {
  const normalized = normalizeColor(color, '')
  if (!normalized) {
    return null
  }

  return parseHexColor(normalized) ?? parseRgbColor(normalized)
}

export function colorToNormalizedRgb(color: string): { red: number; green: number; blue: number } {
  return (
    tryParseColorToNormalizedRgb(color) ??
    tryParseColorToNormalizedRgb('#ffffff') ?? {
      red: 1,
      green: 1,
      blue: 1,
    }
  )
}
