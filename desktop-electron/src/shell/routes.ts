export type ShellRouteKey =
  | "home"
  | "profile"
  | "plan"
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

export interface NavGroup {
  label: string;
  routes: ShellRoute[];
}

const ROUTES: Record<ShellRouteKey, ShellRoute> = {
  home: {
    key: "home",
    path: "/home",
    label: "Dashboard",
    phase: "P2",
    description: "Credits, generation output and recent activity at a glance.",
    icon: "fa-house",
  },
  progress: {
    key: "progress",
    path: "/progress",
    label: "Progress",
    phase: "P3",
    description: "Live run stages, recovery actions and pending downloads.",
    icon: "fa-wave-square",
  },
  music: {
    key: "music",
    path: "/music",
    label: "Music",
    phase: "P4",
    description: "Batch composer, song editor, automation and history.",
    icon: "fa-music",
  },
  image: {
    key: "image",
    path: "/image",
    label: "Image",
    phase: "P5",
    description: "Image job queue, previews and prompt settings.",
    icon: "fa-image",
  },
  vizzy: {
    key: "vizzy",
    path: "/vizzy",
    label: "Vizzy",
    phase: "P7",
    description: "The hosted Vizzy editor and the automation pipeline.",
    icon: "fa-film",
  },
  marketplace: {
    key: "marketplace",
    path: "/marketplace",
    label: "Marketplace",
    phase: "P6",
    description: "Browse, install and manage Vizzy templates.",
    icon: "fa-store",
  },
  profile: {
    key: "profile",
    path: "/profile",
    label: "Profile",
    phase: "P2",
    description: "Signed-in account, credits, usage and channel profiles.",
    icon: "fa-user",
  },
  plan: {
    key: "plan",
    path: "/plan",
    label: "Plan",
    phase: "P10",
    description: "Buy credit packs and review billing activity.",
    icon: "fa-credit-card",
  },
  settings: {
    key: "settings",
    path: "/settings",
    label: "Settings",
    phase: "P2/P8",
    description: "Profiles, publication, preferences, prompts, pools and Suno.",
    icon: "fa-gear",
  },
};

/**
 * Sidebar information architecture: work first, then creation, discovery and
 * account controls. Paths stay stable; only grouping/labels change.
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Overview",
    routes: [ROUTES.home],
  },
  {
    label: "Create",
    routes: [ROUTES.progress, ROUTES.music, ROUTES.image, ROUTES.vizzy],
  },
  {
    label: "Discover",
    routes: [ROUTES.marketplace],
  },
  {
    label: "Account",
    routes: [ROUTES.profile, ROUTES.plan, ROUTES.settings],
  },
];

const ALL_ROUTES = NAV_GROUPS.flatMap((group) => group.routes);

export const WORKSPACE_ROUTES: ShellRoute[] = ALL_ROUTES.filter(
  (route) => route.key !== "settings",
);

export const UTILITY_ROUTES: ShellRoute[] = ALL_ROUTES.filter(
  (route) => route.key === "settings",
);
