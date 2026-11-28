/**
 * Starter templates that make a fresh install usable before the user signs in.
 *
 * The marketplace is where curated templates live, but a first-run picker that
 * is completely empty is the slowest possible start. Two small projects are
 * bundled with the app and copied into the template folder once; they need no
 * account, no network and no download, and the user can edit or delete them.
 */

import fs from "node:fs";
import path from "node:path";

import { logger } from "./logger";
import { saveVideoTemplate } from "./video-templates";

export interface StarterTemplate {
  /** Folder name in the user's templates directory. */
  id: string;
  /** Name shown in the Studio template picker. */
  name: string;
  /** File name inside the bundled starter directory. */
  file: string;
}

export const STARTER_TEMPLATES: readonly StarterTemplate[] = [
  {
    id: "neon-spectrum",
    name: "Neon Spectrum",
    file: "neon-spectrum.camxora-vizzy.json",
  },
  {
    id: "neon-reel",
    name: "Neon Reel",
    file: "neon-reel.camxora-vizzy.json",
  },
];

/**
 * Written after the first seed so templates the user deletes stay deleted
 * instead of reappearing on every launch.
 */
export const STARTER_SEED_MARKER = ".starter-templates-seeded";

function starterRootFromResources(): string {
  const resources = process.resourcesPath
    ? path.join(process.resourcesPath, "starter-templates")
    : "";
  return resources && fs.existsSync(resources) ? resources : "";
}

/** Dev/packaged starter source: env override, resources, then the app directory. */
export function resolveStarterTemplatesRoot(): string {
  const fromEnv = process.env.CAMXORA_STARTER_TEMPLATES_DIR;
  if (fromEnv) return path.resolve(fromEnv);
  const fromResources = starterRootFromResources();
  if (fromResources) return fromResources;
  return path.join(process.cwd(), "starter-templates");
}

/**
 * Copy the bundled starters into `root` when this is the first launch.
 *
 * Returns the ids that were created. A folder that already exists is left
 * alone (the user may have edited it), and any failure is logged instead of
 * blocking startup.
 */
export function seedStarterTemplates(
  root: string,
  sourceRoot: string = resolveStarterTemplatesRoot(),
): string[] {
  const marker = path.join(root, STARTER_SEED_MARKER);
  if (fs.existsSync(marker)) return [];

  fs.mkdirSync(root, { recursive: true });
  const seeded: string[] = [];
  for (const starter of STARTER_TEMPLATES) {
    const destination = path.join(root, starter.id);
    if (fs.existsSync(destination)) continue;
    const file = path.join(sourceRoot, starter.file);
    if (!fs.existsSync(file)) {
      logger.warn("starter template missing", { id: starter.id, file });
      continue;
    }
    try {
      saveVideoTemplate({
        root,
        name: starter.name,
        snapshotJson: fs.readFileSync(file, "utf8"),
        id: starter.id,
        createdAt: new Date().toISOString(),
      });
      seeded.push(starter.id);
    } catch (error) {
      logger.warn("starter template failed to install", {
        id: starter.id,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  try {
    fs.writeFileSync(marker, `${new Date().toISOString()}\n`, "utf8");
  } catch (error) {
    logger.warn("starter template marker could not be written", {
      error: error instanceof Error ? error.message : String(error),
    });
  }
  if (seeded.length > 0) logger.info("starter templates seeded", { ids: seeded });
  return seeded;
}
