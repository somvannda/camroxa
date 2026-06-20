export interface DashboardData {
  activeBatches: number;
  failedItems: number;
  songs: number;
  images: number;
  mp4: number;
  merged: number;
  youtube: number;
  credits: number;
}

export interface MusicSong {
  id: string;
  title: string;
  description: string;
  structure: string;
  status: string;
  okChannel: string;
  altChannel: string;
  sunoStatus: string;
  generatedAt: string;
}

export interface ProgressRow {
  batch: string;
  runDate: string;
  channel: string;
  status: string;
  music: string;
  image: string;
  converter: string;
  merge: string;
  youtube: string;
  stage: string;
  notes: string;
  updated: string;
}

export interface VideoTemplate {
  id: string;
  name: string;
  settings: Record<string, any>;
}

export interface MusicProfile {
  id: string;
  name: string;
  folder: string;
  logoPath: string;
  videoTemplate: string;
  reelTemplate: string;
}

export interface LogEntry {
  timestamp: string;
  message: string;
}

export type PageKey = 'login' | 'home' | 'music' | 'video' | 'workflow' | 'image' | 'progress' | 'settings' | 'log' | 'merger';
