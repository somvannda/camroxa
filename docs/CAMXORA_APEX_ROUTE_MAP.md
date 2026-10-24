# CAMXORA apex route map

Draft route map for the new `camxora.com` app. Legacy redirects are only enabled after cutover approval.

## Public

| Prototype | New route | Notes |
|---|---|---|
| index.html | `/` | Listen-first home |
| discover.html | `/discover` | Sticky filters, banner, shelves |
| charts.html | `/charts` | Time and region filters |
| search.html | `/search` | Server-rendered query page |
| artist.html | `/artist/[id]` | Artist profile |
| playlist.html | `/playlists/[id]` | Playlist detail |
| - | `/albums/[id]` | Reuse catalog data |
| studio.html | `/studio` | Desktop download and features |
| developers.html | `/developers` | API marketing; links to musicapi host |
| artist-program.html | `/artist-program` | Program landing |
| pricing.html | `/pricing` | Plans and packs from API |
| about.html | `/about` | Content migration |
| blog.html | `/blog` | Reuse blog data |
| contact.html | `/contact` | Contact form |
| legal.html | `/legal` | Terms, privacy, cookies, copyright, acceptable use, data deletion |
| - | `/changelog` | Existing release notes |

## Signed-in / app

| Prototype | New route | Notes |
|---|---|---|
| login.html / signup.html | `/login`, `/signup` | Existing auth endpoints |
| forgot-password.html / reset-password.html | `/forgot-password`, `/reset-password` | Existing auth endpoints |
| verify-email.html | `/verify-email` | Existing auth endpoints |
| create.html | `/create` | Studio-first create flow |
| library.html | `/library` | Tracks, albums, playlists, likes |
| account.html / settings.html | `/account` | Profile, plan, usage, preferences |
| notifications.html | `/notifications` | Notification list |
| invite.html / redeem.html | `/invite`, `/redeem` | Invite and redeem |
| checkout.html | `/checkout` | Sandbox/test only until cutover |
| community.html | `/community` | Feed and challenges |
| artist-dashboard.html | `/artist-dashboard` | Artist KPIs |
| publish.html | `/publish` | Publish a track |

## Legacy mapping - after cutover approval only

| Old | New |
|---|---|
| `music.camxora.com/` | `camxora.com/` |
| `music.camxora.com/explore` | `/discover` |
| `music.camxora.com/genres` | `/discover` |
| `music.camxora.com/profile` | `/account` |
| `music.camxora.com/register` | `/signup` |
| `music.camxora.com/create` | `/create` |
| `music.camxora.com/library` | `/library` |
| `music.camxora.com/pricing` | `/pricing` |
| `camxora.com/terms` | `/legal#terms` |
| `camxora.com/privacy` | `/legal#privacy` |
| `camxora.com/cookies` | `/legal#cookies` |
| `camxora.com/download` | `/studio` |

## Not changed

- `music.camxora.com` - remains live and untouched.
- `music.sandbox.camxora.com` - remains the old music reference.
- `musicapi.camxora.com` and `admin.musicapi.camxora.com` - untouched.
- `app.camxora.com` - retained for billing/API keys in v1.
