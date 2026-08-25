import type { LicenseSession } from '@/lib/content-license';
import type { ProtectedAudioGraph } from '@/lib/mpeg-playback';
import type { StreamTrack } from '@/lib/streaming-api';

import type { PlayerId } from './detect';

export type PackagedPlayContext = {
  playerId: PlayerId;
  media: HTMLMediaElement;
  session: LicenseSession;
  track: StreamTrack;
  token: number;
  loadToken: { current: number };
  objectUrlRef: { current: string | null };
  signal: AbortSignal;
  volume: number;
  muted: boolean;
  catalogDuration: number;
  ensureGraph: () => ProtectedAudioGraph;
  setPlaying: (value: boolean) => void;
  setError: (value: string | null) => void;
  playingRef: { current: boolean };
  heartbeatRef: { current: number | null };
  ramCacheKey: string;
  startPositionHeartbeat: (getPosition: () => number) => void;
  startMediaSessionTick: () => void;
  syncNowPlayingFromRefs: (reason: string, force?: boolean) => void;
};

export type PlayBackend = {
  id: PlayerId;
  play: (ctx: PackagedPlayContext) => Promise<void>;
};
