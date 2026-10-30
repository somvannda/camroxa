# SUNO STUDIO WORKFLOW DOCUMENTATION

End-to-end journeys. Each step lists the surface and the observable result. Used as
the manual test script in `TESTING_AND_ACCEPTANCE_CRITERIA.md`.

## W-A. First project (new user)

1. `/studio` → signed out: marketing page, no broken studio controls.
2. Sign in → `/studio` shows the home with an empty state and a single primary CTA.
3. "New project" → project created → editor opens with a skeleton, then an empty
   arrangement.
4. Empty state offers "Create a track". Creating audio + MIDI tracks works.
5. Rename the project in the header. Reload the page; the name persists.
6. Play: silence, transport advances, clock and bar.beat advance.
7. Stop, reload: the arrangement and BPM persist.

**Pass:** after step 7 a fresh session sees the same project without any Save click.

## W-B. Bring a generated song into an arrangement

1. `/create` → generate a song (existing flow) → wait for both variants.
2. From the clip menu: "Open in Studio" (or `/studio` → start from a song).
3. Editor opens with that clip on a track at 0.
4. Drag it to bar 3; split at bar 5; duplicate the second half.
5. Undo twice, redo once.
6. Close the tab, reopen via `/studio` resume card.

**Pass:** arrangement matches what was left, including splits and duplicates.

## W-C. Build a multi-track mix

1. Add 3 audio clips on 3 tracks, 1 MIDI track with a melody.
2. Per track: set volume and pan; mute one; solo another and hear only it.
3. Inspector: EQ, filter, reverb send, compression, drive on the MIDI track.
4. Automation: add 3 volume points and 2 pan points; play and confirm movement.
5. Master: fader, EQ, compression, drive; watch the spectrum and meters.

**Pass:** audible, reversible (undo restores every mix value), persisted on reload.

## W-D. Export

1. Export → full mix → WAV. File downloads, duration equals project duration.
2. Export → loop range → MP3. Duration equals loop length within 50 ms.
3. Export → per-track → ZIP with one file per track.
4. Export → project JSON. Re-import it into a new session.

**Pass:** re-imported project is arrangement-identical and sounds identical.

## W-E. Stems and paid operations

1. Select a generated clip → Separate stems (2-stem).
2. Dialog shows cost from `pricing`. Confirm.
3. Clip shows a pending state; on completion, stems appear on new tracks.
4. Balance decreased by exactly the shown cost.
5. Force a failure (e.g. cancel/insufficient credits): message shown, credits not
   silently lost.

## W-F. Collaboration

1. Share → create an edit link with a 1-day expiry → copy.
2. Open in another browser/profile; the shared page loads with collaborators and
   comments.
3. Edit in profile B; profile A receives the update (polling) and offers to apply.
4. Post a comment from B; A sees the unread badge.
5. Revoke the link; B's next request terminates with a clear message.
6. Fork from B before revocation; the forked project appears in B's home.

## W-G. Failure paths

1. Stop the API → edit → save shows `error` with retry; the edit is not lost.
2. Restart the API → retry succeeds.
3. Open a project id you do not own → 403 terminal state, no data shown.
4. Open a revoked share token → terminal state with explanation.
5. Generation refused for policy → the clip states the reason and offers no retry
   until the input changes.

## W-H. Advanced editing

1. MIDI track → piano roll → draw notes across 2 bars → quantize.
2. Play; notes sound. Export MIDI; re-import; notes round-trip.
3. Reverse a clip; fade in/out; change speed with pitch preserved.
4. Alternate takes: add a take, switch, confirm playback follows the active take.

## Coverage note

W-A through W-H are the acceptance journeys. W-A, W-B, W-D(4) and W-G are the
minimum bar for calling the Studio "usable"; W-E and W-F are the minimum for
"professional".
