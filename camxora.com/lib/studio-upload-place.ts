/**
 * Place a Studio upload inside a project document.
 *
 * Used by the Library's Uploads tab ("Add to project"), so the web List can send audio
 * straight into a Studio session. Pure: the caller owns the API read/write and the
 * version check; this only reshapes the document.
 */

export type UploadProjectTrack = {
  id: string;
  name?: string;
  color?: string;
  index?: number;
  volume?: number;
  pan?: number;
  muted?: boolean;
  solo?: boolean;
  hidden?: boolean;
  collapsed?: boolean;
  groupId?: string | null;
  chain?: unknown[];
  clipIds: string[];
  [key: string]: unknown;
};

export type UploadProjectClip = {
  id: string;
  title?: string;
  start?: number;
  duration?: number;
  audioUrl?: string | null;
  volume?: number;
  pan?: number;
  [key: string]: unknown;
};

export type UploadProjectData = {
  lanes?: unknown[];
  tracks?: unknown[];
  [key: string]: unknown;
};

export type UploadToPlace = {
  filename: string;
  url: string;
  durationSeconds?: number | null;
};

export type PlacementResult = {
  data: UploadProjectData;
  trackId: string;
  clipId: string;
  /** Where the clip starts, in seconds. */
  start: number;
};

/** Filename without its extension, used as the clip title. */
export function uploadTitle(filename: string): string {
  return filename.replace(/\.[a-z0-9]{2,5}$/i, "").trim() || "Upload";
}

function asTracks(value: unknown): UploadProjectTrack[] {
  return Array.isArray(value)
    ? (value.filter(
        (entry) => entry && typeof entry === "object" && Array.isArray((entry as UploadProjectTrack).clipIds)
      ) as UploadProjectTrack[])
    : [];
}

/**
 * Append the upload to the project's first track at the end of that track's clips,
 * creating the track when the project is empty. Existing lanes, tracks and settings are
 * carried through untouched.
 */
export function placeUploadInProject(
  data: UploadProjectData,
  upload: UploadToPlace,
  stamp: string
): PlacementResult {
  const lanes = Array.isArray(data.lanes) ? ([...data.lanes] as UploadProjectClip[]) : [];
  const tracks = asTracks(data.tracks);
  const trackId = tracks[0]?.id ?? `track-${stamp}`;
  const clipId = `clip-${stamp}`;

  const owner = tracks[0];
  const trackClips = owner
    ? lanes.filter((clip) => owner.clipIds.includes(clip.id))
    : [];
  const start = trackClips.reduce(
    (end, clip) => Math.max(end, (clip.start ?? 0) + (clip.duration ?? 0)),
    0
  );
  const duration = Math.max(1, Math.round(upload.durationSeconds || 4));

  const clip: UploadProjectClip = {
    id: clipId,
    title: uploadTitle(upload.filename),
    start,
    duration,
    audioUrl: upload.url,
    volume: 1,
    pan: 0,
  };

  const nextTracks: UploadProjectTrack[] = owner
    ? tracks.map((track) =>
        track.id === trackId ? { ...track, clipIds: [...track.clipIds, clipId] } : track
      )
    : [
        {
          id: trackId,
          name: "Uploads",
          color: "#38bdf8",
          index: 0,
          volume: 80,
          pan: 0,
          muted: false,
          solo: false,
          hidden: false,
          collapsed: false,
          groupId: null,
          chain: [],
          clipIds: [clipId],
        },
      ];

  return {
    data: { ...data, lanes: [...lanes, clip], tracks: nextTracks },
    trackId,
    clipId,
    start,
  };
}
