/**
 * Ruler section markers ("Create Section" in the clip menu, S46).
 *
 * Markers live on the project document as plain time/label records; they are not
 * clips, so they survive clip edits and versions without joining the lane model.
 */

export type SectionMarker = {
  id: string;
  time: number;
  label: string;
  color: string;
};

export function sanitizeSectionMarkers(input: unknown): SectionMarker[] {
  if (!Array.isArray(input)) return [];
  return input
    .map((raw) => {
      if (!raw || typeof raw !== "object") return null;
      const marker = raw as Record<string, unknown>;
      const time = Number(marker.time);
      if (!Number.isFinite(time)) return null;
      return {
        id: typeof marker.id === "string" && marker.id ? marker.id : `marker-${time}`,
        time: Math.max(0, time),
        label: typeof marker.label === "string" ? marker.label.slice(0, 80) : "Section",
        color: typeof marker.color === "string" ? marker.color : "#3dafff",
      };
    })
    .filter((marker): marker is SectionMarker => marker !== null)
    .sort((a, b) => a.time - b.time);
}
