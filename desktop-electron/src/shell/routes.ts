import {
  Activity,
  Clapperboard,
  Image,
  LayoutDashboard,
  Music2,
  Settings,
  Store,
  UserRound,
  type LucideIcon,
} from "lucide-react";

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
  icon: LucideIcon;
}

export const WORKSPACE_ROUTES: ShellRoute[] = [
  {
    key: "home",
    path: "/home",
    label: "Dashboard",
    phase: "P2",
    description: "Usage, quota and recent activity at a glance.",
    icon: LayoutDashboard,
  },
  {
    key: "profile",
    path: "/profile",
    label: "Profile",
    phase: "P2",
    description: "Signed-in account, plan, credits, allowance and channel profiles.",
    icon: UserRound,
  },
  {
    key: "progress",
    path: "/progress",
    label: "Progress",
    phase: "P3",
    description: "Live run stages, recovery actions and pending downloads.",
    icon: Activity,
  },
  {
    key: "music",
    path: "/music",
    label: "Music",
    phase: "P4",
    description: "Batch composer, song editor, automation and history.",
    icon: Music2,
  },
  {
    key: "image",
    path: "/image",
    label: "Image",
    phase: "P5",
    description: "Image job queue, previews and prompt settings.",
    icon: Image,
  },
  {
    key: "vizzy",
    path: "/vizzy",
    label: "Vizzy",
    phase: "P7",
    description: "The hosted Vizzy editor and the automation pipeline.",
    icon: Clapperboard,
  },
  {
    key: "marketplace",
    path: "/marketplace",
    label: "Marketplace",
    phase: "P6",
    description: "Browse, install and manage Vizzy templates.",
    icon: Store,
  },
];

export const UTILITY_ROUTES: ShellRoute[] = [
  {
    key: "settings",
    path: "/settings",
    label: "Settings",
    phase: "P2/P8",
    description: "Profiles, publication, preferences, prompts, pools and Suno.",
    icon: Settings,
  },
];
