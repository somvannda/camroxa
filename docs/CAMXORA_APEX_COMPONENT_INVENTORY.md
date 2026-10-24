# CAMXORA apex component inventory

Inventory of template primitives to extract from `web-camxora/design-reference/app.css` and the HTML pages.

## Shell

| Component | Current source | Notes |
|---|---|---|
| App grid | `.app` | Sidebar + main |
| Sidebar | `.sidebar`, `.side-scroll`, `.brand`, `.nav`, `.playlists`, `.side-grid` | Keep bottom account slot |
| Topbar | `.topbar`, `.search`, `.top-actions` | Guest and signed-in states |
| Content | `.content`, `.page` | Scroll container |
| Footer | `.site-footer` | Full footer on app pages |
| Player | `.player`, `.p-now`, `.p-center`, `.p-right`, `.p-queue-panel` | New visual layer over existing player logic |

## Identity and account

| Component | Source | Notes |
|---|---|---|
| Logo | `camxora-logo.svg` | Original asset only |
| Guest offer | `.guest-offer`, `.guest-signin-row` | Start creating / sign in |
| Member credits | `.member-credit`, `.member-profile` | Balance and profile |
| Credits modal | `.modal-backdrop`, `.pack-grid` | Data from API |
| Auth forms | `.auth-page`, `.auth-card`, `.auth-field` | Existing auth endpoints |

## Music surfaces

| Component | Source | Notes |
|---|---|---|
| Track card | `.card`, `.card .art`, `.card .play` | Green play action |
| Continue card | `.continue-card`, `.cc-bar` | Resume listening |
| Hero | `.hero`, `.hero-img`, `.hero-copy` | Image masks required |
| Discover banner | `.banner`, `.banner-copy` | Percent-based mask |
| Product band | `.home-cta`, `.studio-band`, `.api-band` | Right-side image blend |
| Mood tile | `.mood`, `.mood-grid` | Keep restrained gradients |
| Creator card | `.creator-card`, `.home-creator` | Follow state |
| Chart table | `.chart-table`, `.chart-row` | Movement labels, preview play |
| Playlist/album | `.playlist-cover`, detail pages | Reuse catalog data |

## Forms and controls

| Component | Source | Notes |
|---|---|---|
| Button | `.btn`, `.btn-primary`, `.btn-ghost` | Primary `#8B00FF`, 10px radius |
| Header auth | `.header-auth` | 96 x 36 |
| Inputs | `.input`, `.select`, `.textarea` | Focus ring `#C084FC` |
| Tabs | `.tabs`, `.tab` | Accessible selected state |
| Chips | `.chip-row`, `.chip2` | Filter state |
| Modal | `.modal-backdrop`, `.modal` | Focus trap required |
| Create dock | `.create-dock` | Sticky above player |
| Blueprint | `.blueprint`, `.bp-wave` | Green waveform accent |

## Data and status

| Component | Source | Notes |
|---|---|---|
| Stats row | `.stats-row`, `.stat-card` | Artist dashboard |
| Generation row | `.gen-row` | Create history |
| Payout row | `.payout-row` | Artist dashboard |
| Notifications | `.notif-row` | List and menu |
| Empty/loading/error | - | New shared states required |

## Cleanup before porting

- Remove dead light-mode CSS.
- Remove old glass-button overrides.
- Replace Google Fonts with self-hosted Inter.
- Replace Unsplash URLs with owned/B2 assets.
- Replace static prices/packs/generations with API data.
- Replace player simulation with existing player engines.
- Add accessible focus, labels, and reduced-motion states.
