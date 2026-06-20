## YouTube Upload Integrity + No-Reupload - Design

### Product Goal
Prevent accidental duplicate uploads and ensure uploads only start when the merged MP4 is complete and valid.

### Problems Observed (Boss report)
- A channel (Bass Vortex) appears to upload the same batch repeatedly.
- Upload can start while the merged MP4 is still being written.
- Thumbnail/playlist fixes should not require reuploading the entire video when a YouTube video id already exists.

---

## User-Facing Behavior

### A) No Duplicate Reuploads
- If an upload job enters `FAILED`, it should stay failed until Boss explicitly hits Retry.
- Auto-scanning for merged outputs must not resurrect failures automatically.

### B) Upload Readiness Gate (Merged MP4)
- The app must only enqueue/upload a merged MP4 when it is stable:
  - file exists
  - file size is above a minimum threshold
  - file modification time is not “very recent”
  - optionally, `ffprobe` can read a non-zero duration

### C) Existing Upload Edit (No Reupload)
When `youtube_video_id` exists for a job:
- Do not reupload the MP4.
- Allow “post actions”:
  - set/replace thumbnail
  - add to playlist (only when previously failed)

### D) Post-Upload Processing Check
After upload returns a `video_id`, the app should query YouTube for `processingStatus`:
- If YouTube reports processing failure/rejection, mark the job failed (without reupload loop).

