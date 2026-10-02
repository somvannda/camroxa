import {
  generateLyrics,
  generateMusic,
  getBillingInfo,
  getClipsRaw,
  getLyrics,
  pollClips,
} from "./suno.js";
import { captchaRequired } from "./captcha.js";

const [, , command, ...args] = process.argv;

function print(label: string, data: unknown): void {
  console.log(`\n== ${label} ==`);
  console.log(JSON.stringify(data, null, 2));
}

async function cmdBilling(): Promise<void> {
  const info = await getBillingInfo();
  print("Account / billing info", info);
}

async function cmdLyrics(): Promise<void> {
  const prompt = args.join(" ") || "a song about hope and new beginnings";
  console.log(`Generating lyrics for: "${prompt}"`);
  const id = await generateLyrics(prompt);
  console.log(`Lyrics job id: ${id}`);
  let result;
  for (let i = 0; i < 60; i++) {
    result = await getLyrics(id);
    if (result.status === "complete" || result.status === "error") break;
    await new Promise((r) => setTimeout(r, 3_000));
  }
  print("Lyrics", result);
}

async function cmdGenerate(): Promise<void> {
  const description = args.join(" ") || "an upbeat synth-pop track about summer";
  console.log(`Generating music for: "${description}"`);
  const clips = await generateMusic({ gptDescriptionPrompt: description });
  print("Submitted clips", clips);
  const ids = clips.map((c) => c.id);
  if (ids.length) {
    console.log("\nPolling until complete...");
    const done = await pollClips(ids);
    print("Completed clips", done);
  }
}

async function main(): Promise<void> {
  try {
    switch (command) {
      case "billing":
        await cmdBilling();
        break;
      case "lyrics":
        await cmdLyrics();
        break;
      case "generate":
        await cmdGenerate();
        break;
      case "captcha":
        console.log("Captcha required?", await captchaRequired());
        break;
      case "models": {
        const info = await getBillingInfo();
        const anyInfo = info as Record<string, unknown>;
        console.log("keys:", Object.keys(anyInfo).join(", "));
        console.log(
          "models:",
          JSON.stringify(
            anyInfo.models ?? anyInfo.subscription ?? anyInfo.plan_info ?? null,
            null,
            2,
          ),
        );
        break;
      }
      case "clip": {
        const ids = args.filter((a) => a.trim().length > 0);
        if (!ids.length) {
          console.log("Usage: clip <id> [id2...]");
          break;
        }
        console.log("Polling clips:", ids.join(", "));
        const done = await pollClips(ids, 60_000, 5_000);
        print("Clips", done);
        break;
      }
      case "feed": {
        const ids = args.filter((a) => a.trim().length > 0);
        const raw = await getClipsRaw(ids);
        console.log("status:", raw.status);
        console.log("body:", raw.body);
        break;
      }
      default:
        console.log("Usage: npm run billing | lyrics [prompt] | generate [description]");
        console.log("Tip: start with `npm run billing` to verify auth works.");
    }
  } catch (err) {
    console.error("\nError:", err instanceof Error ? err.message : err);
    process.exit(1);
  }
}

main();
