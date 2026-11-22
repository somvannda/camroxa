/**
 * Electron-aware wrapper around `resolveUnderBase`: the configured Suno output
 * folder first, then the managed downloads folder.
 */
import { getDevicePreferences } from "./device-settings";
import { getAppPaths } from "./paths";
import { resolveUnderBase } from "../shared/user-paths";

export function userDataRoot(): string {
  const configured = getDevicePreferences().sunoOutputDir.trim();
  return configured || getAppPaths().downloads;
}

export function resolveUserPath(value: string): string {
  return resolveUnderBase(value, userDataRoot());
}
