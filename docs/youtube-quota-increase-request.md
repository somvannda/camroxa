# YouTube Data API — quota increase request (ready to submit)

Use this document when filling Google's **YouTube Data API v3 quota extension** form
(`console.cloud.google.com` → APIs & Services → YouTube Data API v3 → Quotas →
*Apply for higher quota*, or the audit form linked from the quota page).

Everything below is written to be pasted field-by-field. Replace the two placeholders:

- `<PROJECT_NUMBER>` — Google Cloud project number (not the id), shown on the project dashboard.
- `<CONTACT_EMAIL>` — an address on the product domain (e.g. `support@camxora.com`).

---

## 1. Request values

| Field | Value |
|---|---|
| API | YouTube Data API v3 |
| Quota units per day requested | **500,000** |
| Current quota | 10,000 |
| Primary method driving usage | `videos.insert` (1,600 units each) |

Capacity that buys: **~300 uploads/day** on the platform Google client
(500,000 ÷ 1,600 ≈ 312), with headroom for `thumbnails.set` (50), `playlistItems.insert`
(50) and `channels.list` (1).

Why this size: the product publishes finished music videos, one per customer run.
A typical customer run is 5–10 videos, so 30 active customers ≈ 150–300 uploads/day.
Ask for the number you can defend; a 250,000–500,000 request with real numbers is
more likely to be granted than a speculative million.

---

## 2. Project / company details

| Field | Suggested answer |
|---|---|
| Company / organisation | CAMXORA |
| Website | `https://camxora.com` |
| Contact email | `<CONTACT_EMAIL>` |
| Project number | `<PROJECT_NUMBER>` |
| App type | Desktop application + web account portal |
| Users | Paying customers who own the YouTube channels they publish to |

---

## 3. "Describe your application and how it uses the API"

> CAMXORA is a desktop studio that turns a customer's own music tracks into finished
> videos (lyrics video, artwork, mix). YouTube upload is a delivery step: the customer
> clicks *Upload to YouTube* on one of their own finished videos, or enables automatic
> upload for a batch they created. The app then uploads **the customer's own merged MP4,
> unmodified** (no transcoding, no re-encoding, no derivative content) to a channel the
> customer connected to their own account.
>
> API use is limited to:
>
> - `videos.insert` — one resumable upload per published video (1,600 units)
> - `thumbnails.set` — the customer's own 16:9 thumbnail (50 units)
> - `playlistItems.insert` — optional, adds the video to a playlist the customer picked (50 units)
> - `channels.list` / `playlists.list` — read the channel name and the playlist list at connect time (1 unit each)
>
> Nothing else: no searching, no scraping, no reading other channels' videos, no comments,
> no analytics harvesting, no resale of API data.

---

## 4. "How do users authenticate and authorise?"

> Google OAuth 2.0 authorisation-code flow with PKCE over HTTPS, initiated from the
> CAMXORA app. Scopes: `youtube.upload`, `youtube.readonly`, `youtube.force-ssl`.
>
> - Each customer consents on Google's own screen and picks the channel explicitly.
> - The refresh token is stored **encrypted at rest** (AES/Fernet, key from a server-side
>   master key) and is never exposed to the desktop client.
> - Short-lived access tokens (1 hour) are minted server-side per upload; revoking access
>   or deleting the connection deletes the stored token (`DELETE /api/v3/youtube/profiles/{id}/connection`).
> - Customers can disconnect at any time in Settings, or revoke at `myaccount.google.com`.
> - A customer may also supply their own Google OAuth client ("bring your own app"), in
>   which case credentials are validated against Google before storage and encrypted the
>   same way.

---

## 5. "Estimated usage"

| Item | Value |
|---|---|
| Uploads today | < 10/day (early access) |
| Uploads at the requested quota | up to 300/day |
| Videos per customer run | 5–10 |
| Average file size | 1–3 GB |
| Upload method | resumable (`uploadType=resumable`, 16 MB chunks) |
| Peak window | customer local time, spread across the day |

---

## 6. "Does your app comply with the YouTube API Services Terms and Developer Policies?"

> Yes. Specific controls:
>
> - **User-owned content only**: the app uploads a file the customer created on their own
>   machine, to a channel the customer owns and connected themselves.
> - **No re-encoding**: the original MP4 is sent as-is; the app's own local renderer runs
>   before upload and is not an API function.
> - **No data retention beyond operation**: API responses (channel id, title, playlist
>   names) are stored only as part of the customer's connection record and are deleted
>   when the connection is removed.
> - **No circumvention**: one project, no quota-sharing tricks, no automated account
>   creation, no proxy pools.
> - **Deletion**: disconnecting removes the stored refresh token; deleting an account
>   removes all connection and upload records.
> - **Quota discipline**: a per-day counter stops scheduling uploads once the project
>   allowance is near, and resumes the next quota day instead of retrying.

---

## 7. Evidence to attach (this is what gets requests approved)

Record **one unedited screen recording**, 2–4 minutes:

1. Sign in to the app, open **Settings → YouTube → Connect channel**.
2. Show the Google consent screen (channel picker visible).
3. Back in the app, show the connected channel name.
4. Pick a finished video, click **Upload to YouTube**, let the progress run to `Published`.
5. Open YouTube in a browser and show the newly uploaded video on that channel.

Also attach:

- a screenshot of the OAuth consent screen configuration (scopes + redirect URI),
- one paragraph on the architecture (desktop → API → Google; token broker; encrypted storage),
- the privacy policy and terms URLs.

---

## 8. While waiting for the decision

Quote these in customer-facing copy and in the app:

- Default platform quota allows ~6 uploads per day, **per project**.
- The app shows `Daily YouTube quota reached — resumes tomorrow` rather than a retry storm.
- Customers who need more today can **connect their own Google app** (Settings → YouTube →
  *Use my own Google app*): their own project has its own 10,000 units/day, and they can
  request their own increase.

---

## 9. If the request is rejected

Ask for the reason (usually one of: unclear use case, thin evidence, unverified app,
commercial use of a personal account). Typical remedy:

1. Complete app **verification** first (brand + sensitive scopes), then re-apply.
2. Re-apply with measured production numbers instead of projections.
3. Re-verify that the recording shows the real flow, not a mockup.
4. Use the desktop → provider path as overflow until the increase lands, so customers are
   never blocked.
