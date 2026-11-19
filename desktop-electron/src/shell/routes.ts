export type ShellRouteKey =
  | "home"
  | "profile"
  | "progress"
  | "music"
  | "image"
  | "vizzy"
  | "marketplace"
  | "settings";

export interface ShellRoute {
  key: ShellRouteKey;
  path: string;
  label: string;
  phase: string;
  description: string;
  /** Font Awesome 6 solid class, e.g. "fa-house". */
  icon: string;
}

export const WORKSPACE_ROUTES: ShellRoute[] = [
  {
    key: "home",
    path: "/home",
    label: "Dashboard",
    phase: "P2",
    description: "Usage, quota and recent activity at a glance.",
    icon: "fa-house",
  },
  {
    key: "profile",
    path: "/profile",
    label: "Profile",
    phase: "P2",
    description: "Signed-in account, plan, credits, allowance and channel profiles.",
    icon: "fa-user",
  },
  {
    key: "progress",
    path: "/progress",
    label: "Progress",
    phase: "P3",
    description: "Live run stages, recovery actions and pending downloads.",
    icon: "fa-wave-square",
  },
  {
    key: "music",
    path: "/music",
    label: "Music",
    phase: "P4",
    description: "Batch composer, song editor, automation and history.",
    icon: "fa-music",
  },
  {
    key: "image",
    path: "/image",
    label: "Image",
    phase: "P5",
    description: "Image job queue, previews and prompt settings.",
    icon: "fa-image",
  },
  {
    key: "vizzy",
    path: "/vizzy",
    label: "Vizzy",
    phase: "P7",
    description: "The hosted Vizzy editor and the automation pipeline.",
    icon: "fa-film",
  },
  {
    key: "marketplace",
    path: "/marketplace",
    label: "Marketplace",
    phase: "P6",
    description: "Browse, install and manage Vizzy templates.",
    icon: "fa-store",
  },
];

export const UTILITY_ROUTES: ShellRoute[] = [
  {
    key: "settings",
    path: "/settings",
    label: "Settings",
    phase: "P2/P8",
    description: "Profiles, publication, preferences, prompts, pools and Suno.",
    icon: "fa-gear",
  },
];
