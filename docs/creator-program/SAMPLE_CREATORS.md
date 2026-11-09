# Sample Creator Pack (Deferred)

**Status:** Design fixture + requirement. **Not seeded. Not a launch blocker.**
**Target:** Phase 4 (demo / marketing / QA), after identity and publishing are live.
**Related:** [README](./README.md) · [BRD](./BRD.md) · [Product Spec](./PRODUCT_SPEC.md) · [Roadmap](./ROADMAP.md)

---

## 1. Decision

We are **keeping the sample pack as a specification and fixture now**, and **deferring the actual seed + real SLai avatars + audio** until:

1. `creator_profiles`, `creator_releases`, and the publish pipeline exist (Phase 1–2).
2. A valid SLAI key is configured (the local key currently returns `AUTH_002: Invalid API key`).
3. There is a demo/marketing need (Phase 4).

**Why not now**

- The database tables the seed would write to do not exist yet.
- Real audio for 65 tracks costs credits and depends on the generation pipeline.
- The sample catalog must never leak into production as if it were real creators.
- None of this blocks the Creator Program launch.

**Why keep the fixture now**

- It forces the requirement to be concrete: names, categories, tiers, Khmer lyrics, prompt policy, image policy.
- It gives QA and design something to build against once the tables land.
- It is docs-only: zero runtime, build, or migration impact.

---

## 2. Fictional disclosure

Every creator in this pack is **fictional**. Names, handles, bios, links, and images are invented for demo purposes.

- Do **not** present them as real artists.
- Do **not** use real people's names, faces, or likenesses.
- Public demo pages must show a **“Sample creator”** label until replaced.
- Before a public launch, either remove the pack or clearly mark it as demo content.

---

## 3. Roster (8 creators)

| Handle | Name | Khmer name | Category | Tier | AI disclosure | Release |
|---|---|---|---|---|---|---|
| `sokha` | Sokha Chan | សុខា ចាន់ | Khmer Pop | Verified | AI-assisted | **3 albums × 10 tracks** |
| `vannak` | Vannak Rith | វណ្ណៈ រិទ្ធ | Khmer Hip Hop | Verified | AI-assisted | EP × 5 |
| `dara` | Dara Malis | តារា ម៉ាលីស | R&B | Verified | AI-assisted | EP × 5 |
| `kanya` | Kanya Sopheak | កញ្ញា សុភ័ក្ត្រ | Khmer Ballad | Verified | Original | EP × 5 |
| `rithy` | Rithy Bun | រិទ្ធី ប៊ុន | EDM | Verified | AI-generated | EP × 5 |
| `chenda` | Chenda Meas | ចេនដា មាស | Traditional Fusion | Verified | Original | EP × 5 |
| `pisey` | Pisey Nou | ពិសី នូ | Lo-fi | Creator | AI-assisted | EP × 5 (instrumental) |
| `sovan` | Sovan Reach | សុវណ្ណ រាជ | Khmer Rap | Verified | Original | EP × 5 |

**Category coverage:** Pop, Hip Hop, R&B, Ballad, EDM, Traditional Fusion, Lo-fi, Rap. Additional sub-genres are listed in `creators.json`.

---

## 4. Discography requirement

| Creator | Release | Type | Tracks | Language | Notes |
|---|---|---|---|---|---|
| Sokha | *Bassac Moon* | Album | 10 | Khmer | Night-drive synth-pop |
| Sokha | *Rainy Season* | Album | 10 | Khmer | Monsoon ballad |
| Sokha | *Golden Hour* | Album | 10 | Khmer | Bright dance-pop |
| Vannak | *Street Temple* | EP | 5 | Khmer | Boom-bap |
| Dara | *River Lights* | EP | 5 | Khmer | Neo-soul R&B |
| Kanya | *Letters Home* | EP | 5 | Khmer | Piano ballad |
| Rithy | *Neon Bay* | EP | 5 | Khmer hooks | Big-room EDM |
| Chenda | *Golden Fibers* | EP | 5 | Khmer | Traditional fusion |
| Pisey | *Rainy Kampot* | EP | 5 | Instrumental | Lo-fi |
| Sovan | *Concrete Khmer* | EP | 5 | Khmer | Conscious rap |

**Total:** 10 releases, **65 tracks**.

### Khmer-first lyrics

- Every album and track uses `language: "km"`.
- Every vocal track carries `lyrics_km`.
- Instrumentals are explicitly `instrumental: true` and have no lyrics (Pisey; Rithy tracks are vocal-hook led).
- English translations are **not required for the seed**; they are a QA aid and can be added as `lyrics_en` later.
- Do not machine-translate and call it final. A native Khmer reviewer must approve public lyrics.

### Prompt policy

- **No production prompt is reused.** `prompts.json` contains a new prompt for every artist and every album.
- Each track’s `style_prompt` is `album prompt + track modifier`, so the album has a coherent sound while each track has its own direction.
- Prompts include genre, BPM range, key, instrumentation, vocal type, language, mix, and mood.
- Prompts must not name real artists or request impersonation.

---

## 5. Avatar requirement

- One square (1:1) portrait thumbnail per creator.
- Generated with **SLai** using the `avatar_prompt` in `creators.json`.
- Fictional people only; no real-person likeness.
- No text, logos, or watermarks in the image.
- Stored at `sample-creators/avatars/<handle>.png`.
- Suggested size: 1024×1024 source, 512×512 display.

### Current status

| Item | Status |
|---|---|
| SLai generator script | Ready: `scripts/creator-program/generate_sample_avatars.py` |
| Local SLAI key | **Invalid** — `AUTH_002: Invalid API key` |
| Current avatars | Local placeholders: `scripts/creator-program/make_placeholder_avatars.py` |
| Replace with SLai | Run the generator once a valid key is in the key pool |

**To regenerate with SLai**

```bash
python scripts/creator-program/generate_sample_avatars.py --check
python scripts/creator-program/generate_sample_avatars.py --force
```

The script reads `platform_api/.env`, decrypts an active `slai` key from `api_key_entries` in memory, and never prints or writes the secret.

---

## 6. Files

| File | Purpose |
|---|---|
| `creators.json` | Roster: names, handles, Khmer names, categories, bios, links, palette, avatar prompts |
| `prompts.json` | One original artist prompt + album prompt per release |
| `discography.json` | 10 releases, 65 tracks, Khmer lyrics, BPM/key/mood, style prompts |
| `avatars/*.png` | Placeholder thumbnails (replace with SLai output) |
| `scripts/creator-program/generate_sample_avatars.py` | SLai avatar generator |
| `scripts/creator-program/make_placeholder_avatars.py` | Local placeholder generator |
| `scripts/creator-program/build_sample_discography.py` | Rebuilds `discography.json` from the source data |

---

## 7. Seeding plan (deferred)

When Phase 1–2 are live, add a **separate, idempotent seed script** (not a migration):

1. Insert 8 `creator_profiles` rows with `status='active'`, `is_sample=true`.
2. Insert 10 `creator_releases` rows with `status='published'`.
3. Insert 65 `stream_tracks` rows + 10 `stream_albums` rows.
4. Attach placeholder or generated audio (`storage_key`) only in non-production.
5. Insert `creator_track_credits` for each track.
6. Mark all rows with a `sample` flag or a dedicated `sample_creator_pack` namespace so they can be removed in one command.
7. Do **not** run this seed in production.

**Removal:** one script that deletes everything tagged as sample, in dependency order, without touching real creators.

---

## 8. Acceptance criteria (for the deferred pack)

- [ ] 8 fictional creators with complete profiles and Khmer names.
- [ ] 10 releases, 65 tracks, all with `language=km` and Khmer lyrics where vocal.
- [ ] 3 pop albums × 10 tracks exist and validate against the release schema.
- [ ] Every release has its own prompt; no production prompt reused.
- [ ] 8 SLai-generated avatars, 1:1, no text/logos, fictional people.
- [ ] Sample rows are tagged and removable in one command.
- [ ] Demo pages show a “Sample creator” label.
- [ ] Native Khmer review of all public lyrics.

---

## 9. What is *not* included

- Real audio files (generation is a separate, credit-consuming step).
- Real social links or real people.
- Production seeding.
- English translations.
- Album covers (prompts are included; images are not generated yet).
