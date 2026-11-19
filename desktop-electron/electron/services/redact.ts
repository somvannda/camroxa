const SECRET_KEY = /token|password|secret|authorization|cookie|email/i;
const EMAIL = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi;
const BEARER = /Bearer\s+[A-Za-z0-9._~+/-]+=*/gi;

export function redactString(value: string): string {
  return value.replace(BEARER, "Bearer [redacted]").replace(EMAIL, "[redacted-email]");
}

export function redact(value: unknown, depth = 0): unknown {
  if (depth > 8) return "[depth-limit]";
  if (typeof value === "string") return redactString(value);
  if (Array.isArray(value)) return value.map((item) => redact(item, depth + 1));
  if (value && typeof value === "object") {
    const output: Record<string, unknown> = {};
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      output[key] = SECRET_KEY.test(key) ? "[redacted]" : redact(child, depth + 1);
    }
    return output;
  }
  return value;
}
