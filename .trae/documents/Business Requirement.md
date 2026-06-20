🎧 AI Music Generator Desktop App

Business Requirements Document (BRD)

1. 📌 Overview
1.1 Purpose

Build a desktop application (Electron-based) that automates the end-to-end workflow of:

Song generation (title, lyrics, album)
Image generation (background + YouTube thumbnail)
Song production via SUNO (automated with Playwright)
Final audio merging

The goal is to reduce manual effort and create a fully automated AI music production pipeline.

1.2 Tech Stack
Layer	Technology
Desktop App	Electron
UI	shadcn/ui + Tailwind
Icons	Lucide
Backend	Node.js (Electron main process)
DB	PostgreSQL
AI (Text Gen)	DeepSeek
AI (Polish + Image)	OpenAI
Automation	Playwright
Audio Processing	FFmpeg
2. 🎯 Core Features
2.1 SONG GENERATION FLOW (Core Engine)
Description

Generate:

Song Title
Lyrics
Album Name
Background Image
YouTube Thumbnail
Functional Requirements
2.1.1 Input Controls
Language
Creativity level
Song count
Prompt template
Text style
Car model selection (optional or random)
Image style selection
Structure template
Description template
2.1.2 AI Generation Flow

Step 1: Generate Song Content

Use DeepSeek
Output:
Title
Lyrics
Album Name

Step 2: Polish Lyrics

Use OpenAI
Improve:
Grammar
Flow
Structure

Step 3: Background Image Generation

Use:
Stored car models (DB/directory)
Stored image samples
System randomly selects:
1 car model
1 image style reference
Sends prompt to OpenAI Image API:
Combine:
Car
Neon/night aesthetic
Reference style

Step 4: Thumbnail Generation (16:9)

Input:
Generated background image
Text style template (DB)
Output:
YouTube-ready thumbnail
Output Per Song
Title
Lyrics (raw + polished)
Album name
Background image
Thumbnail image
Batch Output
Generate N songs per request
2.2 SUNO AUTOMATION FLOW
Trigger

Button: "Automation"

Functional Steps
2.2.1 Workspace Setup
Open SUNO via Playwright
Create workspace:
Format: YYYY-MM-DD
2.2.2 Song Upload Loop

For each generated song:

Input:
Title
Lyrics
Style
Generate song via SUNO
2.2.3 Output Handling
SUNO generates 2 versions
System:
Rename first → {title}_OK
Download both versions
Output
Local audio files (.mp3/.wav)
2.3 MERGE SONG FLOW
Description

Merge generated songs using FFmpeg

Functional Requirements
User-configurable:
Songs per merged file (e.g., 7)
Example:
10 songs → 2 files:
File 1: 7 songs
File 2: 3 songs
Output
Final merged audio files
2.4 MANAGEMENT MODULES (UI Tabs)

Based on your screenshots:

2.4.1 Image Samples
Upload images
Tag images

Store in:

/data/image_samples
2.4.2 Car Models
Store:
Make
Model
Trim
Year
Category
2.4.3 Prompt Templates
Store reusable prompts
Tag system:
e.g. car_seeded
2.4.4 Text Styles
Title format
Subtitle format
Position
Opacity
2.4.5 Song Structure Templates

Example:

[Intro]
[Build]
[Drop]
[Break]
[Outro]
2.4.6 Song Description Templates

Used for AI prompting

2.5 SETTINGS MODULE
Required Settings
AI Settings
DeepSeek API key
OpenAI API key
Generation Settings
Default creativity
Default count
Language
Image Settings
Output directory
Resolution
Style strength
SUNO Automation
Login session storage
Timeout settings
Retry logic
FFmpeg Settings
Path to FFmpeg binary
Merge size default
Database Settings
Host: localhost
User: postgres
Password: postgres
Database: MG
3. 🗄️ DATABASE DESIGN (PostgreSQL)
3.1 songs
id SERIAL PRIMARY KEY
title TEXT
lyrics_raw TEXT
lyrics_polished TEXT
album TEXT
status TEXT
created_at TIMESTAMP
3.2 images
id SERIAL PRIMARY KEY
song_id INT
type TEXT -- background | thumbnail
path TEXT
created_at TIMESTAMP
3.3 car_models
id SERIAL PRIMARY KEY
make TEXT
model TEXT
trim TEXT
year INT
category TEXT
3.4 image_samples
id SERIAL PRIMARY KEY
file_path TEXT
tags TEXT[]
created_at TIMESTAMP
3.5 prompt_templates
id SERIAL PRIMARY KEY
name TEXT
content TEXT
tags TEXT[]
created_at TIMESTAMP
3.6 text_styles
id SERIAL PRIMARY KEY
name TEXT
title TEXT
subtitle TEXT
opacity FLOAT
position TEXT
3.7 song_structures
id SERIAL PRIMARY KEY
name TEXT
content TEXT
updated_at TIMESTAMP
3.8 song_descriptions
id SERIAL PRIMARY KEY
name TEXT
content TEXT
updated_at TIMESTAMP
3.9 automation_logs
id SERIAL PRIMARY KEY
song_id INT
status TEXT
message TEXT
created_at TIMESTAMP
4. 🔄 SYSTEM ARCHITECTURE
Layers
UI (Renderer)
React + shadcn
Electron Main
Handles:
FS access
Playwright
FFmpeg
Services
AI Service
Image Service
Automation Service
Merge Service
5. 🚀 WORKFLOW SUMMARY
Full Pipeline
Generate Songs (DeepSeek)
Polish Lyrics (OpenAI)
Generate Images (OpenAI)
Save to DB
Run SUNO Automation
Download Songs
Merge with FFmpeg
6. ⚠️ RISKS & CONSIDERATIONS
SUNO UI changes → breaks automation
API rate limits
Image consistency issues
File storage growth
7. 💡 RECOMMENDATIONS (IMPORTANT)
1. Queue System (VERY IMPORTANT)

Use a job queue:

Prevent UI freezing
Track progress
2. Retry System
Failed AI calls
Failed automation steps
3. Versioning
Store multiple versions of lyrics/images
4. Preview System
Preview image before saving
Preview lyrics before automation
5. Modular AI Prompts
Make prompts editable → huge flexibility
6. Logging Dashboard
Show:
Success
Failures
Progress
7. Export Feature
Export:
CSV
JSON
Final songs
8. 📦 FUTURE FEATURES (Optional)
YouTube auto upload
Spotify pipeline
Voice cloning
Beat generation integration
👉 Next Step

If you want, I can break this into:

Phase 2 Docs:
✅ Technical Architecture (code-level)
✅ API Design
✅ Folder Structure
✅ Electron + React boilerplate
✅ Playwright automation script
✅ FFmpeg merge script

Just tell me: “continue with technical spec” 👍

1. yes we download both version, but when we merged, we should know right? we only merge {title}_OK together, and the other version without _OK are merged accordingly, so we don't have mixed merged. 



Good catch — this is actually important to define clearly now, otherwise your pipeline will get messy later.

Let’s formalize it properly and update your requirements 👇

🔁 Updated Requirement: Dual-Version Merge Logic
🎯 Goal

Ensure SUNO’s 2 generated versions per song are never mixed during merging.

You will produce:

✅ One merged file for _OK versions
✅ One merged file for non-OK versions
🧠 Naming Convention (Critical)

After SUNO generation:

Version	Naming Rule
Preferred version	{title}_OK
Alternate version	{title}_ALT (recommended — instead of leaving unnamed)

👉 I strongly recommend renaming BOTH versions for clarity:

Avoid ambiguity later
Easier filtering & debugging
🔀 Merge Logic
Input Example (10 songs)

You will have:

10 files → _OK
10 files → _ALT
Merge Output

If merge size = 7:

✅ OK Version Output
merged_OK_1.mp3 → 7 songs
merged_OK_2.mp3 → 3 songs
✅ ALT Version Output
merged_ALT_1.mp3 → 7 songs
merged_ALT_2.mp3 → 3 songs
⚙️ Functional Requirements Update
1. File Classification

System must:

Scan downloaded folder
Detect:
_OK
_ALT (or non-OK fallback)
2. Separate Pipelines

System must create two independent queues:

Queue A → OK songs
Queue B → ALT songs
3. Merge Execution

Each queue is processed independently:

for each queue:
    chunk songs based on user setting
    merge using ffmpeg
    export file with correct suffix
🗄️ Database Update (IMPORTANT)

Add fields to track versions properly:

Update: songs table
ALTER TABLE songs ADD COLUMN batch_id TEXT;
New Table: song_versions
CREATE TABLE song_versions (
  id SERIAL PRIMARY KEY,
  song_id INT,
  version_type TEXT, -- OK | ALT
  file_path TEXT,
  duration FLOAT,
  created_at TIMESTAMP
);
🧩 Merge Tracking Table (Optional but SMART)
CREATE TABLE merged_outputs (
  id SERIAL PRIMARY KEY,
  version_type TEXT, -- OK | ALT
  file_path TEXT,
  song_count INT,
  created_at TIMESTAMP
);
⚙️ FFmpeg Strategy
Example Command
ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp3
Generate list.txt dynamically:
file 'song1_OK.mp3'
file 'song2_OK.mp3'
file 'song3_OK.mp3'
⚠️ Edge Cases (Don’t Skip These)
1. Missing Version
If _OK exists but _ALT missing:
Skip OR log warning
2. Uneven Counts
OK = 10, ALT = 8
Still process independently
3. Corrupted File
Skip and log
Do NOT break entire batch
💡 UX Recommendation

Add UI indicator:

Batch #12
✔ OK: 10 songs
✔ ALT: 10 songs
⚠ Missing: 0
🔥 Strong Recommendation (Important Upgrade)

Instead of relying only on filenames:

👉 Store metadata in DB

Example:

song_id	version	path
1	OK	file1.mp3
1	ALT	file2.mp3

This prevents:

Bugs from renaming
File mismatch issues
✅ Final Summary

Your merge system should:

Separate _OK and _ALT
Never mix versions
Produce parallel merged outputs
Track everything in DB
Handle missing/corrupt files safely

If you want next, I can build:

✅ FFmpeg merge service (Node.js code)
✅ Playwright SUNO automation script (with renaming logic)
✅ File watcher + auto-import system

Just say: “build merge service” 🚀

continue with technical spec

Great — now we’ll move from business requirements into a practical technical specification you (or an AI builder) can directly implement.

I’ll structure this as a Phase 2 Technical Spec focused on:

Architecture
Project structure
Core services (with pseudo + real code patterns)
Playwright automation design
FFmpeg merge service
Job queue system (very important)
🧠 1. SYSTEM ARCHITECTURE
High-Level Design
Electron App
├── Renderer (React + shadcn UI)
├── Main Process (Node.js)
│   ├── IPC Handlers
│   ├── Services Layer
│   ├── Job Queue
│   ├── File System Access
│   ├── Playwright Automation
│   ├── FFmpeg Execution
│
└── PostgreSQL Database
Key Principle

👉 ALL heavy work runs in Main process (or workers)
👉 Renderer = UI only

📁 2. PROJECT STRUCTURE
app/
├── main/
│   ├── index.ts
│   ├── ipc/
│   │   ├── song.ipc.ts
│   │   ├── automation.ipc.ts
│   │   ├── merge.ipc.ts
│   │
│   ├── services/
│   │   ├── ai/
│   │   │   ├── deepseek.service.ts
│   │   │   ├── openai.service.ts
│   │   │
│   │   ├── song/
│   │   │   ├── song-generator.service.ts
│   │   │   ├── lyric-polish.service.ts
│   │   │
│   │   ├── image/
│   │   │   ├── image-generator.service.ts
│   │   │   ├── thumbnail.service.ts
│   │   │
│   │   ├── automation/
│   │   │   ├── suno.service.ts
│   │   │   ├── playwright.service.ts
│   │   │
│   │   ├── merge/
│   │   │   ├── ffmpeg.service.ts
│   │   │
│   │   ├── queue/
│   │   │   ├── job-queue.ts
│   │   │   ├── worker.ts
│   │
│   │   ├── db/
│   │   │   ├── db.ts
│   │   │   ├── repositories/
│   │
│   │   ├── utils/
│   │   │   ├── logger.ts
│   │   │   ├── file.ts
│
├── renderer/
│   ├── components/
│   ├── pages/
│   ├── store/
│
├── data/
│   ├── image_samples/
│   ├── outputs/
│   ├── downloads/
⚙️ 3. CORE SERVICES
3.1 SONG GENERATOR SERVICE
// song-generator.service.ts
export async function generateSong(input) {
  const { prompt, structure } = input;

  const result = await deepseek.generate({
    prompt,
    structure
  });

  return {
    title: result.title,
    lyrics: result.lyrics,
    album: result.album
  };
}
3.2 LYRIC POLISH SERVICE
// lyric-polish.service.ts
export async function polishLyrics(lyrics: string) {
  return await openai.chat({
    system: "Improve lyrics flow, grammar, and musicality",
    user: lyrics
  });
}
3.3 IMAGE GENERATION SERVICE
Key Logic:
Random car model
Random image sample
Combine prompt
export async function generateBackgroundImage() {
  const car = await carRepo.getRandom();
  const sample = await imageRepo.getRandom();

  const prompt = `
  A neon night car scene, ${car.make} ${car.model},
  inspired by ${sample.tags}, cinematic lighting
  `;

  return await openai.image(prompt);
}
3.4 THUMBNAIL SERVICE
export async function generateThumbnail(bgImage, textStyle, title) {
  return await openai.image(`
    Create YouTube thumbnail 16:9
    Use this background: ${bgImage}
    Title: ${title}
    Style: ${textStyle}
  `);
}
🤖 4. PLAYWRIGHT AUTOMATION (SUNO)
4.1 Core Service
import { chromium } from 'playwright';

export async function runSunoAutomation(batchId) {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();

  await page.goto("https://suno.com");

  await createWorkspace(page, batchId);

  const songs = await songRepo.getByBatch(batchId);

  for (const song of songs) {
    await generateSong(page, song);
    await handleVersions(page, song);
  }

  await browser.close();
}
4.2 Create Workspace
async function createWorkspace(page, batchId) {
  await page.click("button:has-text('New Workspace')");
  await page.fill("input", `Batch-${batchId}`);
  await page.click("button:has-text('Create')");
}
4.3 Generate Song
async function generateSong(page, song) {
  await page.fill("textarea[name='lyrics']", song.lyrics_polished);
  await page.fill("input[name='title']", song.title);

  await page.click("button:has-text('Generate')");
  await page.waitForTimeout(30000);
}
4.4 Handle Versions (CRITICAL)
async function handleVersions(page, song) {
  const versions = await page.$$(".song-item");

  // Rename first
  await versions[0].click();
  await page.fill(".title-input", `${song.title}_OK`);

  // Rename second
  await versions[1].click();
  await page.fill(".title-input", `${song.title}_ALT`);

  // Download both
  for (const v of versions) {
    await v.click();
    await page.click("button:has-text('Download')");
  }
}
🔁 5. MERGE SERVICE (FFmpeg)
5.1 Core Logic
export async function mergeSongs(versionType: "OK" | "ALT", chunkSize: number) {
  const files = await songVersionRepo.getByType(versionType);

  const chunks = chunkArray(files, chunkSize);

  for (let i = 0; i < chunks.length; i++) {
    const listFile = createListFile(chunks[i]);

    await runFFmpeg(listFile, `merged_${versionType}_${i}.mp3`);
  }
}
5.2 Create list.txt
function createListFile(files) {
  const content = files.map(f => `file '${f.path}'`).join("\n");

  const filePath = `/tmp/list_${Date.now()}.txt`;
  fs.writeFileSync(filePath, content);

  return filePath;
}
5.3 Run FFmpeg
import { exec } from "child_process";

function runFFmpeg(listFile, output) {
  return new Promise((resolve, reject) => {
    exec(
      `ffmpeg -f concat -safe 0 -i ${listFile} -c copy ${output}`,
      (err) => {
        if (err) reject(err);
        else resolve(true);
      }
    );
  });
}
🔄 6. JOB QUEUE SYSTEM (VERY IMPORTANT)
Why?
Prevent UI freeze
Handle long AI + automation tasks
Retry failed jobs
6.1 Simple Queue Design
type Job = {
  id: string;
  type: "generate" | "automation" | "merge";
  payload: any;
};
6.2 Queue Implementation
class JobQueue {
  private queue: Job[] = [];
  private running = false;

  add(job: Job) {
    this.queue.push(job);
    this.run();
  }

  async run() {
    if (this.running) return;
    this.running = true;

    while (this.queue.length) {
      const job = this.queue.shift();

      try {
        await this.process(job);
      } catch (e) {
        console.error("Job failed", e);
      }
    }

    this.running = false;
  }

  async process(job: Job) {
    switch (job.type) {
      case "generate":
        return generateSongs(job.payload);
      case "automation":
        return runSunoAutomation(job.payload);
      case "merge":
        return mergeSongs(job.payload.type, job.payload.size);
    }
  }
}
🔌 7. IPC (Renderer ↔ Main)
Example
// renderer
window.electron.invoke("generateSongs", payload);

// main
ipcMain.handle("generateSongs", async (_, payload) => {
  queue.add({
    type: "generate",
    payload
  });
});
🧱 8. DATABASE CONNECTION
import { Pool } from "pg";

export const db = new Pool({
  host: "localhost",
  user: "postgres",
  password: "postgres",
  database: "MG"
});
🔥 9. CRITICAL IMPLEMENTATION NOTES
1. File Naming Standard
{batchId}_{songId}_{version}.mp3

Example:

20260421_12_OK.mp3
20260421_12_ALT.mp3
2. Directory Structure
/data
  /songs
  /images
  /thumbnails
  /merged
3. Logging

Always log:

AI calls
Automation steps
FFmpeg output
4. Error Handling
Retry AI calls (3x)
Skip failed songs (don’t block batch)