import { app } from "electron";

export function devAuthBypass(): boolean {
  return !app.isPackaged && process.env.CAMXORA_DEV_AUTH === "1";
}
