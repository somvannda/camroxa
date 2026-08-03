/** Static Guides slide deck — public product copy only (no secrets). */

export type SlideKind = "title" | "section" | "content" | "win" | "cta";

export type SlideMock =
  | "pipeline"
  | "onboarding"
  | "settings"
  | "templates"
  | "music"
  | "progress"
  | "images"
  | "upload"
  | "youtube"
  | "growth"
  | "roadmap"
  | "publishEverywhere";

export type GuideSlide = {
  id: string;
  section: string;
  kind: SlideKind;
  eyebrow?: string;
  title: string;
  subtitle?: string;
  bullets?: string[];
  /** Optional screenshot under /guides/*.png — falls back to mock panel. */
  imageSrc?: string;
  mock?: SlideMock;
  footerNote?: string;
};

export const GUIDE_SECTIONS = [
  "Intro",
  "Monetization",
  "Onboarding",
  "YouTube setup",
  "Using CAMXORA",
  "Growth",
  "Coming soon",
  "Thank you",
] as const;

export const GUIDE_DECK: GuideSlide[] = [
  {
    id: "intro-title",
    section: "Intro",
    kind: "title",
    eyebrow: "CAMXORA Guides",
    title: "Faceless YouTube music. One studio. Dual channels. One click.",
    subtitle:
      "Stop the ChatGPT + Suno + CapCut grind — then learn the channel craft CAMXORA automates.",
    bullets: [
      "One pipeline, not six tabs: lyrics → music → art → video → merge",
      "Dual channels by default (Primary + Secondary)",
      "Desktop studio creates; this panel manages account, credits, and profiles",
    ],
  },
  {
    id: "intro-what",
    section: "Intro",
    kind: "content",
    eyebrow: "What is CAMXORA?",
    title: "A Windows desktop pipeline for dual faceless channels.",
    bullets: [
      "Guided onboarding builds both channel profiles — names, logos, covers, SEO",
      "Generate lyrics, music, artwork, and spectrum video in one app",
      "Export YouTube-ready videos today (auto YouTube upload is coming soon)",
      "Track usage, credits, and profiles from this user panel",
    ],
    mock: "pipeline",
  },
  {
    id: "intro-flow",
    section: "Intro",
    kind: "content",
    eyebrow: "How it works",
    title: "Idea → lyrics → music → art → video → YouTube-ready.",
    bullets: [
      "Pick a niche and lock dual channel identities",
      "Prepare YouTube titles, keywords, tags, and playlists",
      "Run Music → Image → Video templates → Progress in the desktop app",
      "Export finished videos, then upload and repeat with less manual work",
    ],
    mock: "pipeline",
    footerNote: "From ~10 hours a day of manual channel work toward ~1 hour with the CAMXORA pipeline.",
  },
  {
    id: "win-section",
    section: "Monetization",
    kind: "section",
    eyebrow: "Biggest win",
    title: "Get monetized — or we refund 100%.",
    subtitle: "Follow the CAMXORA playbook and YouTube policies. We refund the plan fee — not AdSense.",
  },
  {
    id: "win-guarantee",
    section: "Monetization",
    kind: "win",
    eyebrow: "Monetization guarantee",
    title: "Get monetized — or we refund 100%.",
    bullets: [
      "Use CAMXORA to build and publish dual faceless music channels",
      "Follow CAMXORA’s workflow and YouTube policies",
      "Keep posting consistency — upload every day on both channels",
      "If you don’t reach monetization, claim a full plan refund (trade-in: you also return the channels you built)",
      "Once either channel reaches YouTube monetization, the refund is no longer available",
    ],
    footerNote:
      "Refund covers the plan fee only — not AdSense earnings or third-party costs. Contact support@camxora.com with account, invoice, and channel details.",
  },
  {
    id: "onboard-section",
    section: "Onboarding",
    kind: "section",
    eyebrow: "Onboarding board",
    title: "Build your channel system.",
    subtitle: "Primary + Secondary — Genre → Names → Logos → Cover Art → Description & SEO.",
  },
  {
    id: "onboard-niche",
    section: "Onboarding",
    kind: "content",
    eyebrow: "Step 1 · Pick Your Genre",
    title: "Choose your music genre.",
    bullets: [
      "Select a focused music style audiences can recognize instantly",
      "Keep Primary and Secondary related but distinct",
      "Niche drives naming, art direction, and SEO later",
      "Commit before generating logos and covers",
    ],
    mock: "onboarding",
  },
  {
    id: "onboard-names",
    section: "Onboarding",
    kind: "content",
    eyebrow: "Step 2 · Choose Names",
    title: "Pick unique channel names.",
    bullets: [
      "Generate or write names that match your niche",
      "Check availability and brand feel for both channels",
      "Keep names short, searchable, and consistent with covers",
      "You’ll reuse these across YouTube Studio and CAMXORA profiles",
    ],
    mock: "onboarding",
  },
  {
    id: "onboard-logo",
    section: "Onboarding",
    kind: "content",
    eyebrow: "Step 3 · Design Logos",
    title: "Create visual identity.",
    bullets: [
      "Generate logo options for Primary and Secondary",
      "Prefer simple marks that read at YouTube avatar size",
      "Stay consistent with niche colors and mood",
      "Save the finals into each channel profile",
    ],
    mock: "onboarding",
  },
  {
    id: "onboard-cover",
    section: "Onboarding",
    kind: "content",
    eyebrow: "Step 4 · Cover Art",
    title: "YouTube banners for each channel.",
    bullets: [
      "Create banner art sized for YouTube’s safe areas",
      "Echo the logo palette without overcrowding text",
      "Use covers that signal genre at a glance",
      "Upload the same identity in Studio and CAMXORA",
    ],
    mock: "onboarding",
  },
  {
    id: "onboard-seo",
    section: "Onboarding",
    kind: "content",
    eyebrow: "Step 5 · Description",
    title: "SEO content & tags — copy into YouTube.",
    bullets: [
      "Craft a channel description that states niche + value",
      "Generate keywords that match how fans search",
      "Build a clean tag set — relevant, not spammy",
      "Reuse this language in video titles and playlists later",
    ],
    mock: "onboarding",
  },
  {
    id: "yt-section",
    section: "YouTube setup",
    kind: "section",
    eyebrow: "YouTube Studio",
    title: "Prepare channels before the pipeline",
    subtitle: "Create the channel shell so CAMXORA has somewhere to publish.",
  },
  {
    id: "yt-create",
    section: "YouTube setup",
    kind: "content",
    eyebrow: "Create & prepare",
    title: "How to create and prepare a YouTube channel.",
    bullets: [
      "Create a Brand Account / channel for each profile",
      "Upload logo avatar and banner from onboarding",
      "Confirm country / audience settings in Studio",
      "Enable features you need (custom URL later when eligible)",
    ],
    mock: "youtube",
  },
  {
    id: "yt-title-desc",
    section: "YouTube setup",
    kind: "content",
    eyebrow: "Title & description",
    title: "Channel title and About description.",
    bullets: [
      "Use the onboarding name as the public channel title",
      "Paste your polished description into the About tab",
      "Lead with niche, then posting cadence and value",
      "Keep claims honest and policy-safe",
    ],
    mock: "youtube",
  },
  {
    id: "yt-keywords-tags",
    section: "YouTube setup",
    kind: "content",
    eyebrow: "Keywords & tags",
    title: "Channel keywords and video tags.",
    bullets: [
      "Add channel keywords in Studio advanced settings",
      "Reuse onboarding keywords as a starting set",
      "For each upload, pick a tight tag set from your niche list",
      "Avoid irrelevant or misleading tags",
    ],
    mock: "youtube",
  },
  {
    id: "yt-country-playlist",
    section: "YouTube setup",
    kind: "content",
    eyebrow: "Country & playlists",
    title: "Country targeting and playlist structure.",
    bullets: [
      "Set channel country to match your intended audience",
      "Create playlists by mood, series, or album theme",
      "Add new videos to playlists on every upload",
      "Playlists help binge sessions and channel navigation",
    ],
    mock: "youtube",
  },
  {
    id: "use-section",
    section: "Using CAMXORA",
    kind: "section",
    eyebrow: "Desktop studio",
    title: "How to use CAMXORA day to day",
    subtitle: "Settings → Video/Marketplace templates → Music → Progress → Image → export & upload.",
  },
  {
    id: "use-settings",
    section: "Using CAMXORA",
    kind: "content",
    eyebrow: "1 · Settings",
    title: "Channel profiles and preferences.",
    bullets: [
      "Open Settings and select Primary / Secondary profiles",
      "Confirm niche, identity assets, and generation preferences",
      "Align sample packs and output folders with your machine",
      "Save before starting a new batch",
    ],
    mock: "settings",
    imageSrc: "/guides/settings.png",
  },
  {
    id: "use-templates",
    section: "Using CAMXORA",
    kind: "content",
    eyebrow: "2 · Video · Marketplace",
    title: "Design and install video templates.",
    bullets: [
      "Use Video for layouts that fit long-form music videos",
      "Browse Marketplace for curated one-click template packs",
      "Keep typography and safe margins consistent with covers",
      "Reuse templates across batches for brand consistency",
    ],
    mock: "templates",
    imageSrc: "/guides/templates.png",
  },
  {
    id: "use-music",
    section: "Using CAMXORA",
    kind: "content",
    eyebrow: "3 · Music",
    title: "Understand the Music page and run the pipeline.",
    bullets: [
      "Review song drafts, titles, and album grouping",
      "Start the generation pipeline for the active batch",
      "Let music, image, and export stages run in sequence",
      "Don’t interrupt mid-batch unless you intend to retry",
    ],
    mock: "music",
    imageSrc: "/guides/music.png",
  },
  {
    id: "use-progress",
    section: "Using CAMXORA",
    kind: "content",
    eyebrow: "4 · Progress",
    title: "Track stages on the Progress page.",
    bullets: [
      "Watch music, image, converter, merge, and upload stages",
      "Failed rows surface errors you can retry",
      "Done means assets are ready for the next step",
      "Use Progress as the source of truth while batches run",
    ],
    mock: "progress",
    imageSrc: "/guides/progress.png",
  },
  {
    id: "use-images",
    section: "Using CAMXORA",
    kind: "content",
    eyebrow: "5 · Image",
    title: "Backgrounds and thumbnails.",
    bullets: [
      "Review generated backgrounds and thumbnails per channel",
      "Regenerate when art doesn’t match the niche",
      "Thumbnails matter for click-through — keep them readable",
      "Ready images unlock export and upload paths",
    ],
    mock: "images",
    imageSrc: "/guides/images.png",
  },
  {
    id: "use-upload",
    section: "Using CAMXORA",
    kind: "content",
    eyebrow: "6 · Export & upload",
    title: "Ship YouTube-ready videos.",
    bullets: [
      "Export finished MP4s from the desktop pipeline today",
      "Confirm titles, descriptions, and tags before publish",
      "Upload manually for now — auto YouTube upload is coming soon",
      "Add each video to the matching playlist",
    ],
    mock: "upload",
    imageSrc: "/guides/upload.png",
  },
  {
    id: "growth-section",
    section: "Growth",
    kind: "section",
    eyebrow: "Audience growth",
    title: "Best practices to earn followers and views",
    subtitle: "Consistency and community — not just uploads.",
  },
  {
    id: "growth-practices",
    section: "Growth",
    kind: "content",
    eyebrow: "Engagement",
    title: "Reply, show up, and attract traffic.",
    bullets: [
      "Must reply to all comments — every reply builds trust and the algorithm",
      "Keep posting consistency: upload every day on both channels",
      "Use your channel account as the profile on larger niche channels",
      "Drop helpful, relevant comments there to invite audiences back to your channels",
      "Stay policy-safe: no spam, misleading links, or off-topic promotions",
    ],
    mock: "growth",
  },
  {
    id: "soon-section",
    section: "Coming soon",
    kind: "section",
    eyebrow: "Our vision",
    title: "Create once. Publish everywhere.",
    subtitle:
      "CAMXORA is evolving into an all-in-one content automation platform — generate, manage, and publish across platforms with minimal manual effort. Roadmap below — no exact release dates.",
  },
  {
    id: "soon-distrokid",
    section: "Coming soon",
    kind: "content",
    eyebrow: "DistroKid integration",
    title: "Direct music publishing with WAV.",
    bullets: [
      "Automatic WAV export for distribution-ready audio",
      "Upload tracks to DistroKid from the CAMXORA workflow",
      "Manage releases without leaving the studio path",
      "Streamlined music distribution alongside video publishing",
    ],
    mock: "roadmap",
    footerNote: "Coming soon — timing to be announced.",
  },
  {
    id: "soon-youtube",
    section: "Coming soon",
    kind: "content",
    eyebrow: "YouTube auto upload",
    title: "Fully automated video uploads.",
    bullets: [
      "Scheduled publishing when you want it live",
      "Automatic titles, descriptions, and tags",
      "Playlist assignment and thumbnail upload",
      "Privacy and publish settings handled in-flow",
    ],
    mock: "roadmap",
    footerNote: "Coming soon — timing to be announced.",
  },
  {
    id: "soon-facebook",
    section: "Coming soon",
    kind: "content",
    eyebrow: "Facebook Reels auto upload",
    title: "One-click publishing to Facebook Reels.",
    bullets: [
      "Automatic captions and hashtags",
      "Scheduled posting for Reels",
      "Cross-platform distribution from the same batch",
      "Less manual jumping between Studio and Meta",
    ],
    mock: "roadmap",
    footerNote: "Coming soon — timing to be announced.",
  },
  {
    id: "soon-pipeline",
    section: "Coming soon",
    kind: "content",
    eyebrow: "Unified publishing pipeline",
    title: "One studio loop to every platform.",
    bullets: [
      "Music → artwork → video → thumbnail → metadata → publish",
      "Destinations: YouTube, Facebook Reels, DistroKid",
      "More platforms planned after the core three",
      "One studio loop instead of six disconnected tools",
    ],
    mock: "publishEverywhere",
    footerNote: "Features ship when ready — not on a fixed calendar.",
  },
  {
    id: "thank-you",
    section: "Thank you",
    kind: "cta",
    eyebrow: "Thank you",
    title: "Finish profiles, open the desktop studio, ship the next batch.",
    bullets: [
      "Complete or review Profiles in this panel",
      "Download / open the CAMXORA desktop app",
      "Run one full pipeline end-to-end before scaling",
      "Lean on the monetization guarantee while you follow the workflow",
    ],
    footerNote: "Need help? support@camxora.com",
  },
];
