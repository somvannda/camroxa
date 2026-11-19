/**
 * Manual image asset inspection (PG-34/PG-37).
 *
 * The desktop bridge exposes no directory listing, so the page probes the four
 * expected file names directly. `inspectRunDirectory` stays pure and takes the
 * existence probe as an argument, which keeps it unit-testable.
 */

export const MANUAL_ASSET_EXTENSIONS = ["png", "jpg", "jpeg", "webp"] as const;

export const MANUAL_ASSET_SPECS = [
  { key: "background-16x9", label: "BG 16:9" },
  { key: "background-9x16", label: "BG 9:16" },
  { key: "thumbnail-16x9", label: "TH 16:9" },
  { key: "thumbnail-9x16", label: "TH 9:16" },
] as const;

export interface ManualAssetFile {
  key: string;
  label: string;
  fileName: string;
  present: boolean;
  checkedPaths: string[];
}

export interface ManualInspection {
  runDir: string;
  ready: boolean;
  readyCount: number;
  total: number;
  missing: string[];
  files: ManualAssetFile[];
  error: string | null;
}

export type ExistsProbe = (path: string) => Promise<boolean>;

function separatorFor(runDir: string): string {
  if (runDir.includes("\\") && !runDir.includes("/")) return "\\";
  if (runDir.includes("/") && !runDir.includes("\\")) return "/";
  return "\\";
}

export function joinRunPath(runDir: string, fileName: string): string {
  const base = String(runDir ?? "").trim().replace(/[\\/]+$/, "");
  if (!base) return fileName;
  return `${base}${separatorFor(base)}${fileName}`;
}

/**
 * Probes `background-16x9.(png|jpg|jpeg|webp)` and siblings. A probe that
 * throws counts as missing so a permissions error surfaces as "not ready"
 * instead of a rejected promise.
 */
export async function inspectRunDirectory(runDir: string, exists: ExistsProbe): Promise<ManualInspection> {
  const directory = String(runDir ?? "").trim();
  if (!directory) {
    return {
      runDir: "",
      ready: false,
      readyCount: 0,
      total: MANUAL_ASSET_SPECS.length,
      missing: MANUAL_ASSET_SPECS.map((spec) => spec.label),
      files: MANUAL_ASSET_SPECS.map((spec) => ({
        key: spec.key,
        label: spec.label,
        fileName: `${spec.key}.png`,
        present: false,
        checkedPaths: [],
      })),
      error: "This run has no folder on this device.",
    };
  }

  let permissionError: string | null = null;
  const files = await Promise.all(
    MANUAL_ASSET_SPECS.map(async (spec): Promise<ManualAssetFile> => {
      const checkedPaths = MANUAL_ASSET_EXTENSIONS.map((extension) =>
        joinRunPath(directory, `${spec.key}.${extension}`),
      );
      for (const candidate of checkedPaths) {
        try {
          if (await exists(candidate)) {
            return {
              key: spec.key,
              label: spec.label,
              fileName: candidate.slice(candidate.lastIndexOf(separatorFor(candidate)) + 1),
              present: true,
              checkedPaths,
            };
          }
        } catch (error) {
          permissionError = error instanceof Error ? error.message : "Unable to read the run folder.";
        }
      }
      return {
        key: spec.key,
        label: spec.label,
        fileName: `${spec.key}.png`,
        present: false,
        checkedPaths,
      };
    }),
  );

  const missing = files.filter((file) => !file.present).map((file) => file.label);
  return {
    runDir: directory,
    ready: missing.length === 0,
    readyCount: files.length - missing.length,
    total: files.length,
    missing,
    files,
    error: permissionError,
  };
}

export function missingAssetHint(missing: string[]): string | null {
  if (missing.length === 0) return null;
  return `Missing ${missing.join(", ")}. Add the file as background-16x9, background-9x16, thumbnail-16x9 or thumbnail-9x16 (png, jpg, jpeg or webp) in the run folder.`;
}
