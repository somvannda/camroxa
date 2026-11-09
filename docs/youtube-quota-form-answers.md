# YouTube API Services — Audit & Quota Extension form: copy-paste answers

Form: https://support.google.com/youtube/contact/yt_api_form
(reached from **Cloud Console → APIs & Services → YouTube Data API v3 → Quotas → "Apply for higher quota"**)

Fill top to bottom. Text in `code blocks` is meant to be pasted verbatim.
Anything marked **⚠ needs your input** must be replaced.

---

## 1. Contact / project

| Field | Answer |
|---|---|
| Company / developer name | `CAMXORA` |
| Contact email | `duke@camxora.com` |
| Project number | `2647196562` |
| Application name | `CAMXORA` |
| Website | `https://camxora.com` |
| Is this a public application? | `Yes` |
| Platforms | `Desktop application + web account portal` |

---

## 2. Which API / scopes

| Field | Answer |
|---|---|
| API | `YouTube Data API v3` |
| Scopes used | `https://www.googleapis.com/auth/youtube.upload`, `https://www.googleapis.com/auth/youtube.readonly`, `https://www.googleapis.com/auth/youtube.force-ssl` |
| Methods used | `videos.insert`, `thumbnails.set`, `playlistItems.insert`, `channels.list`, `playlists.list` |

---

## 3. "Describe how your application uses the YouTube API"

```
CAMXORA is a desktop studio for independent musicians. A customer turns their own
music tracks into a finished video (lyrics video, artwork, mix) inside the app, then
chooses to publish it to a YouTube channel they own and have connected themselves.

The app uploads the customer's own merged MP4 file, unmodified. It is a resumable
upload (uploadType=resumable, 16 MB chunks, 1-3 GB per file). No transcoding, no
re-encoding, no derivative content, no third-party media.

API calls per published video:
  videos.insert          1 x 1600 units  (the upload itself)
  thumbnails.set         1 x 50 units    (customer's own 16:9 thumbnail)
  playlistItems.insert   1 x 50 units    (optional, playlist chosen by the customer)
  channels.list / playlists.list         (read at connect time, 1 unit each)

The app does not use search, does not read other channels, does not collect comments,
analytics or metadata for any purpose other than displaying the customer's own channel
name and playlist list in Settings.
```

---

## 4. "How do users authorise your application?"

```
Standard Google OAuth 2.0 authorisation-code flow with PKCE over HTTPS.

1. The customer opens Settings -> YouTube -> Connect channel inside CAMXORA.
2. Google's consent screen is shown; the customer picks the channel explicitly.
3. The refresh token is stored encrypted at rest (Fernet/AES, key held only on our
   server) and is never exposed to the desktop client.
4. Each upload uses a short-lived access token (1 hour) minted server-side.
5. Disconnecting in the app deletes the stored token; customers may also revoke at
   myaccount.google.com at any time.
```

---

## 5. Expected usage

| Field | Answer |
|---|---|
| Current active users | `⚠ your current count (e.g. 5)` |
| Users in 6 months | `⚠ realistic number (e.g. 50)` |
| Videos uploaded per user per day | `5-10` |
| Estimated uploads per day at peak | `⚠ e.g. 200` |
| Quota units requested per day | `500000` |
| Why that number | see below |

```
500,000 units/day covers roughly 300 video uploads per day (videos.insert is 1,600
units each), plus thumbnails, playlist inserts and channel reads. A typical customer
run is 5-10 videos, so this supports ~30 daily active customers with headroom.

We are not asking for more than we can justify: a full batch for one customer is
about 16,000 units, and we schedule batches across the day.
```

---

## 6. Data handling / compliance questions

If the form asks any of these, answer exactly:

| Question | Answer |
|---|---|
| Do you store YouTube API data? | `Yes - only channel name/id, playlist names, and upload status, as part of the customer's connection record.` |
| Do you share it with third parties? | `No.` |
| Do you use it for advertising or profiling? | `No.` |
| Do you sell API data? | `No.` |
| Do you use it to train models? | `No.` |
| Retention | `Until the customer disconnects or deletes their account; then deleted.` |
| Deletion request contact | `duke@camxora.com` |
| Do you charge users? | `Yes - CAMXORA is paid software. YouTube API data itself is not sold.` |
| Does your app modify or re-upload third-party content? | `No - only the customer's own files to the customer's own channel.` |

---

## 7. Attachments / links

| Item | Value |
|---|---|
| Terms of Service | `https://camxora.com/terms` |
| Privacy Policy | `https://camxora.com/privacy` |
| Demo video (unlisted YouTube) | **⚠ record after the native upload build; paste the unlisted link** |

### Demo video script (2–4 minutes, unedited)

1. Open CAMXORA, sign in.
2. Settings → YouTube → **Connect channel** → Google consent → pick channel.
3. Show the channel name now displayed in Settings.
4. Open a finished video, click **Upload to YouTube**.
5. Let the progress reach **Published**.
6. Switch to YouTube in a browser and show the video on that channel.
7. Say the date and that it is a real end-to-end upload through this project.

---

## 8. Before you press submit

- [ ] Consent screen publishing status is **In production**
- [ ] Scopes `youtube.upload`, `youtube.readonly`, `youtube.force-ssl` are on the consent screen
- [ ] Redirect URI `https://api.camxora.com/api/v3/youtube/oauth/callback` is registered
- [ ] `https://camxora.com/terms` and `/privacy` load publicly
- [ ] Demo video is **unlisted** and the link is set to "anyone with the link"
- [ ] Numbers in section 5 are ones you can defend in a follow-up email

---

## 9. If a field doesn't match this sheet

Google changes the form wording occasionally. Paste the field text to me and I'll give
you the exact answer. Do not guess on: project number, scopes, or requested units.
