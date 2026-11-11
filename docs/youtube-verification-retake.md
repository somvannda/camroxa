# YouTube verification — retake kit

Google's reply asks for a **new demonstration video** that proves each scope is necessary, shows
the effect on the user's own account, and comes with test credentials. This kit is the checklist and
the script for that recording.

## 0. Setup before you press record

| Item | Why |
|---|---|
| A **fresh Google account** that has never authorised CAMXORA | consent then shows exactly our three scopes, not `openid` / `userinfo.*` from a previous sign-in |
| A channel on that account | the upload target |
| One **empty playlist** (e.g. `CAMXORA Demo`) | proves `playlistItems.insert` |
| A 16:9 thumbnail file placed as `thumbnail-16x9.png` in the run folder | proves `thumbnails.set` |
| An already-merged MP4 in Progress | so the demo needs no music generation |
| Test CAMXORA account | credentials for Google |
| Credits on that account | an upload costs 5; wallet must not block |

Record full screen, 1280×720 or better, mic on, **one unedited take**, 5–7 minutes.

## 1. Recording script

**0:00 — intro.** “This is a live demonstration of CAMXORA (latest build) publishing to YouTube through
project 2647196562. I will show each requested scope and its effect on the account.”

**0:20 — `youtube.readonly` (read only at connect).**
Settings → Publication. Point at the Playlist dropdown listing `CAMXORA Demo` from the channel.
Say: “The app reads only the channel name and the playlist list, once, at connect time.”

**1:00 — consent screen (scope matching).**
Settings → Profiles → **Connect YouTube**. On Google's screen:
- click **Show all services** so every scope is expanded;
- pause on each line and read it: *Manage your YouTube videos*, *View your YouTube account*, and the
  force-ssl line;
- say: “These are exactly the three scopes configured for this project; nothing else is requested.”

**2:00 — approve and pick the channel.** Show *Connected: `<channel>`* back in Settings.

**2:30 — baseline in YouTube Studio.** Open a second window: **Content** list (the video is not
there) and the `CAMXORA Demo` playlist (empty). Say: “This is the state before the upload.”

**3:00 — `youtube.upload`.**
Progress → right-click the merged row → **Upload to YouTube**. Let the percentage run to 100%, then
**Publishing**, then **Published** with the link. Say: “One upload, triggered by the user, of the
user's own file. No re-encoding.”

**4:30 — source account impact.**
Back in YouTube Studio → refresh **Content**: the new video is listed. Open it and show the
**custom thumbnail**. Say: “`thumbnails.set` applied the customer's own thumbnail.”

**5:00 — `youtube.force-ssl`.**
Open `CAMXORA Demo` → the video is inside. Say: “`playlistItems.insert` added the video to the
playlist the customer selected. We never delete videos, edit ratings or touch comments; the broader
scope description is Google's wording, not our usage.”

**5:30 — close.** “That is the entire use of the API: one upload, channel and playlist reads at
connect, and two writes — thumbnail and playlist insert.”

## 2. Test credentials (for the reply)

Create in the admin portal: **Users → New user**

- Email: `review@camxora.com`
- Password: generate a strong one, share it in the reply
- Credits: add ~500 (Admin → Users → adjust balance)
- Profile: `Review Channel` with Publication defaults (unlisted, Category Music, AI use = Yes)

Then verify the login works from a **clean browser profile** and that the desktop build on
`https://camxora.com/download` (current build) accepts it. If Cloudflare Turnstile challenges the login,
tell me before replying — Google must not hit a bot wall.

## 3. Reply email

```
Hello,

Thank you for the review. A new demonstration video addresses each point:

1. Source account impact — the video shows YouTube Studio before and after: the uploaded video
   appears with the customer's thumbnail, and the selected playlist gains that video. We never
   delete content, edit comments or ratings.
2. Consent screen — every requested scope is expanded and read aloud: youtube.upload (the single
   user-triggered upload), youtube.readonly (channel name and playlist list read at connect time),
   youtube.force-ssl (thumbnails.set and playlistItems.insert only).
3. Scope matching — recorded with a fresh Google account that had no prior grants to our client, so
   the consent screen shows exactly the three scopes configured for project 2647196562.

Demo video: <UNLISTED LINK>

Test credentials:
  App: https://camxora.com/download (latest desktop build)
  Email: review@camxora.com
  Password: <PASSWORD>

Steps:
  1. Install, sign in with the credentials above.
  2. Settings -> Profiles -> Connect YouTube, consent with your own Google account, pick a channel.
  3. Settings -> Publication: the playlist list loads from that channel.
  4. Progress -> right-click the merged row -> Upload to YouTube.
  5. The row shows progress, then Published with the video link.

Publishing status remains "In Production".

Kind regards,
Somvannda
```

## 4. Traps to avoid

- Do not add or remove a scope before recording — the video must match the console exactly.
- Do not show the app while the consent screen is collapsed; the reviewer explicitly asked for
  “Show all services”.
- Do not use your own Google account for the demo: prior `openid`/`userinfo` grants make the consent
  list longer than the configured scopes and trigger the “scope matching” objection again.
- Keep the recording **unlisted**, link it in the reply, and leave it up until the review closes.
