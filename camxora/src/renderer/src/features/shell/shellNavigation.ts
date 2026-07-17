import type { ComponentType } from 'react'
import {
  Activity,
  Gauge,
  GitMerge,
  Image as ImageIcon,
  Music4,
  ScrollText,
  Settings,
  UserRound,
  Video,
  Workflow,
} from 'lucide-react'

export type ShellRouteKey =
  | 'home'
  | 'profile'
  | 'workflow'
  | 'progress'
  | 'music'
  | 'image'
  | 'video'
  | 'videoPy'
  | 'merger'
  | 'settings'
  | 'log'

export type ShellRouteMeta = {
  key: ShellRouteKey
  to: `/app/${string}`
  label: string
  title: string
  eyebrow: string
  description: string
  icon: ComponentType<{ className?: string }>
}

export const shellRoutes: ShellRouteMeta[] = [
  {
    key: 'home',
    to: '/app/home',
    label: 'Dashboard',
    title: 'Dashboard',
    eyebrow: 'Workspace',
    description: 'Overview of the current CAMXORA account, profile readiness, and studio status.',
    icon: Gauge,
  },
  {
    key: 'profile',
    to: '/app/profile',
    label: 'Profile',
    title: 'Profile',
    eyebrow: 'Workspace',
    description: 'Signed-in account, plan, credits, allowance, and created channel profiles.',
    icon: UserRound,
  },
  {
    key: 'workflow',
    to: '/app/workflow',
    label: 'Workflow',
    title: 'Workflow',
    eyebrow: 'Workspace',
    description: 'Timeline view for the selected run and channel, driven by the shared progress aggregate feed.',
    icon: Workflow,
  },
  {
    key: 'progress',
    to: '/app/progress',
    label: 'Progress',
    title: 'Progress',
    eyebrow: 'Workspace',
    description: 'Progress monitoring surface with date filters, active-only mode, polling, and row-level pipeline status.',
    icon: Activity,
  },
  {
    key: 'music',
    to: '/app/music',
    label: 'Music',
    title: 'Music',
    eyebrow: 'Workspace',
    description: 'Music workspace with the dense Python-style composer, automation strip, song editor, and history table.',
    icon: Music4,
  },
  {
    key: 'image',
    to: '/app/image',
    label: 'Image',
    title: 'Image',
    eyebrow: 'Workspace',
    description: 'Image workspace with live prompt generation, optional reference uploads, session results, and backend progress context.',
    icon: ImageIcon,
  },
  {
    key: 'video',
    to: '/app/video',
    label: 'Video',
    title: 'Video',
    eyebrow: 'Workspace',
    description: 'Video workspace bootstrap with real local template/state loading through the Electron desktop bridge, ready for preview and export commands next.',
    icon: Video,
  },
  {
    key: 'videoPy',
    to: '/app/video-py',
    label: 'Video (Py)',
    title: 'Video (Py)',
    eyebrow: 'Workspace',
    description: 'Native Python video workspace with PyQt6 UI, GPU preview, and full export pipeline running as an embedded process.',
    icon: Video,
  },
  {
    key: 'merger',
    to: '/app/merger',
    label: 'Merger',
    title: 'Merger',
    eyebrow: 'Reserved route',
    description: 'This route is reserved for later parity with the Python merger flow.',
    icon: GitMerge,
  },
  {
    key: 'settings',
    to: '/app/settings',
    label: 'Settings',
    title: 'Settings',
    eyebrow: 'Workspace',
    description: 'Desktop-editable settings, local paths, and user preferences without reintroducing provider management.',
    icon: Settings,
  },
  {
    key: 'log',
    to: '/app/log',
    label: 'Log',
    title: 'Log',
    eyebrow: 'Reserved route',
    description: 'Runtime logs and diagnostics will be exposed here for long-running desktop sessions.',
    icon: ScrollText,
  },
]

export function getShellRouteMeta(pathname: string): ShellRouteMeta {
  return shellRoutes.find((route) => pathname.startsWith(route.to)) ?? shellRoutes[0]
}
