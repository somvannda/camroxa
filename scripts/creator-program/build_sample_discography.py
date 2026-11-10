#!/usr/bin/env python3
"""Build the Creator Program sample discography.

Reads ``prompts.json`` (one original prompt per artist and album) and writes
``discography.json``. All vocal samples are Khmer-first: ``language`` is ``km``
and every vocal track carries ``lyrics_km``. Instrumentals are explicitly marked.

Usage:
    python scripts/creator-program/build_sample_discography.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = REPO_ROOT / "docs" / "creator-program" / "sample-creators"
PROMPTS_FILE = SAMPLE_DIR / "prompts.json"
OUTPUT_FILE = SAMPLE_DIR / "discography.json"


def track(
    title: str,
    bpm: int,
    key: str,
    duration: int,
    mood: list[str],
    modifier: str,
    lyrics_km: str | None,
    title_km: str | None = None,
) -> dict:
    return {
        "title": title,
        "title_km": title_km,
        "bpm": bpm,
        "key": key,
        "duration_seconds": duration,
        "mood": mood,
        "modifier": modifier,
        "lyrics_km": lyrics_km.strip() if lyrics_km else None,
        "instrumental": lyrics_km is None,
    }


ALBUMS = [
    {
        "slug": "bassac-moon",
        "creator": "sokha",
        "title": "Bassac Moon",
        "release_type": "album",
        "release_date": "2026-11-20",
        "genre": "Khmer Pop",
        "genres": ["Khmer Pop", "Synth Pop"],
        "cover_prompt": "Square album cover, night-drive Khmer synth-pop, a full moon over the Bassac river, neon reflections on wet asphalt, teal and amber palette, grainy 35mm film, no text, no logos, 1:1",
        "tracks": [
            track("Bassac Moon", 104, "A minor", 208, ["night drive", "river", "longing"],
                  "glassy arpeggio, gated snare, close alto lead",
                  "ព្រះចន្ទឆ្លងទន្លេបាសាក់\nឈ្មោះអូននៅក្នុងពន្លឺ\nបងបើកឡានវិលផ្ទះយឺតៗ\nដើម្បីរក្សាអូននៅក្នុងភ្នែក",
                  "ព្រះចន្ទបាសាក់"),
            track("Slow Motion", 100, "F major", 196, ["slow dance", "neon"],
                  "warm pads, finger snaps, half-time drums",
                  "ក្រុងនេះលឿនពេកសម្រាប់យើង\nប៉ុន្តែយើងឈប់នៅពេលនេះ\nខិតជិតបន្តិច កុំប្រញាប់\nទុកពន្លឺស្វាយធ្វើការជំនួស",
                  "យឺតៗ"),
            track("Golden Hour", 108, "C major", 202, ["sunset", "hope"],
                  "bright plucks, airy pads, hand claps",
                  "ពន្លឺមាសលើផ្លូវវែង\nស្រមោលអូនជិតស្រមោលបង\nយើងរកឃើញមួយជ្រុងថ្ងៃ\nដែលគ្មានអ្នកណាយកទៅបាន",
                  "ម៉ោងមាស"),
            track("Phnom Penh Nights", 106, "G minor", 214, ["city", "friends"],
                  "motorik pulse, street ambience, chant hook",
                  "ម៉ូតូ និងក្លិនផ្កាម្លិះ\nមានវិនដូវរាប់ពាន់\nយើងញ៉ាំកាហ្វេទឹកកក ដើរក្នុងផ្លូវ\nហើយធ្វើដូចគ្មានកន្លែងត្រូវទៅ",
                  "រាត្រីភ្នំពេញ"),
            track("Missed Call", 96, "D minor", 188, ["longing", "distance"],
                  "sparse drums, muted guitar, voice memo texture",
                  "ឈ្មោះអូនភ្លឺលើអេក្រង់ម្តងទៀត\nបងទុកឱ្យវារោទ៍ រាប់ដប់\nសរសេរសារមួយ លុបពីរដង\nជាភាពក្លាហានដែលមិនដែលទៅដល់",
                  "ការហៅដែលខកខាន"),
            track("Riverside", 102, "E minor", 205, ["river", "memory"],
                  "gentle arpeggio, field recording, soft bass",
                  "ទូកឆ្លងកាត់ ទឹកហូរស្ងាត់\nបងរក្សាចង្វាក់អូនលើអណ្តាត\nកៅអីចាស់ ទិដ្ឋភាពចាស់\nមនុស្សផ្សេង កំពុងមើលឆ្លង",
                  "មាត់ទន្លេ"),
            track("Neon Lotus", 110, "A minor", 198, ["club", "escape"],
                  "pulsing bass, sidechained pads, whispered hook",
                  "យើងមិនមែនជាកម្មសិទ្ធិទីនេះ\nបន្ទប់ខ្ចី សំណើចលួច\nបាស់ខ្លាំង កម្រាលដីសើម\nបងមិនទាន់គិតដល់ផ្ទះ",
                  "ឈូកនេអុន"),
            track("3AM", 92, "B minor", 184, ["insomnia", "self"],
                  "lo-fi drums, detuned keys, tired vocal",
                  "កង្ហារលាន់ អេក្រង់ភ្លឺ\nបងរំកិលមើលជីវិតផ្សេង\nក្រុងស្ងាត់ ប៉ុន្តែទ្រូងបងខ្លាំង\nបងក្រោកឯងក្នុងហ្វូងមនុស្ស",
                  "ម៉ោងបីទៀត"),
            track("Stay Until Sunrise", 98, "F major", 212, ["romance", "morning"],
                  "warm bass, brushed drums, sunrise pads",
                  "ពិធីចប់ហើយ ភ្លើងស្លាប់\nអូននៅមាត់ទ្វារ មិនចង់ទៅ\nបងលេងសើចពីភ្លៀង\nអូនសើច ហើយនៅមួយថ្ងៃទៀត",
                  "នៅដល់ថ្ងៃរះ"),
            track("Home in Your Voice", 94, "C major", 206, ["distance", "comfort"],
                  "piano, soft strings, close harmony",
                  "បងទូរស័ព្ទពីបន្ទប់ឆ្ងាយ\nសញ្ញាខូច តែពាក្យឮ\nអូនហៅឈ្មោះបងដូចផ្លូវចាស់\nហើយបងមិនឆ្ងាយទៀតទេ",
                  "ផ្ទះក្នុងសំឡេងអូន"),
        ],
    },
    {
        "slug": "rainy-season",
        "creator": "sokha",
        "title": "Rainy Season",
        "release_type": "album",
        "release_date": "2026-12-04",
        "genre": "Khmer Pop",
        "genres": ["Khmer Pop", "Piano Ballad"],
        "cover_prompt": "Square album cover, monsoon rain on a Phnom Penh balcony, wet jasmine, a single warm lamp, muted blue-grey and amber, grainy film, no text, no logos, 1:1",
        "tracks": [
            track("First Rain", 88, "D minor", 216, ["rain", "release"],
                  "rain foley, Rhodes, brushed drums",
                  "ភ្លៀងដំបូងប៉ះដំបូលដែក\nអូនទុកស្បែកជើងនៅមាត់ជណ្តើរ\nបងរាប់ដំណក់លើកញ្ចក់\nហើយគិតថាបងគួររក្សាអ្វី",
                  "ភ្លៀងដំបូង"),
            track("Umbrella for Two", 84, "Bb major", 204, ["romance", "rain"],
                  "nylon guitar, soft kick, playful hook",
                  "ឆ័ត្រមួយ ជើងពីរ\nផ្លូវភ្លឺ តាក់ស៊ីយឺត\nអូនទាញបងជិតដៃអាវ\nហើយសើចថាយើងមិនដែលសម",
                  "ឆ័ត្រមួយសម្រាប់ពីរនាក់"),
            track("Thunder in My Chest", 92, "G minor", 198, ["storm", "anxiety"],
                  "low strings, heartbeat kick, distant thunder",
                  "មេឃបែកជាពីរនៅកណ្តាល\nភ្លើងដាច់ វិទ្យុនៅលាន់\nបងឮផ្គរលាន់ក្នុងទ្រូង\nជាសញ្ញាដែលបងមិនគោរព",
                  "ផ្គរលាន់ក្នុងទ្រូង"),
            track("Wet Streets", 86, "A minor", 190, ["memory", "city"],
                  "electric piano, tape hiss, slow bass",
                  "ផ្លូវសើមឆ្លុះអ្វីៗ\nស្លាក ភ្លើង ឡានទទេ\nបងដើរជ្រុងដែលអូនធ្លាប់ស្គាល់\nហើយឃើញមុខអូនក្នុងវិនដូវ",
                  "ផ្លូវសើម"),
            track("July Letter", 80, "F major", 220, ["letter", "regret"],
                  "solo piano, room noise, single vocal",
                  "បងសរសេរសារមួយក្នុងខែកក្កដា\nហើយមិនដែលដាក់ក្នុងប្រអប់សំបុត្រ\nក្រដាសរក្សាពាក្យដែលបងជ្រើស\nល្អជាងពាក្យដែលបងនិយាយ",
                  "សំបុត្រខែកក្កដា"),
            track("Cloudbreak", 90, "C major", 194, ["hope", "morning"],
                  "bright Rhodes, soft strings, opening filter",
                  "ភ្លៀងស្រាល មេឃស្តើង\nពន្លឺតិចៗចេញពីវាំង\nបងធ្វើកាហ្វេ ទុកទ្វារ\nសម្រាប់អ្វីដែលចង់មក",
                  "មេឃបើក"),
            track("Monsoon Heart", 82, "E minor", 208, ["storm", "love"],
                  "tremolo guitar, sub bass, layered harmonies",
                  "ចិត្តបងដូចខ្យល់មូសុង\nមកយឺត ខ្លាំង ហើយពិបាកឈប់\nបងជន់លិចបន្ទប់ដែលបងចង់ចាកចេញ\nហើយហៅវាថាស្នេហ៍",
                  "ចិត្តមូសុង"),
            track("Dry Season", 78, "D major", 186, ["drought", "acceptance"],
                  "dry acoustic guitar, sparse piano, warm sub",
                  "ទន្លេរួម ស្មៅក្រៀម\nកម្តៅធ្ងន់លើក្រុង\nបងរង់ចាំភ្លៀងដែលមិនមក\nហើយរៀនរស់ជាមួយអ្វីដែលបាត់",
                  "រដូវក្តៅ"),
            track("If You Come Back", 76, "A minor", 224, ["reunion", "longing"],
                  "piano, cello, close harmony",
                  "បើអូនវិលមកខែធ្នូ\nពេលល្ងាចប្រែជាមាស\nបងទុកភ្លើងក្នុងសាល\nហើយបំភ្លេចអ្វីដែលបងបាននិយាយ",
                  "បើអូនវិលមក"),
            track("After the Rain", 84, "C major", 202, ["healing", "morning"],
                  "soft piano, birds, wide reverb",
                  "ផ្លូវស្អាត ខ្យល់ថ្មី\nសត្វស្លាបចេញមកដូចធម្មតា\nបងបើកបង្អួចទាំងអស់\nហើយទុកឱ្យព្រឹករកបងឃើញ",
                  "ក្រោយភ្លៀង"),
        ],
    },
    {
        "slug": "golden-hour",
        "creator": "sokha",
        "title": "Golden Hour",
        "release_type": "album",
        "release_date": "2026-12-18",
        "genre": "Khmer Pop",
        "genres": ["Khmer Pop", "Dance Pop"],
        "cover_prompt": "Square album cover, golden-hour sunlight on the Mekong, friends on a rooftop, warm lens flare, saturated amber and teal, joyful, no text, no logos, 1:1",
        "tracks": [
            track("Golden Hour", 116, "C major", 196, ["summer", "joy"],
                  "plucked khim hook, hand claps, four-on-floor",
                  "ពន្លឺថ្ងៃលើទន្លេ មាសលើសក់អូន\nគ្មានអ្នកធ្វើការ គ្មានអ្នកបារម្ភ\nយើងរកចង្វាក់ក្នុងរសៀល\nក្រុងទាំងមូលច្រៀងបទតែមួយ",
                  "ម៉ោងមាស"),
            track("Sun on the Mekong", 112, "F major", 204, ["river", "summer"],
                  "bright plucks, group chant, shaker",
                  "ពន្លឺលើមេគង្គ ប្រាក់និងបៃតង\nទូកម៉ូតូលាន់ ខ្យល់ស្អាត\nយើងចែកស្វាយមួយ ចែកសំណើច\nថ្ងៃនេះជារូបថត",
                  "ពន្លឺលើមេគង្គ"),
            track("Dance with Me", 118, "G major", 192, ["dance", "confidence"],
                  "funk guitar, claps, talk-box ad-lib",
                  "អូននៅក្បែរឧបករណ៍បំពងសំឡេង\nបងមិនចេះរាំ តែបងយល់\nបើបងមិនផ្លាស់ឥឡូវ បងនឹងបាត់ឱកាស\nដូច្នេះបងលូកដៃ",
                  "រាំជាមួយបង"),
            track("Sugar Palm", 114, "A major", 188, ["sweet", "slow day"],
                  "ukulele, whistling, lazy bass",
                  "ដើមត្នោត និងម្លប់ឫស្សី\nថ្ងៃបែបនេះយើងមិនដែលបង្កើត\nយើងទិញភេសជ្ជៈ អង្គុយមើល\nទន្លេដឹកនាឡិកាទាំងអស់",
                  "ត្នោតផ្អែម"),
            track("City Lights", 110, "E minor", 200, ["night", "freedom"],
                  "synth bass, rooftop pads, crowd noise",
                  "ក្រុងបើកភ្លើងម្តងមួយៗ\nមួយរយភ្លើង មួយរយរឿង\nយើងនៅលើដំបូល ក្រៅភ្នែកមនុស្ស\nក្រុងទាំងមូលជារបស់យើងយប់នេះ",
                  "ភ្លើងក្រុង"),
            track("Borrowed Time", 108, "D major", 206, ["urgency", "romance"],
                  "driving bass, gated pads, urgent vocal",
                  "យើងរត់លើនាឡិកាខ្ចី\nព្រោះបងមិនចង់ឱ្យវាឈប់\nបងយកយប់នេះ យកការដួល\nយកអ្វីៗដែលមកជាមួយអូន",
                  "ពេលវេលាខ្ចី"),
            track("Young Forever", 116, "C major", 194, ["youth", "anthem"],
                  "stadium drums, gang vocal, bright synth",
                  "យើងមិនដឹងថ្ងៃស្អែកមានន័យអ្វី\nយើងដឹងតែពេលរវាង\nខ្លាំងបន្តិច សេរីបន្តិច\nដូចយើងធ្លាប់ជា",
                  "ក្មេងរហូត"),
            track("One More Song", 112, "G major", 198, ["last call", "friends"],
                  "disco strings, claps, fading crowd",
                  "ឌីជេប្រមូលឧបករណ៍\nភ្លើងស្រអាប់ អ្នកច្រៀងនៅច្រៀង\nបងទាញដៃអូន អូនទាញបងមកវិញ\nកម្រាលទទេ បងមិនខ្វល់",
                  "បទមួយទៀត"),
            track("Goodnight, Phnom Penh", 104, "F major", 214, ["goodnight", "city"],
                  "soft synth, distant traffic, warm choir",
                  "រាត្រីសួស្តី ភ្នំពេញ\nទន្លេពេញដោយពន្លឺ\nរាត្រីសួស្តី ភ្នំពេញ\nយើងឆ្លងកាត់យប់នេះបាន",
                  "រាត្រីសួស្តី ភ្នំពេញ"),
            track("Tomorrow", 118, "C major", 190, ["hope", "future"],
                  "rising synth, group vocal, big finish",
                  "ថ្ងៃស្អែក ថ្ងៃស្អែក\nពាក្យនេះដូចទ្វារ\nថ្ងៃស្អែក ថ្ងៃស្អែក\nបងមិនដឹងវាសម្រាប់អ្វី\nបើអូននៅក្បែរបង\nជាមួយព្រឹកក្នុងភ្នែកអូន\nថ្ងៃស្អែក ថ្ងៃស្អែក\nទៅមើលវាជាមួយគ្នា",
                  "ថ្ងៃស្អែក"),
        ],
    },
    # --- EPs for the other seven creators ---
    {
        "slug": "street-temple", "creator": "vannak", "title": "Street Temple",
        "release_type": "ep", "release_date": "2027-01-08", "genre": "Khmer Hip Hop",
        "genres": ["Khmer Hip Hop", "Boom Bap"],
        "cover_prompt": "Square EP cover, a small temple gate between concrete shophouses at dusk, warm sodium light, film grain, no text, no logos, 1:1",
        "tracks": [
            track("Street Temple", 90, "E minor", 218, ["street", "faith"], "dusty drums, temple bell, upright bass",
                  "កណ្តឹងវត្តលើថ្មបេតុង\nបងរៀនអធិដ្ឋានដោយដៃក្នុងហោប៉ៅ\nក្រុងមិនដែលសួរឈ្មោះបង\nតែវាចាំកន្លែងដែលបងចាប់ផ្តើម"),
            track("Tuk-Tuk Anthem", 92, "E minor", 205, ["night", "friends"], "hand percussion, rubbery bass, chant hook",
                  "កង់បី មិត្តពីរ យប់មួយ\nអ្នកបើកដឹងផ្លូវដោយចិត្ត\nយើងរាប់ភ្លើង ឆ្លងកំផែង\nក្រុងទាំងមូលជាកាតប៉ុស្តិ៍"),
            track("Concrete Prayer", 88, "D minor", 226, ["work", "hope"], "dark piano loop, heavy kick, vinyl crackle",
                  "អគារឡើង លុយចុះ\nដៃឪពុកនៅតែរឹង\nបងអធិដ្ឋានលើថ្មបេតុង\nសង្ឃឹមថាផ្ទះនឹងចាំបង"),
            track("Old Market Cypher", 94, "G minor", 232, ["market", "community"], "breakbeat, brass stab, crowd noise",
                  "ផ្សារចាស់ ក្លិនគ្រឿងទេស\nបងច្រៀងលើចង្វាក់ធុង\nអ្នកលក់សើច ក្មេងៗមើល\nក្រុងនេះជាឆាករបស់យើង"),
            track("Brothers on the Bridge", 90, "A minor", 214, ["friendship", "resolve"], "warm bass, brushed drums, group vocal",
                  "ស្ពានវែង ខ្យល់យប់\nបងនិងមិត្តឈរមើលទឹក\nយើងសន្យាថានឹងមិនបោះបង់\nទោះក្រុងនេះពិបាកប៉ុណ្ណា"),
        ],
    },
    {
        "slug": "river-lights", "creator": "dara", "title": "River Lights",
        "release_type": "ep", "release_date": "2027-01-15", "genre": "R&B",
        "genres": ["R&B", "Neo-Soul"],
        "cover_prompt": "Square EP cover, R&B singer by a rain-streaked window at midnight, purple and blue reflections, soft focus, film grain, no text, no logos, 1:1",
        "tracks": [
            track("River Lights", 76, "D minor", 224, ["midnight", "intimacy"], "Rhodes, brushed snare, warm bass",
                  "ភ្លើងលើទន្លេញញឹមយឺតៗ\nបងចាំអូននៅជ្រុងចាស់\nទឹកហូរយកថ្ងៃទៅ\nតែបងនៅតែដដែល"),
            track("Slow Burn", 80, "Bb major", 212, ["slow burn", "desire"], "fretless bass, finger snaps, falsetto",
                  "ភ្លើងតូចមួយក្នុងទ្រូង\nឆេះយឺតៗ មិនចេញផ្សែង\nបងមិនចង់ឱ្យវាដាច់\nទោះវាឈឺប៉ុណ្ណា"),
            track("Midnight Call", 74, "F minor", 208, ["call", "longing"], "telephone EQ, sub bass, close vocal",
                  "ម៉ោងដប់ពីរយប់ ទូរស័ព្ទលាន់\nបងដឹងថាជាអូន\nពាក្យដំបូងគឺស្ងាត់\nប៉ុន្តែបងឮអ្វីៗទាំងអស់"),
            track("Curfew", 78, "E minor", 220, ["isolation", "city"], "muted keys, slow clap, room tone",
                  "ក្រុងបិទទ្វារ ភ្លើងស្រអាប់\nបងនៅក្នុងបន្ទប់តូច\nគិតដល់អូននៅជ្រុងម្ខាង\nហើយរង់ចាំព្រឹក"),
            track("Stay Close", 72, "C major", 216, ["comfort", "closeness"], "soft Rhodes, heartbeat kick, harmony",
                  "កុំទៅឆ្ងាយពេក\nពេលយប់វែងដូចនេះ\nបងគ្រាន់តែចង់ឮដង្ហើមអូន\nនៅក្បែរបងបន្តិចទៀត"),
        ],
    },
    {
        "slug": "letters-home", "creator": "kanya", "title": "Letters Home",
        "release_type": "ep", "release_date": "2027-01-22", "genre": "Khmer Ballad",
        "genres": ["Khmer Ballad", "Piano Ballad"],
        "cover_prompt": "Square EP cover, handwritten letters on a wooden table, soft window light, a bus ticket, warm beige and brown, no text, no logos, 1:1",
        "tracks": [
            track("Letters Home", 68, "C major", 238, ["home", "distance"], "solo piano, soft strings",
                  "បងសរសេរសំបុត្រទៅផ្ទះ\nរៀបរាប់ពីក្រុងដែលបងរស់\nម្តាយឆ្លើយត្រឹមពាក្យថា\n\"កុំបារម្ភ រក្សាខ្លួនឯង\""),
            track("Battambang Rain", 64, "A minor", 226, ["rain", "memory"], "rain foley, nylon guitar, cello",
                  "ភ្លៀងបាត់ដំបងធ្លាក់យឺតៗ\nក្លិនដីដើរតាមខ្យល់\nបងឈរនៅមាត់ទ្វារ\nចាំថ្ងៃដែលបងត្រូវវិល"),
            track("The Long Bus", 66, "F major", 244, ["journey", "distance"], "piano, bus rhythm, warm bass",
                  "ឡានក្រុងវែង ផ្លូវកោង\nបងដេកមិនលក់ មើលពន្លឺ\nរាល់គីឡូម៉ែត្រ បងខិតជិតផ្ទះ\nហើយឆ្ងាយពីអ្នកដែលបងស្រលាញ់"),
            track("Mother's Voice", 62, "D major", 232, ["mother", "memory"], "solo piano, single vocal, room noise",
                  "សំឡេងម្តាយតាមខ្ញុំទៅគ្រប់ទីកន្លែង\nនៅក្នុងពាក្យដែលខ្ញុំនិយាយ\nនៅក្នុងដៃដែលខ្ញុំប្រើ\nគាត់មិនដែលចេញពីខ្ញុំទេ"),
            track("Where the Rice Grows", 70, "G major", 240, ["roots", "acceptance"], "piano, strings, soft choir",
                  "កន្លែងដែលស្រូវដុះ\nគឺជាកន្លែងដែលបងចាប់ផ្តើម\nទោះបងដើរឆ្ងាយប៉ុណ្ណា\nឫសនៅតែនៅទីនោះ"),
        ],
    },
    {
        "slug": "neon-bay", "creator": "rithy", "title": "Neon Bay",
        "release_type": "ep", "release_date": "2027-02-05", "genre": "EDM",
        "genres": ["EDM", "Big Room"],
        "cover_prompt": "Square EP cover, neon-lit bay at night, festival lights reflecting on water, cyan and lime, high contrast, no text, no logos, 1:1",
        "tracks": [
            track("Neon Bay", 128, "F minor", 210, ["festival", "energy"], "saw lead, four-on-floor, sidechained bass",
                  "ពន្លឺនេអុនលើឆ្នេរសមុទ្រ\nបងរត់តាមចង្វាក់របស់អូន"),
            track("Angkor Drop", 130, "F minor", 198, ["drop", "heritage"], "pentatonic lead, temple bell, big drop",
                  "ប្រាសាទចាស់ ចង្វាក់ថ្មី\nបងលើកដៃ ហើយទម្លាក់"),
            track("Night Ferry", 126, "G minor", 204, ["night", "travel"], "rolling bass, ferry horn, arpeggio",
                  "ទូកយប់ឆ្លងទៅ\nភ្លើងក្រុងនៅខាងក្រោយ"),
            track("Festival Lights", 132, "A minor", 216, ["festival", "crowd"], "stadium synth, crowd chant, hard kick",
                  "ភ្លើងពីលើឆាក\nមនុស្សរាប់ពាន់ច្រៀងជាមួយគ្នា"),
            track("After the Last Song", 124, "E minor", 222, ["afterglow", "friends"], "soft pad, piano, distant crowd",
                  "បន្ទាប់ពីបទចម្រៀងចុងក្រោយ\nនៅសល់តែយើងពីរនាក់"),
        ],
    },
    {
        "slug": "golden-fibers", "creator": "chenda", "title": "Golden Fibers",
        "release_type": "ep", "release_date": "2027-02-12", "genre": "Traditional Fusion",
        "genres": ["Traditional Fusion", "Khmer Folk"],
        "cover_prompt": "Square EP cover, close-up of golden silk weaving, temple stone texture, warm amber light, shallow depth, no text, no logos, 1:1",
        "tracks": [
            track("Golden Fibers", 84, "modal", 226, ["weaving", "memory"], "tro, khim, hand percussion, electronic pulse",
                  "សរសៃមាសលើក្រណាត់ចាស់\nដៃយាយបង្រៀនបងត្បាញ\nរាល់ខ្សែស្រឡាយជាការចងចាំ\nរាល់ថ្ងៃជាការអធិដ្ឋាន"),
            track("Khim at Dusk", 78, "modal", 214, ["dusk", "calm"], "solo khim, room noise, soft drone",
                  "សំឡេងឃឹមនៅពេលល្ងាច\nដូចទឹកធ្លាក់លើថ្ម\nបងលេងយឺតៗ\nដើម្បីទុកឱ្យថ្ងៃចេញទៅ"),
            track("Memory Temple", 88, "modal", 232, ["temple", "ancestors"], "tro, low drone, stone reverb",
                  "ថ្មប្រាសាទនៅស្ងាត់\nដានជើងចាស់នៅលើជណ្តើរ\nបងដើរតាមស្រមោលអតីតកាល\nហើយឮសំឡេងអ្នកដែលចេញទៅ"),
            track("Weaving Song", 92, "modal", 220, ["work", "rhythm"], "khim, clappers, bass pulse",
                  "ខ្សែស្រឡាយទៅមក\nដៃចេះចាំដោយខ្លួនឯង\nបទចម្រៀងនៅក្នុងចង្វាក់\nជីវិតនៅក្នុងក្រណាត់"),
            track("Offerings", 80, "modal", 228, ["ritual", "peace"], "tro, bells, soft choir",
                  "ផ្កា ធូប និងទឹក\nបងដាក់នៅមុខបដិមា\nសុំឱ្យអ្នកដែលចេញទៅ\nដើរលើផ្លូវដែលមានពន្លឺ"),
        ],
    },
    {
        "slug": "rainy-kampot", "creator": "pisey", "title": "Rainy Kampot",
        "release_type": "ep", "release_date": "2027-02-19", "genre": "Lo-fi",
        "genres": ["Lo-fi", "Chillhop"],
        "cover_prompt": "Square EP cover, rainy Kampot street from a window, green shutters, ceiling fan, muted blue-grey, no text, no logos, 1:1",
        "tracks": [
            track("Rainy Kampot", 72, "F major", 184, ["rain", "study"], "cassette wow, rain, Rhodes", None),
            track("Ceiling Fan", 76, "D minor", 176, ["slow", "sleep"], "fan hum, soft kick, muted guitar", None),
            track("Slow Afternoon", 70, "C major", 192, ["afternoon", "calm"], "warm keys, vinyl noise", None),
            track("Green Shutters", 74, "A minor", 180, ["window", "quiet"], "rain, distant motorbike, soft bass", None),
            track("Last Bus Home", 68, "G major", 188, ["night", "home"], "tape hiss, Rhodes, brushed snare", None),
        ],
    },
    {
        "slug": "concrete-khmer", "creator": "sovan", "title": "Concrete Khmer",
        "release_type": "ep", "release_date": "2027-02-26", "genre": "Khmer Rap",
        "genres": ["Khmer Rap", "Conscious Rap"],
        "cover_prompt": "Square EP cover, black-and-white concrete alley at dusk with a single red accent, rain, no text, no logos, 1:1",
        "tracks": [
            track("Concrete Khmer", 90, "G minor", 230, ["work", "identity"], "sparse drums, dark piano loop",
                  "ថ្មបេតុងក្រោមជើងបង\nផ្សែងឡានលាយជាមួយញើស\nបងធំឡើងក្នុងក្រុងនេះ\nហើយក្រុងនេះមិនដែលចាំឈ្មោះបង"),
            track("Overtime", 92, "D minor", 218, ["work", "exhaustion"], "ticking hi-hat, sub bass, dry vocal",
                  "ម៉ោងបន្ថែម ថ្ងៃបន្ថែម\nប្រាក់ខែមិនគ្រប់ខែ\nបងរាប់ថ្ងៃដែលបាត់\nហើយសង្ឃឹមថាថ្ងៃស្អែកខ្លីជាងនេះ"),
            track("The Cost of Leaving", 86, "E minor", 240, ["migration", "family"], "minor piano, slow drums, cello",
                  "ចេញទៅមានតម្លៃ\nបងដឹងពេលបងបោះជើង\nផ្ទះនៅខាងក្រោយ\nហើយផ្លូវនៅខាងមុខវែងណាស់"),
            track("Rent Due", 94, "A minor", 212, ["pressure", "survival"], "knocking rhythm, bass, sparse keys",
                  "ថ្ងៃទីមួយ ប្រាក់ជួល\nម្ចាស់ផ្ទះគោះទ្វារ\nបងញញឹម ហើយនិយាយថា\n\"ខ្ញុំនៅតែធ្វើការ\""),
            track("My Father's Hands", 82, "C minor", 236, ["father", "resolve"], "solo piano, low strings, close vocal",
                  "ដៃឪពុកបងរឹងដូចថ្ម\nមានស្លាកស្នាមពីជីវិត\nបងមើលដៃខ្លួនឯង\nហើយយល់ថាបងមិនទាន់ធ្វើបានគ្រប់គ្រាន់"),
        ],
    },
]


def build() -> dict:
    prompts = json.loads(PROMPTS_FILE.read_text(encoding="utf-8"))["creators"]
    albums = []

    for album in ALBUMS:
        creator = album["creator"]
        prompt_set = prompts[creator]["albums"][album["slug"]]
        album_id = f"{creator}-{album['slug']}"
        prompt_id = f"{creator}.{album['slug']}"
        tracks = []

        for index, item in enumerate(album["tracks"], start=1):
            tracks.append(
                {
                    "id": f"{album_id}-{index:02d}",
                    "track_number": index,
                    "title": item["title"],
                    "title_km": item["title_km"],
                    "duration_seconds": item["duration_seconds"],
                    "bpm": item["bpm"],
                    "key": item["key"],
                    "mood": item["mood"],
                    "instrumental": item["instrumental"],
                    "explicit": False,
                    "language": "km",
                    "origin": "ai_generated" if creator == "rithy" else ("original" if creator in {"kanya", "chenda", "sovan"} else "ai_assisted"),
                    "prompt_id": prompt_id,
                    "style_prompt": f"{prompt_set['prompt']}, {item['modifier']}",
                    "lyrics_km": item["lyrics_km"],
                }
            )

        albums.append(
            {
                "id": album_id,
                "creator_handle": creator,
                "title": album["title"],
                "release_type": album["release_type"],
                "release_date": album["release_date"],
                "genre": album["genre"],
                "genres": album["genres"],
                "language": "km",
                "explicit": False,
                "origin": "ai_generated" if creator == "rithy" else ("original" if creator in {"kanya", "chenda", "sovan"} else "ai_assisted"),
                "prompt_id": prompt_id,
                "prompt": prompt_set["prompt"],
                "cover_prompt": album["cover_prompt"],
                "track_count": len(tracks),
                "tracks": tracks,
            }
        )

    return {
        "version": 1,
        "note": "Fictional sample catalog. Khmer-first vocals (language=km). Every artist and album has an original prompt in prompts.json; no production prompt was reused.",
        "albums": albums,
    }


def main() -> int:
    payload = build()
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tracks = sum(album["track_count"] for album in payload["albums"])
    print(f"wrote {OUTPUT_FILE.relative_to(REPO_ROOT)}: {len(payload['albums'])} releases, {tracks} tracks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
