export function createId(prefix: string) {
  const r = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
  return `${prefix}-${r}`;
}

export function nowIso() {
  return new Date().toISOString();
}

