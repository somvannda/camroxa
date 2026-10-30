# Song ⋮ menu — delta from Suno's catalogue

Suno ships **74 `songActions` keys**. Ours covers 21. This is the mechanical
gap list (no guessing): every key below exists in their bundle.

Legend: ✅ in our menu · ➕ missing · 🔒 plan/paywall-only on Suno (we gate by
credits, not plans)

## Core playback

| Key | Ours |
|---|---|
| `play` / `pause` | ✅ playbar equivalent |
| `playCount` | ➕ not shown |
| `playbarLike` `playbarDislike` `playbarShare` `playbarRemix` `playbarComment` | ➕ playbar actions |

## Library actions

| Key | Ours |
|---|---|
| `like` / `likeWithTitle` | ✅ |
| `dislike` / `dislikeAction` | ✅ |
| `notInterested` | ➕ |
| `pinToProfile` / `unpinFromProfile` | ➕ |
| `pinToProject` | ➕ |
| `moveToWorkspace` | ✅ (Manage ▸) |
| `moveToTrash` | ✅ |
| `deletePermanently` | ➕ (trash page only) |
| `restoreToLibrary` | ✅ (trash page) |
| `addToPlaylist` / `removeFromPlaylist` | ✅ add ➕ remove |
| `removeFromAlbum` | ➕ |

## Share / copy

| Key | Ours |
|---|---|
| `copySongLink` | ✅ Copy link |
| `copyLinkAtCurrentTime` | ➕ |
| `shareWithFriends` / `shareWithTitle` | ✅ Share sheet |
| `comment` / `commentAction` / `allowComments` | ➕ |

## Download

| Key | Ours |
|---|---|
| `mp3Audio` `wavAudio` | ✅ |
| `m4aAudio` | ➕ |
| `downloadUnavailableReason` | ➕ no reason shown |
| `downloadRemixContestUnavailableReason` | ➕ n/a |

## Remix / Edit

| Key | Ours |
|---|---|
| `remix` | ✅ submenu |
| `cover` | ✅ |
| `reusePrompt` | ✅ |
| `mashup` | ✅ |
| `extend` | ✅ |
| `replaceSection` | ✅ API wrapped, UI modal |
| `crop` | ✅ (derive) |
| `adjustSpeed` + `adjustSpeedDisabledReason` | ✅ (derive) |
| `fadeIn` / `fadeOut` | ✅ (derive) |
| `remaster` + `remasterTooLongReason` | ✅ |
| `getStems` | ✅ |
| `getStemsMidi` | ✅ (same endpoint, MIDI not downloadable) |
| `addVocal` | ➕ |
| `addInstrumental` | ➕ |
| `voice` | ✅ |
| `sampleThisSong` | ✅ |
| `useAsSample` | ➕ (distinct from Sample — semantics TBD) |
| `samplePack` | ➕ |
| `useAsInspiration` | ➕ |

## Publish / distribution

| Key | Ours |
|---|---|
| `publish` | ✅ |
| `unpublish` | ➕ |
| `showInHooksFeed` / `videoCoverShownInHooksFeed` / `videoCoverHiddenFromHooksFeed` | ➕ |
| `allowRemixes` | ➕ |
| `openSongInNewTab` | ➕ |
| `openInStudio` | ✅ |
| `openInEditor` | ✅ |
| `songDetails` | ✅ |
| `songRadio` | ✅ |
| `manage` | ✅ |
| `getHumanHelp` | ➕ |

## Paywall / state keys (Suno plan model)

`upgradeForFullSong`, `streamingDisabledReason`, `failedToUnlockSong`,
`unlockingSong` — Suno's plan/preview gates. Camxora is credit-based, so these
map to "insufficient credits" messaging rather than a plan upsell.

## What this proves

Nine items we never listed are real Suno controls: `addVocal`,
`addInstrumental`, `useAsSample`, `samplePack`, `pinToProfile`,
`pinToProject`, `copyLinkAtCurrentTime`, `comment`/`allowComments`,
`openSongInNewTab`, `unpublish`, `showInHooksFeed`, `removeFromAlbum`.

They stay unbuilt until each one's contract is captured — but they are no longer
unknown.
